"""세션 모델 제어 테스트 (REQ-20260825-037).

CC는 실행 중 model/effort 외부 변경을 지원하지 않는다 — 같은 대화를
`claude --resume --model --effort`로 재개하는 재기동 경로를 검증한다:
session_model(트랜스크립트 모델 추출), 재시작 마커 소비, restart_session 가드.

격리: S9_ROOT=mktemp (모듈 import 시점 캡처, env 즉시 복원).
실행: python3 tests/ session_restart
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

TMP = tempfile.mkdtemp(prefix="s9restart-")
_prev = {k: os.environ.get(k) for k in ("S9_ROOT", "S9_MACHINE")}
os.environ["S9_ROOT"] = TMP
os.environ["S9_MACHINE"] = "testbox"
try:
    spec = importlib.util.spec_from_loader(
        "s9_mod_rst", importlib.machinery.SourceFileLoader("s9_mod_rst", S9))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def write_jsonl(entries, name):
    path = os.path.join(TMP, name)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return path


def asst(stop, model="claude-fable-5"):
    return {"type": "assistant",
            "message": {"stop_reason": stop, "model": model,
                        "content": [{"type": "text", "text": "x"}]}}


def make_binding(sid, **kv):
    os.makedirs(mod.STATE, exist_ok=True)
    b = {"machine": "testbox", "session": sid, "user": "", "history": [], **kv}
    with open(os.path.join(mod.STATE, f"testbox__{sid}.json"), "w",
              encoding="utf-8") as f:
        json.dump(b, f)


class TestSessionModel(unittest.TestCase):
    # R1. 트랜스크립트 마지막 assistant의 model을 읽는다 (캐시는 mtime 기준)
    def test_r1_last_model(self):
        tp = write_jsonl([asst("tool_use", "claude-old-1"),
                          asst("end_turn", "claude-fable-5")],
                         "m1-full.jsonl")
        self.assertEqual(mod.session_model({"transcript_path": tp}),
                         "claude-fable-5")
        self.assertEqual(mod.session_model({"transcript_path": "/no/file"}), "")


class TestRestartMarker(unittest.TestCase):
    # R2. 내 pid를 지목한 신선한 마커만 소비(반환+삭제), 낡은 것은 정리
    def test_r2_marker_consumption(self):
        os.makedirs(os.path.join(TMP, "state", "terminal"), exist_ok=True)
        mine = mod._restart_marker_path("rstsess")
        with open(mine, "w", encoding="utf-8") as f:
            json.dump({"wrapper_pid": os.getpid(), "resume": "full-id",
                       "model": "opus", "effort": "high",
                       "ts": time.time()}, f)
        other = mod._restart_marker_path("othersess")
        with open(other, "w", encoding="utf-8") as f:
            json.dump({"wrapper_pid": 1, "resume": "x",
                       "ts": time.time()}, f)
        stale = mod._restart_marker_path("stalesess")
        with open(stale, "w", encoding="utf-8") as f:
            json.dump({"wrapper_pid": os.getpid(), "resume": "y",
                       "ts": time.time() - mod.RESTART_FRESH_SEC - 10}, f)
        m = mod._consume_restart_marker()
        self.assertIsNotNone(m)
        self.assertEqual(m["resume"], "full-id")
        self.assertFalse(os.path.exists(mine))     # 소비 = 삭제
        self.assertTrue(os.path.exists(other))     # 남의 마커는 보존
        self.assertFalse(os.path.exists(stale))    # 낡은 마커는 정리
        os.remove(other)


class TestRestartGuards(unittest.TestCase):
    def _idle_binding(self, sid):
        tp = write_jsonl([asst("end_turn")], f"{sid}-full-session-id.jsonl")
        make_binding(sid, attach_pid=str(os.getpid()), transcript_path=tp)
        return tp

    # R3. busy 세션 거부 — 진행 중 작업 보호
    def test_r3_busy_refused(self):
        tp = write_jsonl([asst("tool_use")], "busy-full.jsonl")
        make_binding("busysess", attach_pid=str(os.getpid()),
                     transcript_path=tp)
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True):
            r = mod.restart_session("busysess", model="opus")
        self.assertFalse(r["ok"])
        self.assertIn("진행 중", r["reason"])

    # R4. 래퍼 부재(부모가 s9 code 아님) → mode=manual + 정확한 재개 명령
    def test_r4_manual_mode_cmd(self):
        self._idle_binding("mansess")
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True):
            r = mod.restart_session("mansess", model="opus", effort="high")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["mode"], "manual")
        self.assertIn("claude --resume mansess-full-session-id", r["cmd"])
        self.assertIn("--model opus", r["cmd"])
        self.assertIn("--effort high", r["cmd"])

    # R5. effort 무효값·변경 항목 없음 거부
    def test_r5_invalid_inputs(self):
        self._idle_binding("valsess")
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True):
            r = mod.restart_session("valsess", effort="ultra")
            self.assertFalse(r["ok"])
            self.assertIn("effort", r["reason"])
            r = mod.restart_session("valsess")
            self.assertFalse(r["ok"])
            self.assertIn("변경할 항목", r["reason"])

    # R6. 죽은 pid 거부
    def test_r6_dead_pid(self):
        make_binding("deadrst", attach_pid="999999999",
                     transcript_path=os.path.join(TMP, "none.jsonl"))
        r = mod.restart_session("deadrst", model="opus")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
