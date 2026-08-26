"""터미널이 마크다운 블록을 그리는가 (REQ-20260826-029-62x6).

대시보드 터미널은 어시스턴트 응답을 `ccText()` 로 그린다. 그런데 그 함수의
마크다운 근사는 **줄 안쪽**만 다뤘다 — 코드/굵게/경로/해시. 표와 헤딩은 여러
줄이 모여야 뜻이 생기는 **블록**이라 규칙이 아예 없었고, 그래서 화면에는
`| 문서 | 내용 |` 같은 파이프와 `# 제목` 의 해시가 원문 그대로 흘렀다.
실제 클로드 터미널은 같은 텍스트를 표와 제목으로 그린다.

이 테스트가 지키는 계약은 넷이다.

  ① 표로 볼 조건 — 헤더행 + 구분행(`|---|---|`) + 본문행이 다 있을 때만.
     파이프 하나 들어간 평범한 문장을 표로 만들면 지금보다 나쁘다.
  ② 구분행 판별은 가로줄(`-----`)·목록(`- 항목`)과 겹치지 않는다.
  ③ 블록 변환은 **인라인 규칙이 끝난 뒤, placeholder 복원 전**에 돈다.
     순서가 뒤집히면 코드블록 안의 파이프가 표가 되거나(오탐),
     셀 안의 코드/경로 강조가 사라진다.
  ④ 표/헤딩의 시각 언어는 색면이 아니라 선과 타이포다 — 얼룩말 배경 금지,
     헤어라인 구분선, 숫자는 tabular-nums. 그리고 tone 6종(system/paper/
     carbon/phosphor/mist/graphite) 어디서도 같아야 하므로, 스타일은
     테마 토큰이 아니라 터미널 자체 팔레트(--cc-*)로만 쓴다.

픽셀이 아니라 이 계약만 검사한다. 실제 렌더는 사람의 캡처 확인 몫이다.

실행: python3 tests/ terminal_table
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


def js_regex(src, name):
    """`const NAME = /…/flags;` 에서 정규식 본문을 꺼내 파이썬 re 로 컴파일."""
    m = re.search(r"const %s\s*=\s*/(.+?)/([a-z]*);" % name, src)
    if not m:
        raise AssertionError("%s 정규식을 찾지 못했다" % name)
    body, flags = m.group(1), m.group(2)
    f = re.M if "m" in flags else 0
    return re.compile(body, f)


class TerminalBlocks(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    # ---------- ① 표로 볼 조건 ----------

    def test_delimiter_row_is_recognized(self):
        """`|---|---|` 계열은 전부 구분행으로 읽는다 (정렬 표기 포함)."""
        d = js_regex(self.src, "CCTBL_DELIM")
        for ok in ("|---|---|", "| --- | --- |", "|:---|---:|:--:|",
                   "---|---", "| ---- |", "|:-----------|--------:|"):
            self.assertTrue(d.match(ok), "구분행으로 읽어야 한다: %r" % ok)

    def test_delimiter_row_does_not_eat_rules_or_lists(self):
        """가로줄·목록·평범한 문장을 구분행으로 오해하지 않는다."""
        d = js_regex(self.src, "CCTBL_DELIM")
        for no in ("-----", "- 항목", "--- 구분 ---", "| a | b |",
                   "안녕 | 하세요", "", "  ", "───────"):
            self.assertFalse(d.match(no), "구분행이 아니다: %r" % no)

    def test_table_needs_header_delimiter_and_a_body_row(self):
        """셋이 다 있을 때만 표다 — 코드가 세 줄을 함께 본다."""
        blk = self._table_block()
        self.assertTrue("CCTBL_DELIM" in blk, "구분행 판별을 쓰지 않는다")
        self.assertRegex(
            blk, r"lines\[i \+ 2\]",
            "본문행(i+2)까지 확인해야 한다 — 헤더+구분행만으로 표를 만들지 않는다")
        self.assertRegex(
            blk, r'includes\("\|"\)',
            "헤더행과 본문행에도 파이프가 있어야 한다")

    def test_column_count_must_match(self):
        """헤더와 구분행의 칸 수가 다르면 표가 아니다 (GFM 규칙)."""
        blk = self._table_block()
        self.assertRegex(blk, r"length\s*[!=]==\s*[\w.()\[\] +]*length")

    # ---------- ② 정렬 ----------

    def test_alignment_markers_are_honored(self):
        """`:---:` 가운데, `---:` 오른쪽 — 표기를 받는다."""
        blk = self._table_block()
        self.assertTrue("center" in blk and "right" in blk, "정렬 표기를 받지 않는다")
        self.assertRegex(blk, r'startsWith\(":"\)')
        self.assertRegex(blk, r'endsWith\(":"\)')

    def test_escaped_pipe_stays_a_character(self):
        r"""셀 안의 `\|` 는 칸을 가르지 않는다."""
        c = js_regex(self.src, "CCTBL_CELL")
        self.assertEqual(len(c.split(r"a\|b|c")), 2,
                         r"이스케이프한 \| 로는 쪼개지 않는다")

    # ---------- ③ 변환 순서 ----------

    def test_blocks_run_after_inline_and_before_restore(self):
        """인라인 → 블록 → placeholder 복원. 이 순서가 뒤집히면 오탐이 난다."""
        md = re.search(r"const md = s =>[\s\S]*?\n  \};", self.src)
        self.assertIsNotNone(md, "ccText 의 md() 를 찾지 못했다")
        body = md.group(0)
        inline = body.index("```")            # 코드블록 보호 = 인라인의 첫 규칙
        block = body.index("ccBlocks(")       # 블록 변환
        restore = body.index("\\x00(\\d+)\\x00")
        self.assertLess(inline, block, "인라인 규칙이 먼저다")
        self.assertLess(block, restore, "placeholder 복원은 마지막이다")

    def test_fenced_code_keeps_its_pipes(self):
        """코드블록은 placeholder 로 먼저 빠지므로 그 안의 표는 표가 아니다."""
        blk = self._table_block()
        self.assertTrue("```" not in blk,
                        "블록 변환은 코드블록을 다시 건드리지 않는다")

    # ---------- ④ 헤딩 ----------

    def test_heading_takes_hash_plus_space_only(self):
        """`# 제목` 은 헤딩, `#제목`·`#######` 은 아니다."""
        h = js_regex(self.src, "CCHEAD")
        self.assertTrue(h.match("# 제목"))
        self.assertTrue(h.match("### 소제목"))
        self.assertTrue(h.match("  ## 들여쓴 제목"))
        self.assertFalse(h.match("#제목"))
        self.assertFalse(h.match("####### 일곱개"))
        self.assertFalse(h.match("코드 # 주석"))
        self.assertFalse(h.match("#"))

    def test_heading_level_becomes_a_class(self):
        """레벨은 클래스로 나간다 — 크기·굵기 위계를 CSS 가 준다."""
        self.assertRegex(self.src, r'class="cch cch\$\{')
        for lv in (1, 2, 3):
            self.assertRegex(self.src, r"\.cch%d\b" % lv,
                             "cch%d 스타일이 없다" % lv)

    # ---------- ⑤ 시각 언어 ----------

    def test_table_markup_is_a_real_table(self):
        """`<table>` 로 그린다 — 파이프를 흉내 낸 span 배열이 아니라."""
        blk = self._table_block()
        self.assertIn('<table class="cctbl">', blk)
        self.assertIn("<thead>", blk)
        self.assertIn("<tbody>", blk)

    def test_no_zebra_or_color_fill(self):
        """얼룩말 배경·색면 하이라이트 금지 — 구분은 선과 타이포로."""
        css = self._table_css()
        self.assertNotIn("nth-child", css, "줄무늬 배경을 쓰지 않는다")
        self.assertNotRegex(
            css, r"background\s*:\s*(?!none)(?!transparent)[^;}]+",
            "표에는 배경 색면을 깔지 않는다")

    def test_hairline_and_tabular_numbers(self):
        """헤어라인 구분선 + 숫자 열은 tabular-nums."""
        css = self._table_css()
        self.assertIn("border-collapse:collapse", css)
        self.assertIn("tabular-nums", css)
        self.assertIn("white-space:normal", css,
                      "셀은 pre-wrap 을 물려받지 않고 정상 줄바꿈한다")

    def test_styles_survive_every_tone(self):
        """터미널은 tone 무관 상시 다크 — 표도 --cc-* 팔레트로만 쓴다.

        스트림 터미널(.term)에는 --cc-* 가 정의돼 있지 않으므로 fallback 을
        반드시 붙인다. 안 붙이면 문서 안 스트림에서 선이 통째로 사라진다.
        """
        css = self._table_css()
        for token in re.findall(r"var\((--[\w-]+)([^)]*)\)", css):
            name, rest = token
            self.assertTrue(name.startswith("--cc-"),
                            "테마 토큰 %s 은 터미널에서 쓰지 않는다" % name)
            self.assertTrue(rest.strip().startswith(","),
                            "%s 에 fallback 이 없다 — .term 에서 사라진다" % name)
        self.assertNotRegex(css, r"\[data-(?:skin|theme)=",
                            "특정 스킨/톤에만 다는 스타일이 아니다")

    # ---------- helpers ----------

    def _table_block(self):
        m = re.search(r"function ccBlocks\(re[\s\S]*?\n\}", self.src)
        if m is None:
            m = re.search(r"function ccBlocks\([\s\S]*?\n\}\n", self.src)
        self.assertIsNotNone(m, "ccBlocks() 를 찾지 못했다")
        return m.group(0)

    def _table_css(self):
        m = re.search(r"/\* -+ 터미널 블록 마크다운[\s\S]*?\*/([\s\S]*?)\n\n", self.src)
        self.assertIsNotNone(m, "표/헤딩 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
