"""문서 본문의 마크다운 표 (REQ-20260827-008-62x6).

사용자: "QST-20260827-001 문서 본문에 표가 깨져서 나온다. 모든 문서에서 md 표가
깨지지 않도록 md 문법 잘 챙겨줘."

원인은 문서 뷰어의 렌더러(`md2html`)에 **표 갈래가 아예 없다**는 것이었다. 줄
단위로 코드펜스·헤딩·목록·문단만 가르므로 `| a | b |` 는 문단에 떨어져 파이프째
화면에 나왔다.

**이 결함의 진짜 이름은 "렌더러가 두 벌"이다.** REQ-20260826-029 에서 터미널
뷰(`ccText`→`ccBlocks`)에 같은 구멍을 막았는데, 문서 뷰어는 별개의 렌더러라
그대로 남았다. 같은 규칙이 두 자리에 갈리면 한쪽만 고쳐진다 — 이 프로젝트가
2026-08-26 하루에만 세 번 밟은 실패다(data-goto 의 두 뜻 · 질문 판정자의 두
입구 · 그리고 이 렌더러 두 벌).

그래서 이 테스트의 첫 계약은 "표가 보이는가"가 아니라 **"표 규칙이 한 곳에만
있는가"** 다. 두 번째 파서를 쓰는 순간 다음 사람이 또 한쪽만 고친다.

  ① 표를 읽는 규칙은 한 함수(`mdTable`)에만 있다. 구분행 판별도 칸 나누기도
     그 밖에서 다시 쓰이지 않는다.
  ② 문서 뷰어와 터미널 뷰가 **그 하나를** 부른다.
  ③ 문서 뷰어에서 표 갈래는 문단 갈래보다 **먼저** 온다. 뒤면 파이프 줄이
     문단에 먹혀 원래 결함으로 되돌아간다.
  ④ 코드펜스 안의 파이프는 표가 되지 않는다.
  ⑤ 셀 안의 강조(인라인 코드·문서 id 링크·첨부)가 산다. 오늘 노트들의 표가
     정확히 그런 내용이다 — 셀이 죽으면 표는 됐는데 알맹이가 사라진다.
  ⑥ 문서 뷰어의 표는 **터미널 팔레트(--cc-*)를 쓰지 않는다.** 그 토큰은 문서
     뷰어에 없어서 어두운 fallback 으로 떨어지고, 밝은 tone 에서 글자가 배경에
     묻힌다. 029 가 터미널에 fallback 을 붙인 이유가 여기서는 반대로 작동한다.

픽셀은 단위 테스트가 볼 수 없다. 실제 렌더는 사람의 캡처 확인 몫이다.

실행: python3 tests/ doc_table
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


class DocTable(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    # ---------- ① 규칙은 한 곳에만 ----------

    def test_one_table_parser_exists(self):
        """표를 짓는 함수는 하나다."""
        self.assertIsNotNone(self._fn_opt("mdTable"),
                             "공용 표 파서 mdTable() 이 없다")

    def test_table_rules_are_used_nowhere_else(self):
        """구분행 판별과 칸 나누기가 파서 밖에서 다시 쓰이면 두 벌이 된다."""
        tbl = self._fn("mdTable")
        # 정의 자체는 세지 않는다 — 호출만 본다
        for rule, why in ((r"CCTBL_DELIM\.test\(", "구분행 판별"),
                          (r"(?<!function )ccCells\(", "칸 나누기")):
            total = len(re.findall(rule, self.src))
            inside = len(re.findall(rule, tbl))
            self.assertEqual(total, inside,
                             "%s 이 mdTable 밖에서도 쓰인다 — 규칙이 두 벌이다"
                             % why)

    def test_only_one_place_builds_a_markdown_table(self):
        """마크다운 표의 마크업을 짓는 자리가 둘이면 한쪽만 고쳐진다.

        감사 로그·메타 표 같은 정적 표는 무관하다 — 두 화면이 공유해야 하는
        것은 **마크다운을 표로 바꾸는** 그 마크업 하나다. 스타일 계열만 인자로
        갈리고 구조는 한 벌이어야 한다."""
        self.assertEqual(len(re.findall(r'<table class="\$\{cls\}"', self.src)), 1,
                         "마크다운 표 마크업을 짓는 자리가 하나가 아니다")
        for lit in ("cctblw", "mdtblw"):
            self.assertNotIn('"%s"' % lit, self.src,
                             "%s 를 직접 박은 자리가 있다 — 구조가 갈렸다" % lit)

    # ---------- ② 두 렌더러가 같은 하나를 부른다 ----------

    def test_document_viewer_calls_the_shared_parser(self):
        """문서 뷰어가 표를 그리려면 그 하나를 불러야 한다."""
        self.assertRegex(self._fn("md2html"), r"mdTable\(",
                         "문서 뷰어가 공용 표 파서를 부르지 않는다")

    def test_terminal_view_calls_the_shared_parser(self):
        """터미널 뷰도 같은 하나를 부른다 — 자기 복사본을 들고 있으면 안 된다."""
        self.assertRegex(self._fn("ccBlocks"), r"mdTable\(",
                         "터미널 뷰가 공용 표 파서를 부르지 않는다")

    # ---------- ③④ 순서 ----------

    def test_table_branch_comes_before_the_paragraph_fallback(self):
        """문단 갈래가 먼저면 파이프 줄이 문단에 먹혀 원래 결함으로 돌아간다."""
        body = self._fn("md2html")
        t = body.find("mdTable(")
        p = body.find("para.push(")
        self.assertGreater(t, -1, "표 갈래가 없다")
        self.assertGreater(p, -1, "문단 갈래를 찾지 못했다")
        self.assertLess(t, p, "표 갈래가 문단 갈래보다 뒤에 있다")

    def test_fenced_code_keeps_its_pipes(self):
        """코드블록 안의 파이프는 표가 아니다 — 코드 갈래가 먼저 와야 한다."""
        body = self._fn("md2html")
        c = body.find("if (inCode)")
        t = body.find("mdTable(")
        self.assertGreater(c, -1, "코드블록 갈래를 찾지 못했다")
        self.assertLess(c, t, "코드블록 갈래보다 표 갈래가 먼저면 오탐이 난다")

    # ---------- ⑤ 셀 알맹이 ----------

    def test_cells_go_through_inline_rules(self):
        """셀 안의 인라인 코드·문서 id·첨부가 살아야 한다. 표는 됐는데 알맹이가
        사라지면 고친 것이 아니다."""
        body = self._fn("md2html")
        m = re.search(r"mdTable\([^)]*\)", body)
        self.assertIsNotNone(m)
        self.assertIn("inline", m.group(0),
                      "셀을 인라인 규칙에 통과시키지 않으면 강조가 죽는다")

    def test_parser_takes_a_cell_renderer(self):
        """두 렌더러가 셀을 다르게 만든다(한쪽은 이미 HTML, 한쪽은 원문) —
        그 차이를 인자로 받아야 파서를 한 벌로 유지할 수 있다."""
        sig = re.search(r"function mdTable\(([^)]*)\)", self.src)
        self.assertIsNotNone(sig, "mdTable 시그니처를 찾지 못했다")
        self.assertGreaterEqual(len(sig.group(1).split(",")), 3,
                                "셀 렌더러를 받지 않으면 두 벌로 갈라진다")

    def test_escaped_pipe_stays_a_character(self):
        r"""셀 안의 `\|` 는 칸 구분이 아니라 글자다."""
        self.assertIn(r"\\|", self._fn("ccCells"),
                      "이스케이프한 파이프를 되돌리지 않는다")

    # ---------- ⑥ 문서 뷰어의 색 ----------

    def test_document_table_does_not_borrow_terminal_palette(self):
        """--cc-* 는 문서 뷰어에 없다 — 쓰면 어두운 fallback 으로 떨어져
        밝은 tone 에서 글자가 배경에 묻힌다."""
        css = self._css()
        self.assertNotIn("--cc-", css,
                         "문서 뷰어 표가 터미널 팔레트를 빌려 쓴다")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b", "색 하드코딩 금지")

    def test_document_table_is_lines_not_fills(self):
        """색면 얼룩말 금지 — 구획은 헤어라인으로."""
        css = self._css()
        self.assertNotRegex(css, r"nth-child\(", "얼룩말 배경 금지")
        for bg in re.findall(r"background\s*:\s*([^;}]+)", css):
            self.assertIn(bg.strip(), ("none", "transparent"),
                          "표에 색면을 깔지 않는다: %s" % bg)
        self.assertIn("1px solid var(--hairline)", css,
                      "행 구분은 헤어라인으로")

    def test_wide_table_scrolls_inside_itself(self):
        """넓은 표가 뷰어를 가로로 밀면 본문 전체가 흔들린다."""
        css = self._css()
        self.assertIn("overflow-x:auto", css.replace(" ", ""),
                      "표는 자기 안에서 가로 스크롤해야 한다")

    def test_numbers_line_up(self):
        """숫자 열은 자릿수가 세로로 맞아야 비교가 된다."""
        self.assertIn("tabular-nums", self._css())

    def test_table_is_a_real_table(self):
        """진짜 <table> 이라야 스크린리더와 복사가 산다."""
        tbl = self._fn("mdTable")
        for tag in ("<table", "<thead", "<tbody", 'ccCell("th"', 'ccCell("td"'):
            self.assertIn(tag, tbl, "%s 가 없다" % tag)

    # ---------- helpers ----------

    def _fn(self, name):
        m = self._fn_opt(name)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m

    def _fn_opt(self, name):
        m = re.search(r"(?:async )?function %s\([^)]*\)\{[\s\S]*?\n\}" % name,
                      self.src)
        return m.group(0) if m else None

    def _css(self):
        m = re.search(r"/\* ── 문서 본문 표[\s\S]*?\*/([\s\S]*?)\n\n", self.src)
        self.assertIsNotNone(m, "문서 본문 표 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
