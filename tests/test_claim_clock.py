"""클레임은 진전이 아니다 — 멈춤 시계를 되감지 않는다 (REQ-20260829-034-62x6).

실측 2026-08-29 17:36~ (REQ-20260828-041 라운드2). 멈춤 판정 `stall_mins()` 의
시계는 문서의 `updated` 하나다. 그런데 클레임(`stamp_doc_session`)이 문서를
쓰면서 그 `updated` 를 갱신했다. 그래서 이런 순서가 성립했다:

  ① 사람이 깨운다 → ② 워커가 뜨자마자 프롬프트 지시대로 `s9 last <id> --add`
  로 클레임한다(updated 갱신) → ③ 워커가 아무것도 못 하고 죽는다 →
  ④ 카드는 15분 동안 "아직 멈춘 게 아니다 — 방금 문서가 움직였다"로 답한다.

**한 일이 없는데 경보만 꺼진다.** 사용자가 같은 날 "깨우기가 안 된다"고 두 번
반려한 것이 이 뿌리다.

고른 길은 후보 ② 다 — 클레임이 `updated` 를 건드리지 않는다. 후보 ①(진전의
시계를 '실질 진전'으로 좁힌다)은 판정에 축을 하나 더 세우는데, 그 축이 어느
쓰기 자리 하나를 빠뜨리면 **일하는 손 위에 두 번째 손이 붙는다**(이 저장소가
네 번 덴 그 사고). ② 는 쓰기 자리 **하나에서 bump 를 빼는 것**이라, 손대지
않은 모든 경로가 지금 동작(넓은 쪽=안전한 쪽)을 그대로 지킨다.

실행: python3 tests/ claim_clock
"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

DOC = "REQ-20260829-034-62x6"


def s9mod(root):
    """bin/s9 를 격리 ROOT 로 적재한다 (S9_ROOT 는 모듈 상단에서 읽힌다)."""
    os.environ["S9_ROOT"] = root
    name = "s9clock_" + os.path.basename(root)
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, S9))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ago(sec):
    return (datetime.datetime.now().astimezone()
            - datetime.timedelta(seconds=sec)).isoformat(timespec="seconds")


class ClaimClock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s9clock-")
        self.env = {**os.environ, "S9_ROOT": self.tmp,
                    "S9_MACHINE": "testbox", "S9_USER": "tester"}
        self.env.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], capture_output=True, text=True,
                       env=self.env, timeout=60, stdin=subprocess.DEVNULL)
        self.m = s9mod(self.tmp)
        self.m.current_machine = lambda: "testbox"
        os.makedirs(self.m.STATE, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 픽스처 --------------------------------------------------------
    def doc(self, *, quiet_sec=1200, session="aaaaaaaa", sessions=None,
            status="in-progress", doc_id=DOC):
        """조용한 지 quiet_sec 초 된 in-progress 요청 하나."""
        path = os.path.join(self.m.VAULT, "requests", "2026", "08",
                            doc_id + ".md")
        meta = {"id": doc_id, "type": "request",
                "title": "클레임이 멈춤 시계를 되감는다",
                "summary": "s", "status": status, "size": "M",
                "user": "tester", "machine": "testbox",
                "created": ago(quiet_sec + 60), "updated": ago(quiet_sec),
                "status_since": ago(quiet_sec + 30), "priority": 50}
        if session:
            meta["session"] = session
        if sessions:
            meta["sessions"] = list(sessions)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.m.write_doc(path, meta, "\n## Notes\n\n## History\n")
        self.m.rebuild_index(quiet=True)
        return path

    def meta_of(self, path):
        return self.m.read_doc(path)[0]

    def stall(self, doc_id=DOC, win=None):
        """화면이 보는 그 값 — catalog_with_live 가 행에 실어 주는 stalled_mins."""
        win = self.m.STALLED_WIN if win is None else win
        row = next((r for r in self.m.catalog_with_live(stall_win=win)
                    if r["id"] == doc_id), None)
        self.assertIsNotNone(row, "카탈로그에 문서가 없다")
        return row.get("stalled_mins")

    # ---- C1/C2 ---------------------------------------------------------
    def test_c1_claim_does_not_rewind_the_clock(self):
        """C1. 클레임은 `updated` 를 건드리지 않는다."""
        path = self.doc(quiet_sec=1200, session="aaaaaaaa")
        before = self.meta_of(path)["updated"]
        self.assertTrue(self.m.stamp_doc_session(DOC, "bbbbbbbb"),
                        "도장이 아예 안 찍혔다 — 이 시험의 전제가 깨졌다")
        self.assertEqual(self.meta_of(path)["updated"], before,
                         "클레임 한 줄이 진전의 시계를 되감았다")

    def test_c2_the_stamp_still_lands(self):
        """C2. 시계를 안 건드려도 승계 도장은 문서에 남는다."""
        path = self.doc(quiet_sec=1200, session="aaaaaaaa")
        self.m.stamp_doc_session(DOC, "bbbbbbbb")
        meta = self.meta_of(path)
        self.assertEqual(meta.get("session"), "bbbbbbbb")
        self.assertEqual(meta.get("sessions"), ["aaaaaaaa", "bbbbbbbb"])

    # ---- C3 (실사고 재현) ----------------------------------------------
    def test_c3_a_dead_worker_claim_does_not_silence_the_alarm(self):
        """C3. 20분 조용한 요청은 워커가 클레임한 직후에도 멈춤이다.

        이것이 사용자가 본 그 장면이다 — 깨웠는데 워커가 클레임만 하고 죽어,
        카드가 15분간 다시 누를 것을 주지 않았다.
        """
        self.doc(quiet_sec=1200, session="aaaaaaaa")
        self.assertEqual(self.stall(), 20, "전제: 클레임 전에는 20분째 멈춤")
        self.m.stamp_doc_session(DOC, "bbbbbbbb")   # 워커가 뜨자마자 클레임
        self.assertEqual(self.stall(), 20,
                         "클레임 한 줄에 멈춤 경보가 꺼졌다 "
                         "— 한 일이 없는데 시계가 되감겼다")

    # ---- C4 (판정은 한 자리) -------------------------------------------
    def test_c4_screen_cli_and_wake_agree(self):
        """C4. 화면·CLI·깨우기가 같은 답을 준다 — 클레임 전후 모두."""
        self.doc(quiet_sec=1200, session="aaaaaaaa")
        for label in ("클레임 전", "클레임 후"):
            with self.subTest(label):
                self.assertEqual(self.stall(), 20)
                cli = {r["id"]: r["mins"] for r in self.m.stalled_requests()}
                self.assertEqual(cli.get(DOC), 20, "CLI 가 화면과 다르다")
                res = self.m.wake_request(DOC, actor="tester")
                self.assertNotEqual(
                    res["action"], "moving",
                    "화면은 멈춤이라는데 손잡이는 '아직 돈다'며 거부했다")
                self.assertEqual(res["mins"], 20)
                self.m.stamp_doc_session(DOC, "bbbbbbbb")

    def test_c4b_a_moving_doc_is_refused_everywhere(self):
        """C4b. 방금 움직인 요청은 세 자리 모두 '아직 아니다' 로 일치한다."""
        self.doc(quiet_sec=10, session="aaaaaaaa")
        self.assertIsNone(self.stall())
        self.assertEqual(self.m.stalled_requests(), [])
        res = self.m.wake_request(DOC, actor="tester")
        self.assertEqual(res["action"], "moving")
        self.assertFalse(res["ok"])

    # ---- C5 (진짜 진전은 시계를 움직인다) ------------------------------
    def test_c5_a_real_note_moves_the_clock(self):
        """C5. 노트 한 줄(실질 진전)은 여전히 시계를 움직인다."""
        self.doc(quiet_sec=1200, session="aaaaaaaa")
        self.assertEqual(self.stall(), 20)
        r = subprocess.run([S9, "note", DOC, "진전 한 줄", "--label", "test"],
                           capture_output=True, text=True, env=self.env,
                           timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(self.stall(), "노트를 붙였는데 여전히 멈춤이라 한다")

    def test_c5b_a_transition_moves_the_clock(self):
        """C5b. 상태 전이도 진전이다 — 승계 도장이 함께 찍혀도 시계는 움직인다."""
        self.doc(quiet_sec=1200, session="aaaaaaaa", status="open")
        r = subprocess.run([S9, "status", DOC, "in-progress",
                            "--note", "착수"],
                           capture_output=True, text=True,
                           env={**self.env, "S9_SESSION": "cccccccc"},
                           timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(self.stall(), "착수 전이가 시계를 못 움직였다")

    # ---- C6/C7 (멱등·경계) ---------------------------------------------
    def test_c6_repeat_claim_by_the_same_session_is_a_no_op(self):
        """C6. 같은 세션의 반복 클레임은 문서를 다시 쓰지 않는다."""
        path = self.doc(quiet_sec=1200, session="aaaaaaaa")
        self.assertTrue(self.m.stamp_doc_session(DOC, "bbbbbbbb"))
        mtime = os.path.getmtime(path)
        time.sleep(0.01)
        self.assertFalse(self.m.stamp_doc_session(DOC, "bbbbbbbb"))
        self.assertEqual(os.path.getmtime(path), mtime)

    def test_c7_no_stamp_and_empty_session_are_safe(self):
        """C7. 도장 없는 옛 문서·빈 세션에서 아무것도 깨지지 않는다."""
        path = self.doc(quiet_sec=1200, session="")
        self.assertFalse(self.m.stamp_doc_session(DOC, ""))
        before = self.meta_of(path)["updated"]
        self.assertTrue(self.m.stamp_doc_session(DOC, "bbbbbbbb"))
        meta = self.meta_of(path)
        self.assertEqual(meta.get("session"), "bbbbbbbb")
        self.assertEqual(meta["updated"], before)
        self.assertEqual(self.stall(), 20)

    def test_c7b_the_claim_time_is_still_recorded_somewhere(self):
        """C7b. 시계를 안 건드려도 '언제 잡았나'는 남는다 — 바인딩의 claim_at.

        `updated` 를 잃는 대신 클레임 시각이 어디에도 없으면, 그건 정보를
        옮긴 게 아니라 지운 것이다.
        """
        self.doc(quiet_sec=1200, session="aaaaaaaa")
        self.m._claim_req("testbox", "bbbbbbbb", DOC)
        b = self.m.read_binding("testbox", "bbbbbbbb")
        self.assertIn(DOC, b.get("active_reqs") or [])
        self.assertIn(DOC, b.get("claim_at") or {})


if __name__ == "__main__":
    unittest.main()
