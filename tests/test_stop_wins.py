"""중단 도장이 잔상을 이긴다 (2026-08-31 18:12 실사고).

사용자가 카드의 ⏸ 로 위임 작업을 세웠는데, 카드가 ▶ 로 돌아오지 않았다 —
판정이 죽인 위임 손의 열린 기여(3분), 이어서 리드의 중단 처리 명령(손길)을
차례로 attached 로 읽으며 ⏸ 를 계속 그렸다. "중단 처리가 된 거 맞나?"

규칙: 사람이 세운(stopped) 문서에서 붙음을 주장하려면 그 손이 도장 **뒤에
실제로 움직였어야** 한다. 손길(s9 명령 흔적)은 도장을 아예 못 이긴다 —
세우기 직후의 보고·해제 명령이 곧 손길이라 시간 규칙으로도 못 거른다.
pid 생존을 확인한 현재-진실(워커·잡)은 그대로 이긴다.

실행: python3 tests/ stop_wins
"""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


def s9mod(root):
    os.environ["S9_ROOT"] = root
    name = "s9stopw_" + os.path.basename(root)
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, S9))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class StopWins(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s9stopw-")
        self.m = s9mod(self.tmp)
        self.now = time.time()
        # 판정 밖 신호는 전부 조용하게 — 각 시험이 필요한 것만 세운다
        self.m.unassigned_hands = lambda now=None: []
        self.m.delegated_running = lambda *a, **k: None
        self.m.heartbeat_age = lambda *a, **k: None
        self.m.live_agents = lambda *a, **k: []
        self.m._wait_info = lambda *a, **k: None
        self.m.worker_running = lambda *a, **k: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def row(self, stopped_age=None, **kw):
        r = {"id": "REQ-20260831-900-zzzz", "status": "in-progress",
             "updated": "2026-08-31T00:00:00+09:00"}
        if stopped_age is not None:
            r["stopped"] = {"at": self.now - stopped_age, "by": "u",
                            "age": int(stopped_age)}
        r.update(kw)
        return r

    def verdict(self, r):
        return self.m.stall_verdict(r, self.now, self.m.STALLED_WIN,
                                    hands=[], assigned={})

    # S1. 죽은 위임 잔상 — 기여의 마지막 움직임이 도장보다 옛것이면 못 이긴다
    def test_s1_a_dead_delegates_leftover_does_not_beat_the_stop(self):
        self.m.delegated_running = lambda *a, **k: {"transcript": "/no/such"}
        self.m._path_age = lambda p, n: 300          # 도장(120초 전)보다 옛 활동
        v = self.verdict(self.row(stopped_age=120))
        self.assertNotEqual(v["state"], "attached", v)

    # S2. 손길 잔상 — 세우기 직후의 s9 명령은 도장을 못 이긴다
    def test_s2_a_bookkeeping_hand_does_not_beat_the_stop(self):
        self.m.heartbeat_age = lambda *a, **k: 30    # 방금 지나간 손길
        self.m.heartbeat_session = lambda *a, **k: "deadbeef"
        v = self.verdict(self.row(stopped_age=60))
        self.assertNotEqual(v["state"], "attached", v)

    # S3. 도장 뒤의 실제 움직임 — 진짜 일하는 손은 그대로 이긴다
    def test_s3_real_movement_after_the_stop_still_wins(self):
        self.m.delegated_running = lambda *a, **k: {"transcript": "/no/such"}
        self.m._path_age = lambda p, n: 10           # 도장(120초 전) 뒤에 움직임
        v = self.verdict(self.row(stopped_age=120))
        self.assertEqual(v["state"], "attached", v)

    # S4. 도장이 없으면 기존 판정 그대로 — 위임 손은 attached 다
    def test_s4_without_a_stop_the_old_contract_stands(self):
        self.m.delegated_running = lambda *a, **k: {"transcript": "/no/such"}
        self.m._path_age = lambda p, n: 300
        v = self.verdict(self.row())
        self.assertEqual(v["state"], "attached", v)

    # S5. 현재-진실은 도장보다 세다 — pid 생존을 확인한 워커·잡은 그대로
    def test_s5_a_pid_verified_job_still_wins(self):
        v = self.verdict(self.row(stopped_age=60,
                                  jobs=[{"name": "테스트", "mins": 3}]))
        self.assertEqual(v["state"], "attached", v)


if __name__ == "__main__":
    unittest.main(verbosity=2)
