"""대시보드 세션 깨우기 (REQ-20260825-067).

세션이 없으면 대시보드만으로는 되살릴 수 없었다 — 서버가 새 터미널 창을
열어 s9 code를 실행한다. 창을 열 수 없는 환경은 실행 명령을 안내한다.
살아있는 세션이 있으면 중복 스폰하지 않는다.

실행: python3 tests/ session_wake
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

TMP = tempfile.mkdtemp(prefix="s9wake-")
_prev = {k: os.environ.get(k) for k in ("S9_ROOT", "S9_MACHINE")}
os.environ.update({"S9_ROOT": TMP, "S9_MACHINE": "testbox"})
try:
    spec = importlib.util.spec_from_loader(
        "s9_mod_wake", importlib.machinery.SourceFileLoader("s9_mod_wake", S9))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class TestWake(unittest.TestCase):
    # W1. 살아있는 세션이 있으면 스폰하지 않는다 (중복 창 방지)
    def test_w1_refuses_when_live(self):
        with mock.patch.object(mod, "chat_target",
                               lambda *_a, **_k: {"session": "livesess"}), \
             mock.patch.object(mod, "chat_live", lambda *_a, **_k: True):
            r = mod.wake_session()
        self.assertFalse(r["ok"])
        self.assertIn("살아있는 세션", r["reason"])

    # W2. 세션이 없으면 창을 띄운다 — 실행 인자에 s9 code가 들어간다
    def test_w2_spawns_terminal(self):
        calls = []

        class P:
            def __init__(self, argv, **kw):
                calls.append((argv, kw))

        with mock.patch.object(mod, "chat_target", lambda *_a, **_k: None), \
             mock.patch("subprocess.Popen", P), \
             mock.patch("shutil.which", lambda n: "/usr/bin/" + n
                        if n == "xterm" else None):
            r = mod.wake_session()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["mode"], "spawned")
        self.assertTrue(calls, "터미널을 띄우지 않았다")
        argv = " ".join(calls[0][0])
        self.assertIn("bin/s9 code", argv)
        self.assertIn("start_new_session", calls[0][1])   # 세션 분리 필수

    # W3. 창을 열 수 없으면 실행 명령을 안내한다 (실패가 아니라 폴백)
    def test_w3_manual_fallback(self):
        with mock.patch.object(mod, "chat_target", lambda *_a, **_k: None), \
             mock.patch("shutil.which", lambda n: None), \
             mock.patch("builtins.open", side_effect=OSError), \
             mock.patch("glob.glob", lambda *_a, **_k: []):
            r = mod.wake_session()
        self.assertTrue(r["ok"])
        self.assertEqual(r["mode"], "manual")
        self.assertIn("bin/s9 code", r["cmd"])

    # W4. 프런트: 대기 화면에 깨우기 버튼과 호출 경로가 있다
    def test_w4_ui_button(self):
        with open(index_path(),
                  encoding="utf-8") as f:
            html = f.read()
        self.assertIn("cc-wake", html)
        self.assertIn("/api/session/wake", html)
        self.assertIn("여기서 세션 깨우기", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
