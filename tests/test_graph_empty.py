"""빈 그래프가 이유를 말하는가 (REQ-20260826-039-62x6).

사용자는 "그래프 탭에 아무것도 보이지 않는다. 새로고침을 하면 보이긴 하던데…"
라고 썼다. 캡처를 보면 렌더가 실패한 게 아니다. 헤더 종류 필터가 `question`
하나로 좁혀 3건만 남겼는데, 그래프 범례에서는 그 `question` 이 꺼져 있었다.
교집합이 0이니 캔버스는 정직하게 아무것도 안 그렸다 — **다만 이유를 말하지
않았다.** 원인을 알려면 사용자가 위쪽 필터와 범례 두 곳을 스스로 대조해야 했다.

새로고침하면 보이는 것도 같은 얘기다: 헤더 필터는 새로고침에 풀리고 범례
설정은 브라우저에 남는다. 그래서 조합이 저절로 풀린다.

그러니 고칠 것은 그리기가 아니라 **빈 화면의 침묵**이다. 이 테스트가 지키는
계약은 넷이다.

  ① 노드가 0일 때만 안내가 뜬다 (그려진 그래프를 덮지 않는다).
  ② 원인별로 말이 다르다 — 문서 자체가 없음 / 필터가 0건으로 좁힘 /
     남은 문서의 종류를 범례에서 꺼 둠. 셋을 한 문장으로 뭉뚱그리면
     사용자는 여전히 어디를 눌러야 할지 모른다.
  ③ 되돌리는 버튼이 같이 있다 — 진짜 <button> 이라 키보드로도 닿는다.
  ④ 문구는 사용자 언어다. 내부 이름(gtypes·catalog·node·GRAPH_TYPES)이
     화면에 새면 설명이 아니라 암호가 된다.

픽셀이 아니라 이 계약만 검사한다. 실제 렌더는 사람의 캡처 확인 몫이다.

실행: python3 tests/ graph_empty
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")

# 화면에 절대 새면 안 되는 내부 이름들
JARGON = ("gtypes", "GRAPH_TYPES", "catalog", "renderGraph", "localStorage",
          "s9gtypes", "TYPE_ORDER", "노드", "필터링", "렌더")


class GraphEmpty(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    # ---------- ① 뜨는 조건 ----------

    def test_empty_notice_only_when_nothing_is_drawn(self):
        """그릴 노드가 하나라도 있으면 안내는 뜨지 않는다."""
        m = re.search(r"const gEmpty = [^;]+;", self.src)
        self.assertIsNotNone(m, "빈 상태 판정을 renderGraph 에서 찾지 못했다")
        self.assertRegex(m.group(0), r"nodes\.length\s*\?\s*null\s*:",
                         "노드가 있으면 null 이어야 한다")

    def test_notice_is_rendered_into_the_canvas_panel(self):
        """안내는 캔버스가 있는 자리에 뜬다 — 옆 레일이 아니라."""
        m = re.search(r'<canvas id="gcanvas">[\s\S]{0,400}?</div>', self.src)
        self.assertIsNotNone(m)
        self.assertIn("graphEmptyHTML(", m.group(0),
                      "빈 화면 안내가 캔버스 자리에 붙어 있어야 한다")

    # ---------- ② 원인별로 다른 말 ----------

    def test_three_causes_get_three_answers(self):
        """세 갈래를 각기 다른 문장으로 답한다."""
        blk = self._state_fn()
        self.assertRegex(blk, r"if \(!catalog\.length\)",
                         "문서 자체가 없는 경우를 먼저 가른다")
        self.assertRegex(blk, r"if \(!rows\.length\)",
                         "필터가 0건으로 좁힌 경우를 가른다")
        self.assertRegex(blk, r"gtypes\.has\(", "범례에서 꺼 둔 종류를 찾는다")
        msgs = re.findall(r'msg:\s*[`"]([^`"]+)', blk)
        self.assertGreaterEqual(len(msgs), 3, "원인별 문장이 셋 이상이어야 한다")
        self.assertEqual(len(msgs), len(set(msgs)), "문장이 서로 달라야 한다")

    def test_hidden_types_are_named_not_counted(self):
        """무엇이 꺼졌는지 이름으로 말한다 — '3건 숨김'만으로는 못 찾는다."""
        blk = self._state_fn()
        self.assertIn("KO", blk, "종류 이름을 한국어로 바꿔 말한다")
        for ko in ("요청", "지식", "질문", "세션"):
            self.assertIn(ko, blk, "%s 이름이 없다" % ko)

    def test_refresh_confusion_is_answered(self):
        """'새로고침하면 보이던데'에 화면이 답한다."""
        blk = self._state_fn()
        self.assertIn("새로고침", blk,
                      "새로고침하면 왜 보이는지 한 줄로 답해야 한다")

    # ---------- ③ 되돌리는 버튼 ----------

    def test_fix_is_a_real_button(self):
        """진짜 <button> 이다 — 키보드로 닿아야 한다."""
        m = re.search(r"<button class=\"gefix\"[^>]*data-gfix=", self.src)
        self.assertIsNotNone(m, "되돌리기 버튼을 찾지 못했다")

    def test_handler_covers_both_fixes(self):
        """필터 지우기와 종류 다시 켜기 둘 다 실제로 동작한다."""
        m = re.search(r'const gf = e\.target\.closest\("\[data-gfix\]"\);'
                      r'[\s\S]*?\n  \}', self.src)
        self.assertIsNotNone(m, "data-gfix 핸들러가 없다")
        h = m.group(0)
        self.assertIn('"filters"', h)
        self.assertIn("#f-type", h, "종류 필터도 지워야 한다")
        self.assertIn("#f-mine", h, "'내 것만'도 필터다 — 안 풀면 버튼이 죽는다")
        self.assertIn("gtypes.add", h, "꺼 둔 종류를 다시 켠다")
        self.assertIn("s9gtypes", h, "다시 켠 상태를 저장한다")
        self.assertIn("render()", h)

    def test_button_carries_which_types_to_restore(self):
        """어떤 종류를 켤지 마크업이 들고 있다 — 핸들러가 다시 계산하지 않는다."""
        self.assertRegex(self.src, r"data-gtypes=")

    # ---------- ④ 문구와 시각 언어 ----------

    def test_copy_has_no_internal_names(self):
        """사용자 문장에 내부 이름이 새지 않는다."""
        blk = self._state_fn()
        for raw in re.findall(r'(?:msg|note|label):\s*[`"]([^`"]+)', blk):
            # 화면에 나가는 것은 값이 채워진 뒤의 글자다 — 자리표시자와 태그는 뺀다
            line = re.sub(r"\$\{[^}]*\}", "", raw)
            line = re.sub(r"<[^>]*>", "", line)
            for j in JARGON:
                self.assertNotIn(j, line, "내부 용어 %r 이 문구에 있다: %s" % (j, line))

    def test_no_color_fill_and_no_side_bar(self):
        """색면 하이라이트·좌측 세로 띠 금지 — 색은 글자로."""
        css = self._css()
        # 잉크 반전(누른 컨트롤)은 이 제품의 인터랙션 언어라 허용 — 금지 대상은
        # 장식용 색면이다. 그래서 --text/--bg 두 잉크만 통과시킨다.
        for bg in re.findall(r"background\s*:\s*([^;}]+)", css):
            self.assertIn(bg.strip(), ("none", "transparent", "var(--text)", "var(--bg)"),
                          "빈 상태에 색면을 깔지 않는다: %s" % bg)
        self.assertNotIn("border-left", css, "좌측 세로 띠 금지")
        # 꺼진 종류는 그 종류 색 글자로 말한다 — 위 범례 칩과 눈으로 이어지게.
        # TCOLOR 는 --t-* 토큰 맵이라 tone 이 바뀌어도 따라온다.
        self.assertIn("TCOLOR[t]", self._state_fn())

    def test_styles_are_token_only_and_theme_agnostic(self):
        """6개 tone 전부에서 성립하려면 색은 토큰으로만 쓴다."""
        css = self._css()
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b", "색 하드코딩 금지")
        self.assertNotRegex(css, r"\[data-(?:skin|theme)=",
                            "특정 스킨/톤 전용 스타일이 아니다")
        self.assertIn("pointer-events", css,
                      "안내는 캔버스 드래그를 가로막지 않는다 — 버튼만 받는다")

    def test_notice_is_announced(self):
        """동적으로 나타나는 안내는 상태 변화로 알린다 (접근성)."""
        m = re.search(r'<div class="gempty"[^>]*>', self.src)
        self.assertIsNotNone(m)
        self.assertIn('role="status"', m.group(0))

    # ---------- helpers ----------

    def _state_fn(self):
        m = re.search(r"function graphEmptyState\(rows\)\{[\s\S]*?\n\}", self.src)
        self.assertIsNotNone(m, "graphEmptyState() 를 찾지 못했다")
        return m.group(0)

    def _css(self):
        m = re.search(r"/\* -+ 그래프 빈 화면[\s\S]*?\*/([\s\S]*?)\n\n", self.src)
        self.assertIsNotNone(m, "빈 상태 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
