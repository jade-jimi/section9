"""전이가 남거나, 안 남았음이 드러난다 (REQ-20260901-004-62x6).

실사고 2026-09-01. 한 셸 명령에서 REQ-20260831-030 과 -028 의 done 전이가
연달아 돌았다. 출력은 둘 다 `in-progress -> done`, 문서도 그 순간엔 맞았다
(02:05:06). 그런데 아침에 보니 둘 다 in-progress 였고 History 에 그 줄이
없었다. 잠금을 의심할 만한 그림이었지만 잠금은 죄가 없었다 —

  10:21:08  다른 에이전트가 시험을 깨끗한 트리에서 돌려 보려고 `git stash push`
            → 미커밋이던 **그 두 전이가 통째로 stash 로 들어가고** 작업 트리는
            커밋 시점(in-progress)으로 되돌아간다
  10:21:48  `git stash pop` 실패 — 그 20초 사이 훅이 다시 만진 파일 둘이
            "덮어쓰게 된다"며 pop 을 통째로 거부
  10:22:03  `git checkout stash@{0} -- <자기 web/·tests/ 파일들>` — 자기 것만 건짐
  10:22:08  `git stash drop` — 남은 vault/ 변경(전이 둘 + 노트 16건)이 사라짐

유실이 s9 **밖**에서 왔다. 그러니 계약도 두 겹이어야 한다.

  ① **원자 교체** — 쓰기가 도중에 죽어도 문서는 잘리지 않는다. 카탈로그는
     이미 tmp+os.replace 였는데(REQ-20260825-049) 정작 그 원천인 문서 쓰기가
     제자리 truncate 였다. 파생물이 원천보다 튼튼한 거꾸로 선 구조.
  ② **사후 확인** — 전이는 쓴 것을 디스크에서 다시 읽어 확인하고, 없으면
     성공을 말하지 않는다. 출력과 문서가 갈리면 사람은 출력을 믿는다.
  ③ **유실 탐지** — 밖에서 되돌린 것은 막을 수 없으니 드러나게 한다.
     30초마다 뜨는 스냅샷이 이미 독립 사본이라, 맞대 보면 보인다.

실행: python3 tests/ transition_durability
"""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class TransitionDurability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9dur-")
        subprocess.run(["git", "init", "-q", cls.tmp], check=True)
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "-C", cls.tmp, "config", k, v], check=True)
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")
        out = cls.cli("new", "request", "--title", "전이 내구성",
                      "--summary", "s", "--size", "S",
                      "--goal", "전이가 남는다", "--body", "b")
        cls.doc_id = next(w.strip() for w in out.split()
                          if w.strip().startswith("REQ-"))
        # 프로세스 안에서 판정한다 — CLI 왕복은 setUpClass 의 이 몇 번이 전부
        for k, v in cls.env.items():
            os.environ[k] = v
        os.environ.pop("S9_SESSION", None)
        spec = importlib.util.spec_from_loader(
            "s9durmod", importlib.machinery.SourceFileLoader("s9durmod", S9))
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.path = cls.mod.locate(cls.doc_id)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def cli(cls, *argv):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=cls.env, timeout=30, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
        return r.stdout

    def read(self, path=None):
        with open(path or self.path, encoding="utf-8") as f:
            return f.read()

    # ---------- ① 원자 교체 ----------

    def test_d1_a_write_replaces_the_file_instead_of_truncating_it(self):
        """제자리 재작성이면 inode 가 그대로다 — 부분 읽기 창이 열린 채다.

        타이밍에 기대지 않는 결정적 판정(REQ-20260825-049 가 카탈로그에 쓴 것과
        같은 자). 문서는 대시보드가 폴링으로 읽는 파일이기도 하다.
        """
        meta, body = self.mod.read_doc(self.path)
        before = os.stat(self.path).st_ino
        self.mod.write_doc(self.path, meta, body)
        self.assertNotEqual(before, os.stat(self.path).st_ino,
                            "write_doc 이 제자리 재작성이다 — 반쪽 문서가 보일 수 있다")

    def test_d1_b_a_failed_write_leaves_the_original_whole(self):
        """쓰다 죽어도 원본은 통째로 남는다 — 이게 없으면 사고가 곧 소실이다.

        주입 지점은 실물과 같은 자리다: 옛 코드는 `open(path,"w")` 로 **먼저
        비우고** 그 안에서 fm_dump 를 불렀으므로, fm_dump 가 죽으면 남는 것은
        빈 파일이었다. 지금은 내용을 다 만든 뒤에야 임시 파일을 연다.
        """
        original = self.read()
        self.assertIn("## History", original)
        meta, body = self.mod.read_doc(self.path)
        real = self.mod.fm_dump

        def boom(_m):
            raise RuntimeError("디스크가 찼다")

        self.mod.fm_dump = boom
        try:
            with self.assertRaises(RuntimeError):
                self.mod.write_doc(self.path, meta, body)
        finally:
            self.mod.fm_dump = real
        self.assertEqual(self.read(), original,
                         "실패한 쓰기가 원본을 잘랐다")

    def test_d1_c_permissions_survive_the_replace(self):
        """갈아끼운 파일이 0600 이 되면 대시보드·다른 계정이 조용히 못 읽는다."""
        meta, body = self.mod.read_doc(self.path)
        for mode in (0o644, 0o600):
            os.chmod(self.path, mode)
            self.mod.write_doc(self.path, meta, body)
            self.assertEqual(os.stat(self.path).st_mode & 0o777, mode)
        os.chmod(self.path, 0o644)

    def test_d1_d_no_temp_files_are_left_beside_the_document(self):
        """임시 파일이 남으면 그것이 다음 사람의 미스터리가 된다."""
        meta, body = self.mod.read_doc(self.path)
        self.mod.write_doc(self.path, meta, body)
        leftovers = [n for n in os.listdir(os.path.dirname(self.path))
                     if n.startswith(".s9w-")]
        self.assertEqual(leftovers, [])

    # ---------- ② 사후 확인 ----------

    def test_d2_a_a_transition_that_did_not_land_is_not_reported_as_success(self):
        """실사고의 심장: 출력은 성공인데 문서엔 없다.

        쓰기가 통째로 증발하는 상황을 write_doc 무력화로 세운다. 옛 코드는
        조용히 성공을 돌려줬다 — 그 성공을 믿은 사람이 다음 일로 넘어간다.
        """
        before = self.read()
        real = self.mod.write_doc
        self.mod.write_doc = lambda *a, **k: None      # 쓴 척만 한다
        try:
            with self.assertRaises(RuntimeError) as cm:
                self.mod.do_transition(self.doc_id, "in-progress",
                                       note="착수")
        finally:
            self.mod.write_doc = real
        self.assertIn("남지 않았다", str(cm.exception))
        self.assertEqual(self.read(), before, "문서가 건드려졌다")

    def test_d2_b_a_transition_that_did_land_still_succeeds(self):
        """확인이 정상 전이를 막으면 안 된다 — 게이트는 조용해야 쓴다."""
        self.mod.do_transition(self.doc_id, "in-progress", note="착수")
        text = self.read()
        self.assertIn("status: in-progress", text)
        self.assertIn("open -> in-progress", text)

    # ---------- ③ 유실 탐지 ----------

    def test_d3_a_a_reverted_document_is_reported_as_loss(self):
        """실사고 재현 — 전이가 남은 뒤, 밖에서 낡은 사본으로 되돌린다.

        `git stash push` 가 한 일이 정확히 이것이다: 커밋 시점의 내용으로
        파일을 되돌리고, 되돌린 쪽(stash)을 나중에 버린다.
        """
        self.mod.snapshot_dirty()                      # 워처가 뜨는 자리
        landed = self.read()
        self.assertIn("open -> in-progress", landed)
        reverted = "\n".join(
            ln for ln in landed.splitlines()
            if "open -> in-progress" not in ln) + "\n"
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(reverted)                          # 사고: 밖에서 되돌림
        found = self.mod.snapshot_audit()
        mine = [f for f in found if f["path"].endswith(self.doc_id + ".md")]
        self.assertTrue(mine, "되돌려진 문서를 유실로 못 잡았다")
        self.assertTrue(any("open -> in-progress" in m
                            for m in mine[0]["lost"]),
                        f"사라진 History 줄을 못 짚었다: {mine[0]['lost']}")

    def test_d3_b_the_newest_snapshot_being_lossy_does_not_hide_it(self):
        """되돌려진 문서에 뒤늦게 한 줄이 붙으면 그 낡은 내용이 다시 뜬다.

        실사고 10:27 스냅이 그랬다 — 최신 스냅만 보는 탐지기는 그 순간 눈이
        먼다. 보관된 벌수 전부의 합집합과 맞대는 이유.
        """
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("- 2026-09-01T10:27:06+09:00 늦게 붙은 한 줄\n")
        self.mod.snapshot_dirty()                      # 유실본이 최신 스냅이 된다
        found = self.mod.snapshot_audit()
        mine = [f for f in found if f["path"].endswith(self.doc_id + ".md")]
        self.assertTrue(mine, "최신 스냅이 유실본이라고 탐지가 눈멀었다")

    def test_d3_c_a_healthy_vault_reports_nothing(self):
        """거짓 경보를 내면 아무도 안 본다 — 되살리면 조용해져야 한다."""
        d = os.path.join(self.tmp, "state", "snapshots",
                         self.mod.safe_name(
                             os.path.relpath(self.path, self.tmp)))
        newest = sorted(os.listdir(d))[-1]
        with open(self.path, encoding="utf-8") as f:
            live = self.mod._append_only_marks(f.read())
        gone = []
        for snap in sorted(os.listdir(d)):
            with open(os.path.join(d, snap), encoding="utf-8") as f:
                gone += self.mod._marks_lost(
                    self.mod._append_only_marks(f.read()), live)
        with open(self.path, "a", encoding="utf-8") as f:
            for m in sorted(set(gone)):
                f.write(m + "\n")                      # 되살림
        self.assertFalse(
            [f for f in self.mod.snapshot_audit()
             if f["path"].endswith(self.doc_id + ".md")],
            f"살아 있는 문서를 유실로 신고했다 (최신 스냅 {newest})")


    def test_d3_d_a_legitimate_rewrite_is_not_a_loss(self):
        """이름 바꾸기는 유실이 아니다 — 거짓 경보를 내면 탐지기가 죽는다.

        처음 구현은 자국을 **글자로** 맞댔다. 실 vault 에 대 보니 유실 466건이
        나왔는데 전부 거짓이었다: `s9 user` 이름 바꾸기 한 번이 모든 History
        줄의 `(by sjpark1)` 를 `(by nicehugepark)` 로 고쳤을 뿐이었다.
        466건 속에 진짜 하나가 있어도 아무도 못 본다. 그래서 자국의 신원은
        **시각**이다 — 다시쓰기가 건드리지 않고, 줄과 함께 사라지는 부분.
        """
        with open(self.path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("(by tester)", text)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text.replace("(by tester)", "(by 이름바꾼사람)"))
        try:
            self.assertFalse(
                [f for f in self.mod.snapshot_audit()
                 if f["path"].endswith(self.doc_id + ".md")],
                "정당한 다시쓰기를 유실로 신고했다 — 거짓 경보 466건의 뿌리")
        finally:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(text)


if __name__ == "__main__":
    unittest.main()
