"""호스트 포트 감시 임계 동작 테스트 (REQ-20260825-102).

2026-08-25 사고: WSL 포트 중계가 윈도우 동적 포트 16,384개 중 15,709개를
물고 놓지 않아 OS 전체 아웃바운드가 끊겼다. 사람이 "인터넷이 안 된다"를
겪고 나서야 알았고, 그 전까지 아무 경고도 없었다.

그래서 serve 가 주기적으로 재고 임계마다 스스로 손을 쓴다. 이 테스트가
고정하는 것은 **임계와 그때의 행동**이다 —
  60% 미만: 아무것도 하지 않는다(멀쩡한데 건드리면 그게 사고다)
  60%↑   : 우리가 흘린 잔여물만 회수(비파괴)
  90%↑   : 점유자 회수 — 고갈되기 전에, 사람 개입 없이
윈도우 쪽을 못 읽는 환경(순수 리눅스)에서는 조용히 아무것도 하지 않는다.
실행: python3 tests/ port_guard
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

os.environ.setdefault("S9_ROOT", tempfile.mkdtemp(prefix="s9guard-"))
spec = importlib.util.spec_from_loader(
    "s9_mod_guard", importlib.machinery.SourceFileLoader("s9_mod_guard", S9))
s9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s9)


class FakeRun:
    def __init__(self, stdout="", rc=0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = rc


def fake_doctor(bound, total=16384, calls=None):
    """--json 은 진단을, 나머지 플래그는 성공을 돌려주는 가짜 s9-doctor."""
    payload = json.dumps({"windows_ports": {"bound": bound, "count": total,
                                            "top_name": "dllhost.exe",
                                            "top_pid": 31172,
                                            "top_count": bound}})

    def _doctor(*flags, timeout=90):
        if calls is not None:
            calls.append(flags)
        return FakeRun(payload if "--json" in flags and len(flags) == 1
                       else "{}")
    return _doctor


class PortGuard(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.logged = []
        self._orig = (s9._doctor, s9._guard_log)
        s9._guard_log = self.logged.append

    def tearDown(self):
        s9._doctor, s9._guard_log = self._orig

    def tick(self, bound, total=16384):
        s9._doctor = fake_doctor(bound, total, self.calls)
        return s9.port_guard_tick()

    def test_healthy_does_nothing(self):
        v = self.tick(211)
        self.assertIsNone(v["action"])
        self.assertEqual(self.calls, [("--json",)])
        self.assertFalse(self.logged)

    def test_warn_reclaims_only_our_leftovers(self):
        v = self.tick(11000)                      # 67%
        self.assertEqual(v["action"], "sweep")
        self.assertIn(("--sweep", "--json"), self.calls)
        self.assertNotIn(("--recover", "--yes"), self.calls)

    def test_critical_recovers_before_exhaustion(self):
        v = self.tick(15000)                      # 92% — 아직 100%가 아니다
        self.assertEqual(v["action"], "recover")
        self.assertIn(("--recover", "--yes"), self.calls)
        self.assertTrue(v["ok"])
        self.assertTrue(any("자동 회수" in m for m in self.logged))

    def test_no_windows_side_is_silent(self):
        s9._doctor = lambda *a, **k: FakeRun(json.dumps({"windows_ports": {}}))
        self.assertEqual(s9.port_guard_tick(), {})
        self.assertFalse(self.logged)

    def test_doctor_missing_does_not_raise(self):
        s9._doctor = lambda *a, **k: None
        self.assertEqual(s9.port_guard_tick(), {})


if __name__ == "__main__":
    unittest.main()
