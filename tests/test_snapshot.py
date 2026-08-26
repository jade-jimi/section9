"""덮어써도 잃지 않는가 (REQ-20260826-021-62x6).

2026-08-26 하루에 같은 뿌리의 사고가 넷 났다. 전부 **같은 파일에 두 주체가 붙는
것**에서 나왔고, 가장 아픈 하나는 `tests/test_question_type.py` 15건이 커밋 전에
덮여 디스크에서 완전히 사라진 것이다 — git 이력조차 없었다. 마지막 하나는
리드가 냈다: 이미 있는 테스트 파일을 새로 써서 128줄을 덮었다(그건 커밋돼 있어
살았다).

워커 봉투에는 "덮어쓰지 마라 · checkout 쓰지 마라 · 커밋하지 마라"가 이미 적혀
있었다. 그런데도 났다. **규율은 지켜지지 않을 때를 대비하지 못한다.**

그래서 이 장치는 아무의 협조도 요구하지 않는다. 워처가 30초마다 미커밋 파일을
떠 둔다. 누가 무엇으로 덮든 원본은 이미 딴 데 있다.

실행: python3 tests/ snapshot
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class Snapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9snap-")
        subprocess.run(["git", "init", "-q", cls.tmp], check=True)
        subprocess.run(["git", "-C", cls.tmp, "config", "user.email",
                        "t@example.com"], check=True)
        subprocess.run(["git", "-C", cls.tmp, "config", "user.name", "t"],
                       check=True)
        os.environ["S9_ROOT"] = cls.tmp
        spec = importlib.util.spec_from_loader(
            "s9snapmod", importlib.machinery.SourceFileLoader("s9snapmod", S9))
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def write(self, rel, text):
        p = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(p) or self.tmp, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def snaps(self, rel):
        d = os.path.join(self.tmp, "state", "snapshots",
                         self.mod.safe_name(rel))
        try:
            return sorted(os.listdir(d))
        except OSError:
            return []

    def test_s1_overwritten_file_survives(self):
        """S1. 떠 둔 뒤 통째로 덮여도 원본을 되살릴 수 있다.

        이게 이 장치의 존재 이유다 — 커밋 전이라 git 으로는 못 살리는 상황.
        """
        rel = "tests/precious.py"
        self.write(rel, "원본 15건\n")
        self.mod.snapshot_dirty()
        self.write(rel, "남이 덮어쓴 9건\n")      # 사고 재현
        self.assertTrue(self.snaps(rel), "뜬 것이 없다")
        self.mod.cmd_snapshot(type("A", (), {
            "path": None, "restore": rel, "at": None, "now": False})())
        with open(os.path.join(self.tmp, rel), encoding="utf-8") as f:
            self.assertEqual(f.read(), "원본 15건\n")

    def test_s2_restore_does_not_become_another_overwrite(self):
        """S2. 되살리기 직전에 '지금 것'도 뜬다.

        복구가 또 하나의 덮어쓰기가 되면 이 장치가 사고의 원인이 된다.
        """
        rel = "tests/precious.py"
        self.assertTrue(any("남이 덮어쓴" in open(
            os.path.join(self.tmp, "state", "snapshots",
                         self.mod.safe_name(rel), h), encoding="utf-8").read()
            for h in self.snaps(rel)),
            "복구 전에 있던 내용이 어디에도 남지 않았다")

    def test_s3_same_content_is_not_snapped_twice(self):
        """S3. 내용이 그대로면 다시 뜨지 않는다 — 30초마다 도는 루프라
        그러지 않으면 디스크가 같은 파일로 찬다."""
        rel = "tests/stable.py"
        self.write(rel, "변하지 않는다\n")
        self.mod.snapshot_dirty()
        n = len(self.snaps(rel))
        self.mod.snapshot_dirty()
        self.mod.snapshot_dirty()
        self.assertEqual(len(self.snaps(rel)), n)

    def test_s4_state_dir_is_not_snapped(self):
        """S4. state/ 는 뜨지 않는다 — 스냅샷이 자기 자신을 뜨면 끝없이 부푼다."""
        self.write("state/noise.txt", "x")
        self.mod.snapshot_dirty()
        self.assertEqual(self.snaps("state/noise.txt"), [])

    def test_s5_huge_file_is_skipped(self):
        """S5. 소스가 아닌 큰 파일은 건너뛴다 — 이 장치는 코드를 지키는
        것이지 백업이 아니다."""
        self.write("big.bin", "x" * (self.mod.SNAP_MAX_BYTES + 1))
        self.mod.snapshot_dirty()
        self.assertEqual(self.snaps("big.bin"), [])

    def test_s6_watcher_carries_it(self):
        """S6. 워처 루프가 실제로 이걸 부른다 — 사람이 기억해서 치는 명령이면
        오늘 사고 넷 중 하나도 못 막았다."""
        with open(S9, encoding="utf-8") as f:
            src = f.read()
        loop = src.split("def _rework_loop", 1)
        self.assertEqual(len(loop), 2, "워처 루프를 찾지 못했다")
        self.assertIn("snapshot_dirty()", loop[1][:1200],
                      "워처가 스냅샷을 뜨지 않는다")


if __name__ == "__main__":
    unittest.main()
