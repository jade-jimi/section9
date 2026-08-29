"""마우스 없이도 같은 일을 할 수 있는가 (REQ-20260827-007-62x6).

그래프 범례의 종류 항목(.gtype)은 `<span>` 이었다. 보이기는 계기판의 다른
컨트롤과 똑같이 보이는데, Tab 으로 닿지 않고 Enter/Space 로 누를 수도 없다.
마우스가 있어야만 조작되는 컨트롤이다. REQ-20260826-039 의 빈 화면 안내가
"범례의 QUESTION 을 직접 눌러도 된다"고 이 항목을 콕 집어 가리키게 되면서
드러났다.

되돌리는 길 자체는 막혀 있지 않다 — 안내의 주 버튼(.gefix)은 진짜 버튼이라
키보드로 닿는다. 그러니 이건 막힌 것을 뚫는 작업이 아니라 **같은 일을 두 손
중 어느 쪽으로도 할 수 있게** 하는 작업이다.

그 김에 같은 결함의 다른 자리도 훑었다. 보드 카드(.card)는 `tabindex="0"
role="button"` 이라 **Tab 으로 닿기는 하는데** Enter/Space 로는 아무 일도
일어나지 않는다 — 진짜 `<button>` 이 공짜로 주는 것을 흉내 낸 자리에는 손으로
달아 줘야 한다. 닿기만 하고 눌리지 않는 컨트롤은 포커스만 삼키므로 오히려
더 나쁘다.

이 테스트가 지키는 계약은 다섯이다.

  ① 범례 항목은 진짜 <button> 이다 — Tab·Enter·Space 가 따라온다.
  ② 켜짐/꺼짐이 aria-pressed 로도 나온다 (취소선·흐림은 눈에만 보인다).
  ③ 포커스 링이 보인다 — "여기를 켜라"고 짚는 점선 아웃라인(.want)에
     먹히지 않는다. 특이도가 같으면 나중 것이 이기므로 순서까지 본다.
  ④ role="button" 으로 만든 컨트롤은 Enter/Space 로 눌린다.
  ⑤ 범례의 다른 컨트롤(레이아웃 토글)도 여전히 진짜 버튼이다 (회귀 방지).

실행: python3 tests/ legend_keyboard
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


class LegendKeyboard(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    def gtype_markup(self):
        m = re.search(r"GRAPH_TYPES\.map\(t => `(.{0,400}?data-gtype=.{0,400}?)`\)",
                      self.src, re.S)
        self.assertIsNotNone(m, "범례 종류 항목을 그리는 자리를 찾지 못했다")
        return m.group(1)

    # ---------- ① 진짜 버튼 ----------

    def test_legend_type_item_is_a_real_button(self):
        mk = self.gtype_markup()
        self.assertRegex(mk, r"^\s*<button\b",
                         "범례 항목이 <button> 이 아니면 키보드로 닿지 않는다")
        self.assertNotRegex(mk, r"^\s*<span\b", "span 은 포커스를 받지 않는다")
        self.assertIn('type="button"', mk,
                      "폼 안에 들어가도 submit 으로 새지 않게 type 을 밝힌다")

    def test_button_looks_like_the_legend_text_it_replaced(self):
        """버튼의 브라우저 기본 옷(회색 판·보더·글꼴)을 벗겨야 계기판과 같아진다."""
        css = re.search(r"\n\.gtype\{([^}]*)\}", self.src)
        self.assertIsNotNone(css, ".gtype 스타일을 찾지 못했다")
        body = css.group(1)
        for prop in ("background", "border", "font", "color"):
            self.assertIn(prop, body,
                          f"버튼 기본 {prop} 을 벗기지 않으면 범례가 아니라 버튼으로 보인다")

    # ---------- ② 상태는 눈에만 있지 않다 ----------

    def test_on_off_state_is_exposed_not_only_by_strikethrough(self):
        mk = self.gtype_markup()
        self.assertIn("aria-pressed", mk,
                      "켜짐/꺼짐이 취소선·흐림으로만 있으면 눈으로만 읽힌다")
        m = re.search(r'aria-pressed="\$\{([^}]*)\}"', mk)
        self.assertIsNotNone(m, "aria-pressed 값이 실제 상태에서 와야 한다")
        self.assertIn("gtypes.has(t)", m.group(1),
                      "aria-pressed 는 화면이 그리는 켜짐 상태와 같은 출처를 봐야 한다")

    # ---------- ③ 포커스가 보인다 ----------

    def test_focus_ring_survives_the_want_outline(self):
        want = self.src.find(".gtype.want{")
        self.assertGreater(want, 0, ".gtype.want 규칙을 찾지 못했다")
        foc = re.search(r"\.gtype\.want:focus-visible\{([^}]*)\}", self.src)
        self.assertIsNotNone(
            foc, "짚어 준 항목(.want)에 포커스가 가면 점선이 포커스 링을 덮는다 — "
                 "같은 특이도의 규칙으로 명시 복원해야 한다")
        self.assertGreater(foc.start(), want,
                           "특이도가 같으면 나중 규칙이 이긴다 — .want 뒤에 와야 한다")
        self.assertIn("solid", foc.group(1),
                      "포커스는 실선 잉크 링 — 점선(짚기)과 구분돼야 한다")
        base = re.search(r"\.gtype:focus-visible\{([^}]*)\}", self.src)
        self.assertIsNotNone(base, "기본 상태의 포커스 링 규칙이 없다")
        self.assertIn("var(--text)", base.group(1),
                      "포커스 링은 잉크색 — 장식 액센트 색을 새로 들이지 않는다")

    # ---------- ④ 닿기만 하고 안 눌리는 컨트롤 ----------

    def test_role_button_controls_activate_with_enter_and_space(self):
        blocks = re.findall(r'addEventListener\("keydown", (?:e|ev) => \{.{0,900}',
                            self.src, re.S)
        hit = [b for b in blocks if 'role="button"' in b]
        self.assertTrue(hit,
                        'role="button" 로 만든 컨트롤을 Enter/Space 로 누르는 자리가 없다')
        b = hit[0]
        self.assertIn('"Enter"', b, "Enter 로 눌려야 한다")
        self.assertRegex(b, r'"\s"|"Space"|"Spacebar"', "Space 로도 눌려야 한다")
        self.assertIn("preventDefault", b,
                      "Space 를 막지 않으면 페이지가 같이 스크롤된다")
        self.assertRegex(b, r"\.click\(\)",
                         "누른 결과는 클릭과 같은 한 경로로 흘러야 한다")
        self.assertRegex(b, r"input,\s*textarea|textarea|contenteditable",
                         "입력 중인 곳에서는 Enter 를 가로채면 안 된다")

    def test_board_card_is_the_control_that_needed_it(self):
        m = re.search(r'<div class="card"[^`]*?role="button"', self.src)
        self.assertIsNotNone(m, "보드 카드가 role=button 컨트롤이 아니게 되었다면 "
                                "이 테스트의 전제를 다시 봐야 한다")

    # ---------- ⑤ 회귀 방지 ----------

    def test_layout_toggle_is_still_a_real_button(self):
        self.assertRegex(self.src, r'<button class="gmode\$\{',
                         "레이아웃 토글은 계속 진짜 버튼이어야 한다")


if __name__ == "__main__":
    unittest.main()
