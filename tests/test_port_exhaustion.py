"""윈도우 동적 포트 고갈 판정·회수 대상 선별 테스트 (REQ-20260825-100).

실사례(2026-08-25): WSL 포트 중계 COM 대리 프로세스(DllHost)가 동적 포트
16,384개 중 15,709개를 Bound 로 잡고 놓지 않아 새 리스닝 포트 공개가
실패했다 — 브라우저는 ERR_NO_BUFFER_SPACE, 테스트 29건 connection refused.
리눅스 쪽 자원 회수(--fix)로는 절대 풀리지 않는 상태라, 진단이 윈도우 쪽
소진도를 보고 회수 대상을 골라내야 한다.

판정 규칙 두 가지를 고정한다:
(1) 소진도 등급 — 고갈된 뒤가 아니라 임계(warn)에서 먼저 알린다.
(2) 회수 대상 — 지배적 점유 + COM 대리(dllhost)일 때만. 사용자 브라우저·앱은
    아무리 많이 잡고 있어도 죽이지 않고 안내만 한다.
실행: python3 tests/ port_exhaustion
"""
import importlib.util
import shutil
import tempfile
import time
import os
import unittest
from importlib.machinery import SourceFileLoader

HERE = os.path.dirname(os.path.abspath(__file__))
DOCTOR = os.path.join(HERE, "..", "bin", "s9-doctor")

spec = importlib.util.spec_from_loader(
    "s9doctor", SourceFileLoader("s9doctor", DOCTOR))
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)

RELAY_CMD = ("C:\\WINDOWS\\system32\\DllHost.exe "
             "/Processid:{17696EAC-9568-4CF5-BB8C-82515AAD6C09}")


def win(bound, top_count=0, name="dllhost.exe", cmd=RELAY_CMD, total=16384):
    return {"bound": bound, "start": 49152, "count": total,
            "top_pid": 31172, "top_count": top_count,
            "top_name": name, "top_cmd": cmd}


class PortVerdict(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(doctor.port_verdict(win(66))["level"], "ok")
        self.assertEqual(doctor.port_verdict(win(11000))["level"], "warn")
        self.assertEqual(doctor.port_verdict(win(15715))["level"], "critical")

    def test_no_windows_side_is_not_an_error(self):
        self.assertEqual(doctor.port_verdict({}), {})
        self.assertEqual(doctor.port_verdict(None), {})


class RecoverTarget(unittest.TestCase):
    def test_relay_hoarder_identified(self):
        t = doctor.relay_hoarder(win(15715, top_count=15709))
        self.assertIsNotNone(t)
        self.assertEqual(t["pid"], 31172)
        self.assertTrue(t["is_known_relay"])

    def test_user_app_never_a_target(self):
        """크롬이 다 잡고 있어도 사용자 브라우저는 죽이지 않는다."""
        self.assertIsNone(doctor.relay_hoarder(
            win(15715, top_count=15709, name="chrome.exe", cmd="chrome.exe")))

    def test_small_share_not_a_target(self):
        self.assertIsNone(doctor.relay_hoarder(win(66, top_count=29)))


class Advice(unittest.TestCase):
    def base(self, **kw):
        d = {"probe": {"ok": False, "latency": None, "stage": "publish",
                       "error": "12초 안에 공개되지 않음"},
             "degraded": True, "orphan_test_servers": [],
             "headless_chrome": [], "windows_ports": {}}
        d.update(kw)
        return d

    def test_exhaustion_points_at_reclaim_not_wsl_shutdown(self):
        d = self.base(windows_ports=win(15715, top_count=15709))
        lines = doctor.advise(d)
        text = "\n".join(lines)
        self.assertIn("--recover", text)
        first_recover = next(i for i, l in enumerate(lines) if "--recover" in l)
        # 회수를 설명하며 "wsl --shutdown 과 다르다"고 대비시키는 줄은 제외 —
        # 순서를 보는 것이지 단어 등장을 보는 게 아니다.
        shutdown = [i for i, l in enumerate(lines)
                    if "wsl --shutdown" in l and "--recover" not in l]
        self.assertTrue(shutdown and all(i > first_recover for i in shutdown),
                        "회수가 wsl --shutdown 보다 먼저 제시돼야 한다")
        # 호스트 포트가 이미 말랐으면 리눅스 쪽 --fix 보다 회수가 앞선다.
        first_fix = next(i for i, l in enumerate(lines) if "--fix" in l)
        ladder = [i for i, l in enumerate(lines) if l.startswith("1) ")]
        self.assertTrue(any("--recover" in lines[i] for i in ladder),
                        "고갈 상태에서는 회수가 첫 조치여야 한다")
        self.assertLess(min(i for i in ladder), first_fix)

    def test_warn_level_surfaces_before_exhaustion(self):
        d = self.base(probe={"ok": True, "latency": 0.3},
                      degraded=False, windows_ports=win(11000, top_count=10800))
        text = "\n".join(doctor.advise(d))
        self.assertIn("포트", text)


class Sweep(unittest.TestCase):
    """주인 없는 캡처 잔여물 회수 — 나이로만 가른다.

    캡처가 자기 것을 지우는 finally 는 세션이 중간에 죽으면 돌지 않는다.
    그렇게 남은 프로필·브라우저가 2026-08-25 사고의 씨앗이었다. 그렇다고
    무조건 지우면 **진행 중인 캡처**를 죽인다 — 그래서 나이가 유일한 기준이다.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s9sweep-")
        self._env = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = self.tmp
        # powershell 이 없는 환경으로 두어 윈도우 프로세스는 건드리지 않는다.
        self._which = doctor.shutil.which
        doctor.shutil.which = lambda name: None
        self._wintemp = doctor.WIN_TEMP
        doctor.WIN_TEMP = os.path.join(self.tmp, "no-such")

    def tearDown(self):
        doctor.shutil.which = self._which
        doctor.WIN_TEMP = self._wintemp
        if self._env is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mkprof(self, name, age):
        path = os.path.join(self.tmp, name)
        os.makedirs(path, exist_ok=True)
        old = 1_700_000_000.0 - age      # 고정 시각 기준 — 실행 시각에 안 흔들린다
        os.utime(path, (old, old))
        return path

    def test_old_marked_profile_removed_fresh_kept(self):
        stale = self.mkprof("s9shot-999", 0)          # 아주 오래된 것
        fresh = self.mkprof("s9shot-1000", 0)
        now = time.time()
        os.utime(fresh, (now, now))
        other = self.mkprof("my-work", 0)             # 표식 없는 남의 것
        out = doctor.sweep_stale_shots(max_age=600)
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(fresh), "진행 중인 캡처는 건드리지 않는다")
        self.assertTrue(os.path.exists(other), "표식 없는 것은 우리 것이 아니다")
        self.assertEqual(out["profiles"], 1)


if __name__ == "__main__":
    unittest.main()
