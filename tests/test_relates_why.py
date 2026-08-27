"""연관에는 이유가 남는다 (REQ-20260827-030-62x6).

사용자 지적: "REQ-20260827-013 문서에 연관 문서로 REQ-20260827-029 가 있는데
연관되는게 맞나? 문서 연관관계에 대해서 전부 검사를 한번 하는거 어떻게 생각하나?
근본적으로 해결되고 재발이 안됐으면 좋겠는데 말이지."

그 연관은 리드가 걸었고, 이유는 "둘 다 web/index.html 을 고치니 순서를 나눠야
한다" 였다 — **작업 순서에 관한 사실이지 문서 사이의 관계가 아니다.** 기록할
자리가 없으니 관계 필드로 샜다.

전수를 세어 보니 간선 119개 중 40개는 어느 쪽 본문도 상대를 부르지 않는다.
그런데 그 40개에 제대로 걸린 것과 잘못 걸린 것이 섞여 있다 — 지식 문서와 그
요청처럼, 본문이 서로를 안 불러도 맞는 관계가 있다. 반대로 사용자가 짚은 그
간선은 본문 언급이 있어 어떤 자동 검사에도 안 걸린다.

**기계가 가릴 수 있는 문제가 아니다. 빠진 것은 탐지가 아니라 이유다.** 간선에
남는 것이 상대 id 하나뿐이면, 나중에 누가 봐도 '진짜 관계'와 '그때 사정'을
구별할 수 없다. 그래서 걸 때 한 줄을 받아 문서에 남긴다 — 그러면 전수 검사가
추측이 아니라 읽기가 된다.

parent·derived_from 은 강제하지 않는다. 방향과 뜻이 이름에 이미 있다.

실행: python3 tests/ relates_why
"""
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class RelatesWhy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="s9why-")
        self.env = {**os.environ, "S9_ROOT": self.tmp, "S9_MACHINE": "testbox"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        self.A = self.mk("문서 링크 키보드 접근")
        self.B = self.mk("우선순위 표시가 안 읽힌다")

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def mk(self, title, *extra):
        return self.cli("new", "request", "--title", title, "--summary", "s",
                        "--goal", "g", "--size", "S", "--user", "alice",
                        "--body", "x", *extra).split()[0]

    def meta(self, doc_id):
        for root, _d, files in os.walk(os.path.join(self.tmp, "vault")):
            for fn in files:
                if fn.startswith(doc_id) and fn.endswith(".md"):
                    with open(os.path.join(root, fn), encoding="utf-8") as f:
                        block = f.read().split("\n---\n")[0][4:]
                    out = {}
                    for line in block.splitlines():
                        if ": " not in line:
                            continue
                        k, raw = line.split(": ", 1)
                        try:
                            out[k] = json.loads(raw)
                        except ValueError:
                            out[k] = raw
                    return out
        raise AssertionError(f"문서 없음: {doc_id}")

    # N1. 이유가 양쪽에 남는다 — 관계가 양방향이니 이유도 양방향이다
    def test_n1_why_recorded_both_sides(self):
        self.cli("link", self.A, "--relates", self.B,
                 "--why", "같은 접근성 결함의 다른 자리")
        for a, b in ((self.A, self.B), (self.B, self.A)):
            why = self.meta(a).get("relates_why") or {}
            self.assertEqual(why.get(b), "같은 접근성 결함의 다른 자리",
                             (a, self.meta(a)))

    # N2. 전수 검사가 이유와 함께 낸다 — 있는 것과 없는 것이 갈린다
    def test_n2_audit_lists_reasons(self):
        self.cli("link", self.A, "--relates", self.B, "--why", "같은 결함")
        C = self.mk("이유 없이 걸린 옛 관계")
        self.cli("link", self.A, "--relates", C, "--why", "임시")
        # 옛 문서를 흉내낸다: 이유만 지운다 (지금까지 쌓인 119개의 모양)
        for did in (self.A, C):
            self._strip_why(did, C if did == self.A else self.A)
        out = self.cli("linkcheck", "--relates-audit", expect=None)
        self.assertIn("같은 결함", out)
        self.assertIn("미기재", out)

    def _strip_why(self, doc_id, other):
        for root, _d, files in os.walk(os.path.join(self.tmp, "vault")):
            for fn in files:
                if fn.startswith(doc_id) and fn.endswith(".md"):
                    p = os.path.join(root, fn)
                    with open(p, encoding="utf-8") as f:
                        txt = f.read()
                    meta = self.meta(doc_id)
                    why = {k: v for k, v in (meta.get("relates_why") or {}).items()
                           if k != other}
                    new = (f"relates_why: {json.dumps(why, ensure_ascii=False)}"
                           if why else "")
                    lines = [ln for ln in txt.splitlines()
                             if not ln.startswith("relates_why:")]
                    if new:
                        lines.insert(1, new)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                    return

    # N3. `s9 new --relates` 도 같은 규칙을 탄다 — 입구가 둘이면 규칙도 둘 다에
    def test_n3_new_also_requires_why(self):
        r = subprocess.run(
            [S9, "new", "request", "--title", "t", "--summary", "s",
             "--goal", "g", "--size", "S", "--user", "alice", "--body", "x",
             "--relates", self.A], capture_output=True, text=True,
            env=self.env, timeout=30)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        C = self.mk("이유를 준 새 문서", "--relates", self.A,
                    "--why", "앞 요청에서 갈라져 나온 같은 결함")
        self.assertEqual((self.meta(C).get("relates_why") or {}).get(self.A),
                         "앞 요청에서 갈라져 나온 같은 결함")

    # B1. 거두면 이유도 함께 사라진다 — 양쪽에서
    def test_b1_unrelate_drops_why(self):
        self.cli("link", self.A, "--relates", self.B, "--why", "잘못 건 관계")
        self.cli("link", self.A, "--unrelate", self.B)
        for a in (self.A, self.B):
            self.assertNotIn(self.B if a == self.A else self.A,
                             self.meta(a).get("relates_why") or {})

    # B3. 공백뿐인 이유는 안 준 것과 같다
    def test_b3_blank_why_rejected(self):
        self.cli("link", self.A, "--relates", self.B, "--why", "   ", expect=1)

    # F1. --why 없이 --relates 하면 죽는다
    def test_f1_relates_without_why_dies(self):
        out = self.cli("link", self.A, "--relates", self.B, expect=1)
        self.assertIn("--why", out)

    # R2. parent·derived_from·blocked_by·unrelate 는 --why 를 요구하지 않는다
    def test_r2_other_relations_unaffected(self):
        self.cli("link", self.B, "--parent", self.A)
        self.cli("link", self.B, "--derived-from", self.A)
        self.cli("link", self.B, "--blocked-by", self.A)
        self.assertEqual(self.meta(self.B).get("parent"), self.A)


if __name__ == "__main__":
    unittest.main()
