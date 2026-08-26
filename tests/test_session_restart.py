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
        # s9 code 래퍼 경유 — 1회 수동 후엔 재시작 루프가 생겨 자동화된다
        self.assertIn("s9 code --resume mansess-full-session-id", r["cmd"])
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


class TestWorkerModel(unittest.TestCase):
    """무인 워커 모델 고정 (REQ-20260825-080, Fable 한도 소진 실사고).

    워커를 모델 지정 없이 띄우면 계정 기본 모델을 쓴다 — 그 모델 한도가 소진되면
    스폰된 워커가 전부 즉시 죽고, 대시보드 대상 세션까지 죽은 워커로 잡혀
    모델 변경조차 불가능해진다. auto_resume_model 설정이 그 경로를 막는다."""

    # R13. 설정이 있으면 --model 인자가 붙고, 없으면 붙지 않는다
    def test_r13_model_args(self):
        with mock.patch.object(mod, "user_config",
                               lambda n: {"auto_resume_model": "opus"}):
            self.assertEqual(mod._spawn_model_args("sjpark1"),
                             ["--model", "opus"])
        with mock.patch.object(mod, "user_config", lambda n: {}):
            self.assertEqual(mod._spawn_model_args("sjpark1"), [])
        # 설정 읽기 실패가 스폰을 막아선 안 된다
        with mock.patch.object(mod, "user_config",
                               mock.Mock(side_effect=OSError)):
            self.assertEqual(mod._spawn_model_args("sjpark1"), [])

    # R14. 모든 워커 스폰 경로가 이 인자를 통과한다 (한 군데라도 빠지면 재발)
    def test_r14_all_spawn_sites_covered(self):
        with open(S9, encoding="utf-8") as f:
            src = f.read()
        # 스폰 argv 조립 지점 — Popen 호출 형태가 아니라 argv 형태로 센다
        # (스폰 경로가 _spawn_worker 하나로 합쳐져도 계속 잡힌다)
        bare = src.count('["claude", "-p", prompt')
        covered = src.count("*_spawn_model_args(owner)")
        # 0 == 0 으로 조용히 통과하면 감시가 눈을 잃는다 — 하한을 못 박는다
        self.assertGreaterEqual(bare, 1, "워커 스폰 argv 조립 지점을 못 찾았다 "
                                         "— 패턴이 바뀌었으면 이 감시를 고쳐라")
        self.assertEqual(bare, covered, "모델 인자 없는 워커 스폰 경로가 남았다")

    # R15. <synthetic> 등 합성 모델 표기는 상태줄에 흘리지 않는다
    def test_r15_synthetic_model_ignored(self):
        tp = write_jsonl([asst("end_turn", "claude-opus-5"),
                          asst("end_turn", "<synthetic>")], "syn-full.jsonl")
        self.assertEqual(mod.session_model({"transcript_path": tp}),
                         "claude-opus-5")


class TestModelPersistence(unittest.TestCase):
    """모델 선택 지속 (REQ-20260825-080).

    대시보드 모델 변경은 재시작 마커의 --model 뿐이라 그 재개 1회에만 붙었다.
    세션이 새로 뜨거나(s9 code) 무인 워커가 스폰되면 계정 기본값으로 돌아가
    사용자가 고른 모델이 '제멋대로 되돌아가는' 것처럼 보였다."""

    def _idle_binding(self, sid, user="tester"):
        tp = write_jsonl([asst("end_turn")], f"{sid}-full-session-id.jsonl")
        make_binding(sid, attach_pid=str(os.getpid()), transcript_path=tp,
                     user=user)
        return tp

    # M2. --model 만 교체하고 나머지 인자는 보존 — 중복 누적 금지
    def test_m2_args_set_model(self):
        f = mod._args_set_model
        self.assertEqual(f("--permission-mode auto", "opus"),
                         "--permission-mode auto --model opus")
        self.assertEqual(f("--permission-mode auto --model fable", "opus"),
                         "--permission-mode auto --model opus")
        self.assertEqual(f("--model=fable --verbose", "opus"),
                         "--verbose --model opus")
        self.assertEqual(f("", "opus"), "--model opus")
        # 값이 빠진 꼬리 --model 도 삼킨다 (인자 밀림 방지)
        self.assertEqual(f("--verbose --model", "opus"), "--verbose --model opus")
        self.assertEqual(f("--model opus", ""), "")

    # M5. 재시작 루프가 --model 을 두 번 넘기지 않는다 — 마커가 이긴다
    def test_m5_restart_cmd_no_duplicate_model(self):
        base = ["claude", "--permission-mode", "auto", "--model", "fable"]
        cmd = mod._restart_cmd(base, {"resume": "S1", "model": "opus",
                                      "effort": "high"})
        self.assertEqual(cmd.count("--model"), 1, cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus", cmd)
        self.assertIn("--permission-mode", cmd)
        self.assertEqual(cmd[cmd.index("--resume") + 1], "S1")
        self.assertIn("--effort", cmd)
        # 마커에 모델이 없으면 base 의 모델을 그대로 둔다 (기존 동작 보존)
        cmd2 = mod._restart_cmd(base, {"resume": "S1", "effort": "high"})
        self.assertEqual(cmd2[:5], base)

    # M1+M6. 대시보드 변경이 두 저장처를 같은 값으로 맞춘다
    def test_m1_persist_both_places(self):
        cfg = {"s9code_args": "--permission-mode auto --model fable"}
        writes = {}

        def fake_set(name, key, value, actor=""):
            writes[key] = value
            cfg[key] = value
        with mock.patch.object(mod, "user_config", lambda n: dict(cfg)), \
                mock.patch.object(mod, "do_user_config_set", fake_set):
            done = mod._persist_model_choice("tester", "claude-opus-5[1m]")
        self.assertEqual(writes.get("auto_resume_model"), "claude-opus-5[1m]")
        self.assertEqual(writes.get("s9code_args"),
                         "--permission-mode auto --model claude-opus-5[1m]")
        self.assertEqual(sorted(done), ["auto_resume_model", "s9code_args"])

    # M3. 모델 없이 effort/account 만 바꾸면 config 를 건드리지 않는다
    def test_m3_no_model_no_write(self):
        called = []
        with mock.patch.object(mod, "do_user_config_set",
                               lambda *a, **k: called.append(a)):
            self.assertEqual(mod._persist_model_choice("tester", ""), [])
            self.assertEqual(mod._persist_model_choice("", "opus"), [])
        self.assertEqual(called, [])

    # M4. config 쓰기 실패가 재시작을 깨뜨리지 않는다 (best-effort)
    def test_m4_write_failure_isolated(self):
        self._idle_binding("persistfail")
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
                mock.patch.object(mod, "do_user_config_set",
                                  mock.Mock(side_effect=OSError("read-only"))):
            r = mod.restart_session("persistfail", model="opus")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r.get("saved"), [])

    # M1(경로). restart_session 성공이 실제로 저장을 호출한다
    def test_m1b_restart_persists(self):
        self._idle_binding("persistok")
        writes = {}
        with mock.patch.object(mod, "_pid_is_claude", lambda p: True), \
                mock.patch.object(mod, "user_config", lambda n: {}), \
                mock.patch.object(
                    mod, "do_user_config_set",
                    lambda n, k, v, actor="": writes.__setitem__(k, v)):
            r = mod.restart_session("persistok", model="claude-opus-5[1m]")
        self.assertTrue(r["ok"], r)
        self.assertEqual(writes.get("auto_resume_model"), "claude-opus-5[1m]")
        self.assertEqual(writes.get("s9code_args"), "--model claude-opus-5[1m]")


class TestRestartUiContract(unittest.TestCase):
    """대시보드 마크업 계약 (반려 재작업): 모델 라벨은 미상이어도 항상 보이고,
    구버전 serve(404)는 정확한 사유로 안내하며, 진단 플래그로 자가 검증 가능."""
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(HERE, "..", "web", "index.html"),
                  encoding="utf-8") as f:
            cls.html = f.read()

    # R7. 모델 미상 폴백 라벨 — 라벨 실종이 "실행부터 실패"로 보이던 결함
    def test_r7_model_label_always_visible(self):
        self.assertIn("ccmodelbtn", self.html)
        self.assertIn("model?", self.html)

    # R8. 구버전 serve의 404를 "서버 연결 실패"로 오진하지 않는다
    def test_r8_stale_serve_404_reason(self):
        self.assertIn("재시작 API 없음", self.html)

    # R9. ?nosse 진단 플래그 — 터미널 탭 헤드리스 캡처(자가 검증) 경로 유지
    def test_r9_nosse_diag_flag(self):
        self.assertIn("nosse", self.html)

    # R11 (REQ-20260825-045): ultracode는 숨은 기능이 아니어야 한다 —
    #      패널에 설명 + 키워드 삽입 버튼이 있고, effort와 구분해 안내한다.
    def test_r11_ultracode_documented(self):
        self.assertIn("mpuc", self.html)
        self.assertIn("ultracode", self.html)
        self.assertIn("다중 에이전트", self.html)

    # R12 (REQ-20260825-047): 재시작 진행 표시 — 스피너+경과초가 살아 있고
    #      복귀 시 완료 줄로 교체된다("멈춘 듯" 보이던 정적 안내 대체)
    def test_r12_restart_progress_indicator(self):
        self.assertIn("termRestartDone", self.html)
        self.assertIn("cc-restart", self.html)
        self.assertIn("재시작 완료", self.html)

    # R10 (실사고): 모델 선택지에 fable 누락 → opus로 바꾼 뒤 되돌아갈 수 없었다.
    #      claude --help의 별칭(fable/opus/sonnet)이 모두 선택 가능해야 한다.
    def test_r10_model_choices_include_fable(self):
        import re as _re
        m = _re.search(r'row\("m", "model", \[([^\]]*)\]\)', self.html)
        self.assertIsNotNone(m, "모델 선택 행 정의를 찾을 수 없다")
        choices = [c.strip().strip('"') for c in m.group(1).split(",")]
        for alias in ("fable", "opus", "sonnet"):
            self.assertIn(alias, choices)


if __name__ == "__main__":
    unittest.main(verbosity=2)
