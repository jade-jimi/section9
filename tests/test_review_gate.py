"""문서 뷰어 review/blocked 판단 근거 callout (REQ-20260825-006 반려 재작업).

반려 사유: "리뷰나 블럭 판단 근거가 되는 내용, 사용자 판단을 위한 설명이나
선택지가 문서 내부에서 쉽게 확인이 어렵다" — 전이 사유가 본문 최하단 History
한 줄에만 있어 묻힌다. 뷰어가 최근 `-> review|blocked` 전이의 note를 상단
callout(.gate)으로 끌어올리는지, 그 파싱 정규식이 s9가 실제 생성하는 History
라인 형식과 일치하는지(형식 계약)를 검증한다.

격리: S9_ROOT=mktemp. 실행: python3 tests/ review_gate
"""
import glob
import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
INDEX = os.path.join(HERE, "..", "web", "index.html")


class TestReviewGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.html = f.read()

    # --- S1~S3: 뷰어 구현 존재 (단일 파일 JS라 정적 계약으로 검증) ---

    def test_gate_markup_present(self):
        """S1/S2: .gate callout이 review·blocked 두 상태 모두에서 렌더된다."""
        self.assertIn('class="gate', self.html)
        self.assertIn('m.status === "review" || m.status === "blocked"', self.html)
        # 상태별 캡션 — review는 사용자 판단 요청임이 문구로 드러나야 한다
        self.assertIn("확인 요청", self.html)
        self.assertIn("대기 사유", self.html)

    def test_gate_css_ledger_language(self):
        """callout은 계기판 언어를 따른다 — 1px 보더, 라운드/그림자 금지."""
        m = re.search(r"\.gate\{([^}]*)\}", self.html)
        self.assertIsNotNone(m, ".gate CSS 규칙이 없다")
        css = m.group(1)
        self.assertIn("border:1px solid", css)
        self.assertNotIn("border-radius", css)
        self.assertNotIn("box-shadow", css)

    def test_gate_conditional_on_note(self):
        """S3: 전이 note가 없으면 callout을 만들지 않는다 (hit[3] 가드)."""
        self.assertIn("hit && hit[3]", self.html)

    # --- S4: 형식 계약 — JS 정규식이 s9 실제 출력과 일치 ---

    def _gate_re(self, status):
        m = re.search(r'GATE_RE_SRC\s*=\s*"([^"]+)"', self.html)
        self.assertIsNotNone(m, "GATE_RE_SRC 정의가 index.html에 없다")
        # JS 문자열 리터럴 이스케이프(\\S 등)를 실제 패턴으로 복원
        return m.group(1).replace("\\\\", "\\").replace("STATUS", status)

    def test_regex_matches_real_s9_history_line(self):
        tmp = tempfile.mkdtemp(prefix="s9gate-")
        env = {**os.environ, "S9_ROOT": tmp, "S9_MACHINE": "testbox",
               "S9_USER": "tester"}
        env.pop("S9_SESSION", None)

        def cli(*argv):
            r = subprocess.run([S9, *argv], capture_output=True, text=True,
                               env=env, timeout=15, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 0,
                             f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
            return r

        cli("init")
        cli("user", "add", "tester")
        cli("new", "request", "--title", "gate 계약 검증", "--summary", "s",
            "--size", "S", "--body", "b")
        docs = glob.glob(os.path.join(tmp, "vault", "requests", "**", "REQ-*.md"),
                         recursive=True)
        self.assertEqual(len(docs), 1)
        rid = os.path.splitext(os.path.basename(docs[0]))[0]
        cli("status", rid, "in-progress", "--note", "착수")
        note = "확인 포인트: (1) A안 채택 여부 — 예: 201 점프 허용?"
        cli("status", rid, "review", "--note", note)
        with open(docs[0], encoding="utf-8") as f:
            body = f.read()

        pat = re.compile(self._gate_re("review"))
        hit = None
        for ln in body.split("\n"):
            t = pat.match(ln)
            if t:
                hit = t
        self.assertIsNotNone(hit, "-> review 전이 라인이 JS 정규식과 불일치")
        self.assertEqual(hit.group(2), "tester")
        self.assertEqual(hit.group(3), note)
        # 다른 상태 패턴은 이 라인에 걸리지 않아야 한다 (S3의 정적 짝)
        self.assertFalse(any(re.match(self._gate_re("blocked"), ln)
                             for ln in body.split("\n")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
