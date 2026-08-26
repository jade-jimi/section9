"""요청 우선순위 가중치 테스트 (REQ-20260826-005).

지시: "요청에 우선 순위 개념을 가중치 형태로 추가하고 진행시 우선순위가 높은
항목 순서로 진행되게 유도해라."

고정하는 결정 네 가지:
1. 척도는 정수 1~99, 기본 50. 별칭(low/normal/high/urgent)은 숫자로 저장된다 —
   매번 숫자를 고르게 하면 실제로는 아무도 안 쓰기 때문에 별칭을 두되,
   저장은 하나의 수치라 정렬 규칙이 단순해진다.
2. 기본이 50 인 이유는 기존 문서를 손대지 않고도 양방향이 살아야 해서다.
   0 이나 100 을 기본으로 두면 한쪽 방향이 죽는다.
3. 동률이면 **오래 기다린 것이 먼저**다. 갱신 순으로 두면 손이 자주 가는
   항목이 계속 앞에 서서 뒤엣것이 굶는다.
4. 잘못된 값은 거부하고 기존 값을 보존한다 — 조용히 기본값으로 되돌리면
   사람이 매긴 우선순위가 소리 없이 사라진다.

격리: S9_ROOT=mktemp. 실행: python3 tests/ priority
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

spec = importlib.util.spec_from_loader(
    "s9_mod_prio", importlib.machinery.SourceFileLoader("s9_mod_prio", S9))
s9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s9)


class Scale(unittest.TestCase):
    def test_aliases_become_numbers(self):
        self.assertEqual(s9.parse_priority("low"), 25)
        self.assertEqual(s9.parse_priority("normal"), 50)
        self.assertEqual(s9.parse_priority("high"), 75)
        self.assertEqual(s9.parse_priority("urgent"), 90)

    def test_numbers_pass_through(self):
        self.assertEqual(s9.parse_priority("1"), 1)
        self.assertEqual(s9.parse_priority(99), 99)

    def test_out_of_range_and_garbage_rejected(self):
        for bad in ("0", "100", "-5", "abc", "", "7.5"):
            with self.assertRaises(ValueError, msg=bad):
                s9.parse_priority(bad)

    def test_missing_field_reads_as_default(self):
        """기존 문서 299건은 이 필드가 없다 — 중간값으로 읽혀야 한다."""
        self.assertEqual(s9.doc_priority({}), s9.PRIORITY_DEFAULT)
        self.assertEqual(s9.doc_priority({"priority": ""}), s9.PRIORITY_DEFAULT)
        self.assertEqual(s9.doc_priority({"priority": 90}), 90)


class WorkOrder(unittest.TestCase):
    def rows(self):
        return [
            {"id": "A", "priority": 50, "created": "2026-08-01"},
            {"id": "B", "priority": 90, "created": "2026-08-20"},
            {"id": "C", "priority": 50, "created": "2026-08-10"},
            {"id": "D", "created": "2026-08-05"},          # 필드 없음 = 50
            {"id": "E", "priority": 25, "created": "2026-08-02"},
        ]

    def test_high_first_then_oldest(self):
        order = [r["id"] for r in s9.work_order(self.rows())]
        self.assertEqual(order, ["B", "A", "D", "C", "E"])

    def test_stable_for_equal_keys(self):
        rows = [{"id": "X", "priority": 50, "created": "2026-08-01"},
                {"id": "Y", "priority": 50, "created": "2026-08-01"}]
        self.assertEqual([r["id"] for r in s9.work_order(rows)], ["X", "Y"])


class Cli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s9prio-")
        cls.env = {**os.environ, "S9_ROOT": cls.root, "S9_MACHINE": "testbox",
                   "S9_USER": "tester", "S9_SYNC": "off"}
        cls.env.pop("S9_SESSION", None)
        cls.s9run("init")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def s9run(cls, *argv, check=True):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=cls.env, timeout=30, stdin=subprocess.DEVNULL)
        if check and r.returncode != 0:
            raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
        return r

    def new(self, title, *extra):
        out = self.s9run("new", "request", "--title", title, "--summary", "s",
                       "--size", "S", "--user", "tester", "--body", "b",
                       *extra).stdout
        return out.split()[0]

    def meta_of(self, rid):
        show = self.s9run("show", rid, "--meta").stdout
        for line in show.splitlines():
            if line.startswith("priority:"):
                return line.split(":", 1)[1].strip()
        return None

    def test_p1_new_accepts_alias_and_number(self):
        self.assertEqual(self.meta_of(self.new("별칭", "--priority", "high")), "75")
        self.assertEqual(self.meta_of(self.new("숫자", "--priority", "90")), "90")

    def test_p2_default_when_unspecified(self):
        self.assertEqual(self.meta_of(self.new("기본값")),
                         str(s9.PRIORITY_DEFAULT))

    def test_p3_set_changes_it(self):
        rid = self.new("변경")
        self.s9run("set", rid, "--priority", "low")
        self.assertEqual(self.meta_of(rid), "25")

    def test_p4_bad_value_rejected_and_old_kept(self):
        rid = self.new("보존", "--priority", "urgent")
        r = self.s9run("set", rid, "--priority", "200", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.meta_of(rid), "90", "거부됐는데 값이 바뀌었다")

    def test_p5_ls_orders_by_weight(self):
        """조회가 곧 작업 순서다 — 높은 것이 위로."""
        lo = self.new("낮음", "--priority", "low")
        hi = self.new("높음", "--priority", "urgent")
        ids = [ln.split()[0] for ln in self.s9run("ls").stdout.splitlines()
               if ln.startswith("REQ-")]
        self.assertLess(ids.index(hi), ids.index(lo))

    def test_p6_ls_always_shows_the_weight(self):
        """기본값도 찍는다 — 처음엔 숨겼다가 반려됐다.

        도입 직후엔 모든 문서가 기본값이라, 기본값을 숨기면 화면에서 아무것도
        안 보인다. 사용자 반려 그대로다: "우선순위 값이 하나도 보이지 않는다.
        숨겨져 있는 건가? 판단할 수 없다." 보이지 않는 축은 없는 축이고,
        값을 매길 계기조차 생기지 않는다.
        """
        plain = self.new("보통")
        loud = self.new("긴급", "--priority", "urgent")
        lines = {ln.split()[0]: ln for ln in self.s9run("ls").stdout.splitlines()
                 if ln.startswith("REQ-")}
        self.assertIn(f"!{s9.PRIORITY_DEFAULT}", lines[plain])
        self.assertIn("!90", lines[loud])

    def test_p7_digest_shows_the_weight(self):
        """digest 는 세션이 무엇부터 집을지 정하는 자리다 — 거기 안 보이면
        순서만 바뀌고 이유는 안 읽힌다."""
        self.new("다이제스트", "--priority", "urgent")
        out = self.s9run("digest").stdout
        self.assertIn("!90", out)


if __name__ == "__main__":
    unittest.main()
