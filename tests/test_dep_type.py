"""완료되지 않는 문서는 선행이 될 수 없다 (REQ-20260827-055-62x6).

사용자 지적: "REQ-20260827-045 이 요청은 선행 작업이 있는데 그게 요청이 아니다.
어떻게 이런 일이 있을 수 있지?????? doc 문서를 선행으로 잡고 있으면 어떻게 하나!"

**아무도 안 막았다.** `s9 link --blocked-by` 는 자기 참조·존재 여부·대기 순환은
검사하지만 **"그것이 완료될 수 있는 문서인가"는 안 봤다.** 그래서 무인 워커가
자기가 쓴 지식 문서를 그 요청의 선행으로 걸었고 아무 데서도 걸리지 않았다.

지식 문서의 종착 상태는 `published` 다 — 완료되는 개념이 없다. 그러니 그 요청은
**영원히 안 풀리는 대기**가 된다. 보드에는 "막혀 있다"고 뜨는데 풀 방법이 없다.

막는 것은 **대기(blocked_by)뿐이다.** `relates`·`parent`·`derived_from` 으로
지식과 요청을 잇는 것은 정상이고 오히려 권장된다 — 그쪽은 가리지 않는다.

실행: python3 tests/ dep_type
"""
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class DepType(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9dep-")
        self.env = {**os.environ, "S9_ROOT": self.root, "S9_MACHINE": "testbox",
                    "S9_USER": "alice"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        self.A = self.mk("request", "선행이 될 요청")
        self.B = self.mk("request", "기다리는 요청")
        self.K = self.mk("knowledge", "규칙 문서")
        self.Q = self.mk("question", "질문 문서")

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def mk(self, typ, title):
        extra = ["--goal", "g", "--size", "S"] if typ == "request" else []
        return self.cli("new", typ, "--title", title, "--summary", "s",
                        "--user", "alice", "--body", "x", *extra).split()[0]

    def meta(self, doc_id):
        return self.cli("show", doc_id, "--meta")

    # N1. 요청을 선행으로 거는 것은 지금과 같다
    def test_n1_request_dependency_ok(self):
        self.cli("link", self.B, "--blocked-by", self.A)
        self.assertIn(self.A, self.meta(self.B))

    # B1. 지식은 선행이 될 수 없다 — 완료되는 문서가 아니다
    def test_b1_knowledge_refused(self):
        out = self.cli("link", self.B, "--blocked-by", self.K, expect=1)
        self.assertIn(self.K, out)
        self.assertNotIn(self.K, self.meta(self.B))

    # B2. 질문도 같다 — 완료 개념이 없다
    def test_b2_question_refused(self):
        self.cli("link", self.B, "--blocked-by", self.Q, expect=1)

    # B3. 이미 걸린 것은 전수 검사가 잡는다 — 경계를 막아도 과거는 남는다
    def test_b3_linkcheck_finds_existing(self):
        for dp, _dn, fns in os.walk(os.path.join(self.root, "vault")):
            for fn in fns:
                if fn.startswith(self.B) and fn.endswith(".md"):
                    p = os.path.join(dp, fn)
                    t = open(p, encoding="utf-8").read()
                    t = t.replace("\n---\n",
                                  f'\nblocked_by: ["{self.K}"]\n---\n', 1)
                    open(p, "w", encoding="utf-8").write(t)
        self.cli("index", "rebuild")
        out = self.cli("linkcheck", expect=None)
        self.assertIn(self.K, out, out)

    # F1. 없는 문서·자기 자신은 예전 그대로 거부한다
    def test_f1_existing_guards_kept(self):
        self.cli("link", self.B, "--blocked-by", self.B, expect=1)
        self.cli("link", self.B, "--blocked-by", "REQ-99999999-999", expect=1)

    # R1. relates·parent·derived-from 은 타입을 가리지 않는다
    def test_r1_other_relations_allow_knowledge(self):
        self.cli("link", self.B, "--relates", self.K, "--why", "설계 근거")
        self.assertIn(self.K, self.meta(self.B))
        self.cli("link", self.B, "--derived-from", self.K)


if __name__ == "__main__":
    unittest.main()
