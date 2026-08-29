"""사람이 일을 세운다 — 세우기가 화면 손에 닿는다 (REQ-20260829-024 · 서버 몫).

사용자: "의도하지 않게 멈춘 작업들을 깨우려는 건데, 반대로 진행 중인 작업들을
강제로 중단하는 기능도 만들어라. 그래야 계정을 변경하거나 모델을 바꿀 때 그
기능을 같이 섞어서 사용할 수 있다."

021 이 낸 `worker_stop()` 은 **세션이 자기가 집은 문서의 작업자를 세우는 문**
이다. 화면에는 그 열쇠가 없다 — 대시보드에서 누르는 사람에게는 세션이 없고,
클레임을 요구하면 아무도 못 세운다. 그렇다고 화면이 자기 손으로 죽이면 게이트가
두 벌이 되고, 한 벌만 고쳐지는 사고가 시간 문제다.

그래서 이 라운드가 못 박는 것은 셋이다.
· 사람의 근거는 클레임이 아니라 **소유**다 — 같은 함수에 갈래 하나(owner)를
  낸다. 세션끼리의 규칙은 글자 그대로 그대로 둔다.
· 계정·모델을 바꾸는 걸음이 **도는 작업자를 남기지 않는다.** 옛 계정으로 도는
  작업자가 남으면 요금도 권한도 갈린다.
· 깨우기와 같은 모양으로 답한다 — 화면은 ok·action·message 셋만 읽는다.

실행: python3 tests/ stop_reach
"""
import importlib.machinery
import importlib.util
import inspect
import json
import os
import shutil
import signal
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
SRC = open(S9, encoding="utf-8").read()

DOC = "REQ-20260829-999-62x6"
PID = 424242


def _load(name="s9stop"):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, S9))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TheOwnersDoor(unittest.TestCase):
    """S4~S5 — 사람의 권한은 클레임이 아니라 소유다."""

    def setUp(self):
        self.m = _load("s9stop_o")
        self.tmp = tempfile.mkdtemp(prefix="s9stopo-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m._auto_dir = lambda: self.tmp
        self.marker()

    def marker(self, doc=DOC, pid=PID):
        with open(os.path.join(self.tmp, doc + ".json"), "w") as f:
            json.dump({"pid": pid, "last": 0}, f)

    def test_s4_the_owner_needs_no_claim(self):
        """화면에는 세션이 없다 — 클레임을 요구하면 아무도 못 세운다."""
        self.assertIn("owner", set(inspect.signature(self.m.worker_stop)
                                   .parameters),
                      "소유 갈래가 없다 — 화면은 이 문을 열 수 없다")
        sent = []
        alive = [True]

        def _alive(_p):
            v = alive[0]
            alive[0] = False       # SIGTERM 뒤에 물러난다
            return v
        r = self.m.worker_stop(DOC, session="", why="계정을 바꾼다", owner=True,
                               claims=lambda d, s: False,
                               kill=lambda p, s: sent.append((p, s)),
                               alive=_alive, wait=lambda _s: None,
                               note=lambda *a, **k: None)
        self.assertTrue(r.get("ok"), r.get("message"))
        self.assertTrue(r.get("stopped"))
        self.assertEqual([p for p, _ in sent], [PID],
                         "마커에 적힌 pid 가 아닌 것을 죽였다")

    def test_s4b_the_owner_still_owes_a_reason(self):
        """소유가 이유를 면제하지는 않는다 — 기록이 남아야 판정할 수 있다."""
        r = self.m.worker_stop(DOC, session="", why="  ", owner=True,
                               claims=lambda d, s: False,
                               kill=lambda *a: None, alive=lambda p: False,
                               note=lambda *a, **k: None)
        self.assertFalse(r.get("ok"))
        self.assertIn("이유", r.get("reason", ""))

    def test_s5_sessions_still_may_not_stop_each_other(self):
        """소유 갈래를 낸 김에 세션의 규칙이 헐거워지면 안 된다."""
        sent = []
        r = self.m.worker_stop(DOC, session="deadbeef", why="중복이다",
                               claims=lambda d, s: False,
                               kill=lambda p, s: sent.append((p, s)),
                               alive=lambda p: False,
                               note=lambda *a, **k: None)
        self.assertFalse(r.get("ok"))
        self.assertEqual(sent, [], "집지도 않은 세션이 작업자를 죽였다")


class TheScreenContract(unittest.TestCase):
    """S1~S3 · S9 — 화면은 깨우기와 같은 셋만 읽는다."""

    def setUp(self):
        self.m = _load("s9stop_c")
        self.tmp = tempfile.mkdtemp(prefix="s9stopc-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m._auto_dir = lambda: self.tmp

    def test_s1_the_shape_matches_wake(self):
        r = self.m.stop_request("REQ-does-not-exist-0000", actor="nicehugepark")
        self.assertEqual(set(("ok", "id", "action", "message")) - set(r), set())
        self.assertFalse(r["ok"])
        self.assertEqual(r["action"], "missing")

    def test_s2_pressing_twice_is_not_an_error(self):
        """도는 것이 없으면 '못 했다'가 아니라 '없다'다 — 멱등해야 손이 편하다."""
        self.m.locate = lambda _i: "/fake/doc.md"
        self.m.read_doc = lambda _p: ({"id": DOC, "type": "request",
                                       "status": "in-progress"}, "")
        r = self.m.stop_request(DOC, actor="nicehugepark")
        self.assertTrue(r.get("ok"), r.get("message"))
        self.assertEqual(r.get("action"), "none")

    def test_s2b_only_requests_are_stopped(self):
        self.m.locate = lambda _i: "/fake/doc.md"
        self.m.read_doc = lambda _p: ({"id": "DOC-x", "type": "knowledge"}, "")
        r = self.m.stop_request("DOC-x", actor="nicehugepark")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("action"), "not-request")

    def test_s3_the_screen_goes_through_the_one_door(self):
        """화면이 자기 손으로 죽이면 게이트가 두 벌이 된다."""
        i = SRC.find("def stop_request(")
        self.assertGreater(i, 0, "stop_request() 가 없다")
        j = SRC.find("\ndef ", i + 10)
        blk = SRC[i:j]
        self.assertIn("worker_stop", blk, "화면 몫이 worker_stop 을 안 지난다")
        for bad in ("SIGKILL", "SIGTERM", "os.kill"):
            self.assertNotIn(bad, blk, f"두 번째 죽이는 자리가 생겼다: {bad}")

    def test_s3b_the_press_carries_a_reason_and_the_owner_flag(self):
        """버튼에는 이유를 칠 자리가 없다 — 화면이 기본 사유를 싣는다."""
        seen = {}

        def fake(doc, **kw):
            seen.update(kw, doc=doc)
            return {"ok": True, "stopped": True, "pid": PID, "reason": "",
                    "message": "세웠다"}
        self.m.worker_stop = fake
        self.m.locate = lambda _i: "/fake/doc.md"
        self.m.read_doc = lambda _p: ({"id": DOC, "type": "request",
                                       "status": "in-progress"}, "")
        r = self.m.stop_request(DOC, actor="nicehugepark")
        self.assertTrue(seen.get("owner"), "소유 갈래로 부르지 않았다")
        self.assertTrue((seen.get("why") or "").strip(),
                        "이유 없이 불렀다 — worker_stop 이 거부한다")
        self.assertIn("nicehugepark", seen.get("why", ""),
                      "누가 눌렀는지가 사유에 없다")
        self.assertEqual(r.get("action"), "stopped")

    def test_s9_the_press_is_audited(self):
        i = SRC.find("def stop_request(")
        j = SRC.find("\ndef rework_watch_tick(", i)
        self.assertIn("_auto_log", SRC[i:j] if j > i else SRC[i:i + 3000],
                      "누른 것도 거부도 로그에 안 남는다")


class ManyAtOnce(unittest.TestCase):
    """S6 — 계정을 바꾸기 전에 도는 것을 한 번에 세운다."""

    def setUp(self):
        self.m = _load("s9stop_a")

    def test_s6_every_live_worker_is_stopped_and_counted(self):
        self.m.live_workers = lambda: [{"id": "REQ-a", "pid": 1, "age": 10},
                                       {"id": "REQ-b", "pid": 2, "age": 20}]
        stopped = []

        def fake(doc, **kw):
            stopped.append(doc)
            return {"ok": True, "stopped": True, "pid": 9, "reason": "",
                    "message": "세웠다"}
        self.m.worker_stop = fake
        r = self.m.stop_all_workers(actor="nicehugepark", why="계정을 바꾼다")
        self.assertTrue(r.get("ok"))
        self.assertEqual(sorted(r.get("ids") or []), ["REQ-a", "REQ-b"])
        self.assertEqual(r.get("count"), 2)
        self.assertEqual(sorted(stopped), ["REQ-a", "REQ-b"])

    def test_s6b_nothing_running_is_not_an_error(self):
        self.m.live_workers = lambda: []
        r = self.m.stop_all_workers(actor="nicehugepark", why="계정을 바꾼다")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r.get("count"), 0)
        self.assertTrue(r.get("message"))

    def test_s6c_no_second_kill_site(self):
        i = SRC.find("def stop_all_workers(")
        self.assertGreater(i, 0, "stop_all_workers() 가 없다")
        blk = SRC[i:SRC.find("\ndef ", i + 10)]
        self.assertIn("worker_stop", blk)
        for bad in ("SIGKILL", "os.kill"):
            self.assertNotIn(bad, blk, f"두 번째 죽이는 자리가 생겼다: {bad}")


class MixedWithTheAccountSwitch(unittest.TestCase):
    """S7~S8 — 계정·모델을 바꾸는 걸음과 섞인다."""

    def test_s7_restart_can_stop_the_workers_first(self):
        m = _load("s9stop_r")
        self.assertIn("stop_workers",
                      set(inspect.signature(m.restart_session).parameters),
                      "계정·모델을 바꾸며 작업자를 세울 자리가 없다")
        i = SRC.find("def restart_session(")
        blk = SRC[i:SRC.find("\ndef ", i + 10)]
        self.assertIn("stop_all_workers", blk,
                      "재기동이 도는 작업자를 그대로 둔다 — 옛 계정으로 계속 돈다")

    def test_s7b_the_restart_route_carries_it(self):
        i = SRC.find('parsed.path == "/api/session/restart"')
        self.assertGreater(i, 0)
        self.assertIn("stop_workers", SRC[i:i + 900],
                      "화면이 '세우고 바꾸기'를 보낼 자리가 없다")

    def test_s8_the_route_exists(self):
        i = SRC.find('parsed.path == "/api/stop"')
        self.assertGreater(i, 0, "POST /api/stop 이 없다 — 화면 손이 닿지 않는다")
        blk = SRC[i:i + 900]
        self.assertTrue("stop_request" in blk and "stop_all_workers" in blk,
                        "한 건과 전부, 두 갈래가 다 없다")

    def test_s8b_the_cli_stops_them_all(self):
        self.assertIn('wk.add_argument("--stop-all"', SRC,
                      "`s9 workers --stop-all` 이 파서에 없다")
        i = SRC.find("def cmd_workers(")
        self.assertIn("stop_all_workers", SRC[i:i + 1800],
                      "명령이 그 함수를 안 지난다")


if __name__ == "__main__":
    unittest.main()
