"""Esc 즉시 인터럽트 가드 테스트 (REQ-20260825-008).

interrupt_session은 가드 전부 통과 시에만 SIGINT 1회 — 모든 실패는 신호 없이
skipped 보고(협조적 중단 폴백). busy 판정은 트랜스크립트 마지막 메시지
이벤트로: assistant stop_reason=end_turn 또는 [Request interrupted] = idle.

실행: python3 tests/test_interrupt.py
"""
import importlib.machinery
import importlib.util
import json
import os
import signal
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

TMP = tempfile.mkdtemp(prefix="s9int-")
# 모듈 import 시점에만 ROOT/MACHINE 고정 — 같은 프로세스의 다른 테스트 모듈에
# 전역 env가 새지 않게 즉시 복원한다 (mod.ROOT/STATE는 import 시 캡처됨)
_prev = {k: os.environ.get(k) for k in ("S9_ROOT", "S9_MACHINE")}
os.environ["S9_ROOT"] = TMP
os.environ["S9_MACHINE"] = "testbox"
try:
    spec = importlib.util.spec_from_loader(
        "s9_mod_int", importlib.machinery.SourceFileLoader("s9_mod_int", S9))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def write_transcript(entries):
    fd, path = tempfile.mkstemp(suffix=".jsonl", dir=TMP)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return path


def asst(stop, content):
    return {"type": "assistant", "message": {"stop_reason": stop,
                                             "content": content}}


class TestTranscriptBusy(unittest.TestCase):
    # B1. end_turn으로 끝난 트랜스크립트 = idle
    def test_b1_end_turn_idle(self):
        p = write_transcript([{"type": "user", "message": {"content": "해줘"}},
                              asst("end_turn", [{"type": "text", "text": "done"}])])
        self.assertFalse(mod._transcript_busy(p))

    # B2. tool_use로 끝남 = busy (도구 실행 대기/진행)
    def test_b2_tool_use_busy(self):
        p = write_transcript([asst("tool_use", [{"type": "tool_use"}])])
        self.assertTrue(mod._transcript_busy(p))

    # B3. tool_result(user 턴)로 끝남 = busy (다음 어시스턴트 응답 예정)
    def test_b3_tool_result_busy(self):
        p = write_transcript([asst("tool_use", [{"type": "tool_use"}]),
                              {"type": "user",
                               "message": {"content": [{"type": "tool_result"}]}}])
        self.assertTrue(mod._transcript_busy(p))

    # B4. 직전 중단 마커([Request interrupted…]) = idle — 재신호 방지
    def test_b4_interrupted_marker_idle(self):
        p = write_transcript([{"type": "user", "message":
                               {"content": "[Request interrupted by user]"}}])
        self.assertFalse(mod._transcript_busy(p))
        p2 = write_transcript([{"type": "user", "message": {"content": [
            {"type": "text", "text": "[Request interrupted by user]"}]}}])
        self.assertFalse(mod._transcript_busy(p2))

    # B5. 판정 불가(파일 부재·메시지 이벤트 없음·메타뿐) = idle 취급(신호 금지)
    def test_b5_unknown_is_idle(self):
        self.assertFalse(mod._transcript_busy(os.path.join(TMP, "no.jsonl")))
        p = write_transcript([{"type": "ai-title", "aiTitle": "x"}])
        self.assertFalse(mod._transcript_busy(p))


def make_binding(sid, **kv):
    os.makedirs(mod.STATE, exist_ok=True)
    b = {"machine": "testbox", "session": sid, "user": "", "history": [], **kv}
    with open(os.path.join(mod.STATE, f"testbox__{sid}.json"), "w",
              encoding="utf-8") as f:
        json.dump(b, f)
    return b


class TestInterruptGuards(unittest.TestCase):
    # G1. attach 프로세스 미생존 → skipped
    def test_g1_dead_pid(self):
        make_binding("g1sess", attach_pid="999999999")
        r = mod.interrupt_session("g1sess")
        self.assertEqual(r["signal"], "skipped")

    # G2. pid 재사용 방어: 살아있지만 claude가 아닌 프로세스 → skipped
    def test_g2_pid_not_claude(self):
        make_binding("g2sess", attach_pid="1")     # pid 1 = init/systemd
        r = mod.interrupt_session("g2sess")
        self.assertEqual(r["signal"], "skipped")
        self.assertIn("claude", r["reason"])

    # G3. 전 가드 통과 → SIGINT 정확히 1회. 직후 재요청은 쿨다운 거부.
    def test_g3_sent_then_cooldown(self):
        tp = write_transcript([asst("tool_use", [{"type": "tool_use"}])])
        make_binding("g3sess", attach_pid=str(os.getpid()),
                     transcript_path=tp)
        calls = []
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
             mock.patch.object(mod.os, "kill",
                               lambda pid, sig: calls.append((pid, sig))):
            r = mod.interrupt_session("g3sess")
            self.assertEqual(r["signal"], "sent", r)
            self.assertEqual(calls, [(os.getpid(), signal.SIGINT)])
            r2 = mod.interrupt_session("g3sess")
            self.assertEqual(r2["signal"], "skipped")
            self.assertIn("쿨다운", r2["reason"])
            self.assertEqual(len(calls), 1)        # 신호는 여전히 1회

    # G4. idle(end_turn) 트랜스크립트 → 신호 금지
    def test_g4_idle_refused(self):
        tp = write_transcript([asst("end_turn", [{"type": "text", "text": "x"}])])
        make_binding("g4sess", attach_pid=str(os.getpid()),
                     transcript_path=tp)
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
             mock.patch.object(mod.os, "kill",
                               side_effect=AssertionError("신호 금지")):
            r = mod.interrupt_session("g4sess")
        self.assertEqual(r["signal"], "skipped")
        self.assertIn("idle", r["reason"])

    # G5. 활동 신선도 상실(오래된 트랜스크립트) → 신호 금지
    def test_g5_stale_refused(self):
        tp = write_transcript([asst("tool_use", [{"type": "tool_use"}])])
        old = time.time() - mod.INTERRUPT_FRESH_SEC - 60
        os.utime(tp, (old, old))
        make_binding("g5sess", attach_pid=str(os.getpid()),
                     transcript_path=tp)
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
             mock.patch.object(mod.os, "kill",
                               side_effect=AssertionError("신호 금지")):
            r = mod.interrupt_session("g5sess")
        self.assertEqual(r["signal"], "skipped")
        self.assertIn("신선도", r["reason"])

    # G6. ended 바인딩 → skipped
    def test_g6_ended(self):
        make_binding("g6sess", attach_pid=str(os.getpid()), ended="1")
        r = mod.interrupt_session("g6sess")
        self.assertEqual(r["signal"], "skipped")

    # G7. os.kill 예외도 skipped 보고 — 500으로 새지 않는다
    def test_g7_kill_error_reported(self):
        tp = write_transcript([asst("tool_use", [{"type": "tool_use"}])])
        make_binding("g7sess", attach_pid=str(os.getpid()),
                     transcript_path=tp)
        def boom(pid, sig):
            raise PermissionError("denied")
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
             mock.patch.object(mod.os, "kill", boom):
            r = mod.interrupt_session("g7sess")
        self.assertEqual(r["signal"], "skipped")
        self.assertIn("오류", r["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
