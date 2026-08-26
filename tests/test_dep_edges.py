"""선행 의존 축 blocked_by (REQ-20260825-097).

계보 3층(parent/derived_from/relates)은 "어디서 왔는가"를 영속 기록한다.
선행 의존은 "지금 무엇을 기다리는가" — 수명이 있는 상태 축이라 별도 필드로
둔다. 진실은 막힌 문서의 blocked_by 하나뿐이고 역방향(blocks)은 저장하지
않는다(파생물은 인덱스에서 재계산).

실행: python3 tests/ dep_edges
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

TMP = tempfile.mkdtemp(prefix="s9dep-")
_prev = {k: os.environ.get(k) for k in ("S9_ROOT", "S9_MACHINE", "S9_USER")}
os.environ.update({"S9_ROOT": TMP, "S9_MACHINE": "testbox", "S9_USER": "tester"})
try:
    spec = importlib.util.spec_from_loader(
        "s9_mod_dep", importlib.machinery.SourceFileLoader("s9_mod_dep", S9))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class TestDepEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = {**os.environ, "S9_ROOT": TMP, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")

    @classmethod
    def cli(cls, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=cls.env, timeout=20, stdin=subprocess.DEVNULL)
        if expect is not None and r.returncode != expect:
            raise AssertionError(f"s9 {' '.join(argv)} rc={r.returncode}: "
                                 f"{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def new(self, title):
        return self.cli("new", "request", "--title", title, "--summary", "s",
                        "--size", "S", "--goal", "g", "--body", "b").split()[0]

    def meta(self, rid):
        import glob
        p = glob.glob(os.path.join(TMP, "vault", "**", rid + ".md"),
                      recursive=True)[0]
        m, _b = mod.read_doc(p)
        return m

    def catalog(self, rid):
        with open(os.path.join(TMP, "index", "catalog.jsonl"),
                  encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["id"] == rid:
                    return row
        raise AssertionError(f"{rid} not in catalog")

    # D1
    def test_d1_link_records_one_side_only(self):
        a, b = self.new("D1 대기"), self.new("D1 선행")
        self.cli("link", a, "--blocked-by", b)
        self.assertEqual(self.meta(a).get("blocked_by"), [b])
        self.assertNotIn("blocks", self.meta(b))
        self.assertEqual(self.meta(b).get("blocked_by", []), [])

    # D2
    def test_d2_reject_missing_and_self(self):
        a = self.new("D2 대기")
        out = self.cli("link", a, "--blocked-by", "REQ-19990101-999", expect=1)
        self.assertEqual(self.meta(a).get("blocked_by", []), [])
        out += self.cli("link", a, "--blocked-by", a, expect=1)
        self.assertEqual(self.meta(a).get("blocked_by", []), [])
        self.assertTrue(out.strip())

    # D3
    def test_d3_reject_cycle(self):
        a, b, c = self.new("D3 A"), self.new("D3 B"), self.new("D3 C")
        self.cli("link", a, "--blocked-by", b)
        self.cli("link", b, "--blocked-by", c)
        self.cli("link", c, "--blocked-by", a, expect=1)
        self.assertEqual(self.meta(c).get("blocked_by", []), [])

    # D4
    def test_d4_blocked_transition_autolinks(self):
        a, b = self.new("D4 대기"), self.new("D4 선행")
        self.cli("status", a, "blocked", "--note", f"{b} 끝나야 착수 가능")
        self.assertEqual(self.meta(a).get("blocked_by"), [b])

    # D5
    def test_d5_done_releases_dependent(self):
        a, b = self.new("D5 대기"), self.new("D5 선행")
        self.cli("link", a, "--blocked-by", b)
        self.cli("status", a, "blocked", "--note", "선행 대기")
        self.cli("status", b, "in-progress")
        self.cli("status", b, "done", "--note", "완료", "--force")
        self.assertEqual(self.meta(a).get("blocked_by", []), [])
        self.assertEqual(self.meta(a)["status"], "in-progress")

    # D6
    def test_d6_partial_release_keeps_blocked(self):
        a = self.new("D6 대기")
        b, c = self.new("D6 선행1"), self.new("D6 선행2")
        self.cli("link", a, "--blocked-by", b, "--blocked-by", c)
        self.cli("status", a, "blocked", "--note", "선행 둘 대기")
        self.cli("status", b, "in-progress")
        self.cli("status", b, "done", "--note", "완료", "--force")
        self.assertEqual(self.meta(a).get("blocked_by"), [c])
        self.assertEqual(self.meta(a)["status"], "blocked")

    # D7
    def test_d7_catalog_and_graph(self):
        a, b = self.new("D7 대기"), self.new("D7 선행")
        self.cli("link", a, "--blocked-by", b)
        self.assertEqual(self.catalog(a).get("blocked_by"), [b])
        edges = mod.dep_edges()
        self.assertIn({"from": a, "to": b, "rel": "blocked_by"}, edges)

    # D8
    def test_d8_linkcheck_detects_and_fixes(self):
        a = self.new("D8 대기")
        import glob
        p = glob.glob(os.path.join(TMP, "vault", "**", a + ".md"),
                      recursive=True)[0]
        m, body = mod.read_doc(p)
        m["blocked_by"] = ["REQ-19990101-998", a]
        mod.write_doc(p, m, body)
        mod.rebuild_index(quiet=True)
        issues, _fixed = mod.link_audit(fix=False)
        self.assertTrue(any("blocked_by" in i and a in i for i in issues), issues)
        mod.link_audit(fix=True)
        self.assertEqual(self.meta(a).get("blocked_by", []), [])
        issues2, fixed2 = mod.link_audit(fix=True)   # 멱등
        self.assertEqual(fixed2, 0, issues2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
