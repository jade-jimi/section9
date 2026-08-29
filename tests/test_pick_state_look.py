"""집힌 카드는 **집혔다고** 말한다 — 얹힌 척하지 않는다 (REQ-20260829-011).

사용자: "카드 테두리와 경과시간, 이어 말하기 위치가 고정이 되어 원래대로
돌아오지 않는 경우가 있다."

`?pick=` 로 그 화면을 그대로 세워 보고 원인을 잡았다. **멈춘 hover 가 아니다.**
`이어 말하기` 로 집어 둔 카드(docTarget)의 모습이다. 셋이 한꺼번에 걸린다 —
잉크 테두리(.card.picked), 늘 떠 있는 손잡이, 그리고 그 손잡이가 밀어낸
경과시각. 그 세 가지가 정확히 사용자가 "고정됐다"고 말한 셋이다.

왜 hover 로 읽히나: 집힘의 손잡이 규칙이 hover 의 규칙과 **글자 그대로 같았다**
(`color:var(--text); text-decoration:underline`). 지속 상태를 찰나 상태의
재료로 그리면, 사람은 마우스를 치웠는데도 안 풀리는 화면으로 읽는다.

그래서 셋을 가른다.

  ① 집힘은 **낱말**로 말한다. 테두리 하나는 모양일 뿐이라 무슨 상태인지
     말하지 못한다 — id 줄에 잉크 낱말 한 마디를 세운다(색면 아님).
  ② 집혔다고 **데이터가 사라지지 않는다.** 경과시각은 카드가 늘 지고 있는
     사실이고, 문서 하나를 집어 둔 내내 그 사실이 없어질 이유가 없다.
  ③ 손잡이는 여전히 **얹거나 포커스했을 때만** 뜬다. 집힘이 손잡이를 붙들지
     않는다 — 붙들면 손잡이와 시각이 그 모서리를 놓고 영영 다툰다.

모서리 한 칸을 손잡이와 시각이 나눠 쓰는 것 자체는 남긴다. 실측했더니 세
가지가 한 줄에 설 자리가 없다(id 97 + 손잡이 56 + 시각 57 ≈ 226px > 카드 줄
199px). 나눌 수 있는 축은 픽셀이 아니라 **시간**이다: 찰나(포인터가 그 카드에
있는 동안)의 교대는 괜찮고, 지속 상태의 점유는 안 된다. 키보드 포커스도
사용자가 스스로 옮기는 찰나라 같은 규칙을 쓴다.

실행: python3 tests/ pick_state_look
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


def rules_for(src, needle):
    """셀렉터에 needle 이 들어간 CSS 규칙 (셀렉터, 본문) 전부."""
    out = []
    for m in re.finditer(r"(?m)^([^\n{}]*\{)", src):
        pass
    for m in re.finditer(r"(?m)^([^\n{}]+)\{([^{}]*)\}", src):
        if needle in m.group(1):
            out.append((m.group(1).strip(), m.group(2)))
    return out


class PickStateLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    # --- ① 집힘은 낱말로 말한다 ---

    def test_picked_says_it_in_words(self):
        """테두리는 모양일 뿐이다 — 무슨 상태인지는 낱말이 말한다."""
        self.assertIn('class="pkst"', self.src,
                      "집힘을 말하는 낱말이 카드에 없다 — 테두리만으로는 무슨 상태인지 모른다")
        shown = [css for sel, css in rules_for(self.src, ".picked .pkst")]
        self.assertTrue(shown, ".card.picked 에서 그 낱말을 켜는 규칙이 없다")
        hidden = [css for sel, css in rules_for(self.src, ".pkst")
                  if ".picked" not in sel and ":hover" not in sel]
        self.assertTrue(any("display:none" in c.replace(" ", "") for c in hidden),
                        "집지 않은 카드에도 그 낱말이 붙어 있다")

    def test_the_word_is_ink_not_a_filled_chip(self):
        """색은 면이 아니라 글자로 — 칠한 알약 금지."""
        for sel, css in rules_for(self.src, ".pkst"):
            flat = css.replace(" ", "")
            self.assertNotRegex(flat, r"background:(?!none)",
                                "집힘 표시를 색면으로 그렸다: " + sel)
            self.assertNotIn("border-radius:999px", flat, "알약으로 그렸다: " + sel)

    def test_the_word_shares_the_row_instead_of_the_corner(self):
        """낱말은 id 줄 안에 선다 — 모서리에 세우면 경과시각과 겹친다."""
        m = re.search(r'<div class="id">(.+?)</div>', self.src)
        self.assertIsNotNone(m, "카드 id 줄을 찾지 못했다")
        self.assertIn('class="pkst"', m.group(1),
                      "집힘 낱말이 id 줄 밖에 있다 — 모서리는 이미 시각이 쓴다")
        for sel, css in rules_for(self.src, ".pkst"):
            self.assertNotIn("position:absolute", css.replace(" ", ""),
                             "낱말을 모서리에 띄웠다: " + sel)

    def test_the_identifier_never_breaks_across_lines(self):
        """자리를 비워 준 대가로 **식별자가 쪼개지면** 안 된다.

        시각의 칸을 비우려고 id 줄에 padding 을 줬더니, 좁은 열에서 평범한
        카드까지 `REQ-20260829-` / `010` 으로 두 줄이 됐다(glass @1000px 실측).
        식별자는 한 덩어리다 — 줄을 넘겨야 한다면 넘어가는 것은 집힘 낱말이다.
        그래서 id 줄은 flex 로 세우고, 식별자만 nowrap 으로 묶는다."""
        m = re.search(r'<div class="id">(.+?)</div>', self.src)
        self.assertIsNotNone(m)
        self.assertIn('class="idn"', m.group(1),
                      "식별자가 제 이름의 덩어리로 싸여 있지 않다 — 아무 데서나 끊긴다")
        idn = [css for sel, css in rules_for(self.src, ".idn")]
        self.assertTrue(any("white-space:nowrap" in c.replace(" ", "") for c in idn),
                        "식별자가 줄을 넘어 쪼개질 수 있다")
        row = [css for sel, css in rules_for(self.src, ".card .id")]
        self.assertTrue(any("flex-wrap:wrap" in c.replace(" ", "") for c in row),
                        "id 줄이 넘칠 때 낱말이 아래로 내려갈 길이 없다")

    # --- ② 집혔다고 데이터가 사라지지 않는다 ---

    def test_picked_does_not_hide_the_clock(self):
        """경과시각은 카드가 늘 지고 있는 사실이다 — 집었다고 없어지지 않는다.

        셀렉터 목록을 쉼표로 갈라 **한 갈래씩** 본다: `.card:hover .elapsed,
        .card.picked .elapsed{visibility:hidden}` 처럼 찰나와 지속을 한 규칙에
        묶어 두면 "hover 규칙이니 괜찮다"로 넘어가 버린다 — 실제로 그렇게
        묶여 있었다."""
        for sel, css in rules_for(self.src, ".elapsed"):
            if "visibility:hidden" not in css.replace(" ", ""):
                continue
            for part in sel.split(","):
                if ".picked" in part:
                    self.fail("집힌 카드가 경과시각을 지운다: " + part.strip())

    def test_the_clock_still_steps_aside_while_the_pointer_is_there(self):
        """찰나의 교대는 남긴다 — 셋이 한 줄에 설 자리가 없다(실측 226px > 199px)."""
        hit = [part for sel, css in rules_for(self.src, ".elapsed")
               if "visibility:hidden" in css.replace(" ", "")
               for part in sel.split(",") if ":hover" in part]
        self.assertTrue(hit, "얹었을 때 시각이 손잡이에게 자리를 비키는 규칙이 사라졌다")

    # --- ③ 집힘이 손잡이를 붙들지 않는다 ---

    def test_picked_does_not_pin_the_handle_open(self):
        """손잡이는 얹거나 포커스했을 때만 뜬다 — 집힘은 손잡이를 붙들지 않는다."""
        for sel, css in rules_for(self.src, ".pickdoc"):
            if "display:block" not in css.replace(" ", ""):
                continue
            for part in sel.split(","):
                if ".picked" in part and ":hover" not in part and ":focus" not in part:
                    self.fail("집힌 카드가 손잡이를 상시로 붙들고 있다: " + part.strip())

    def test_picked_does_not_borrow_the_hover_mark(self):
        """밑줄은 '지금 누를 수 있다'는 hover 의 말이다 — 지속 상태가 빌려 쓰면
        마우스를 치웠는데도 안 풀린 화면으로 읽힌다."""
        for sel, css in rules_for(self.src, ".pickdoc"):
            if "text-decoration:underline" not in css.replace(" ", ""):
                continue
            for part in sel.split(","):
                if ".picked" in part and ":hover" not in part and ":focus" not in part:
                    self.fail("집힘이 hover 의 밑줄을 쓰고 있다: " + part.strip())

    def test_picked_does_not_wear_a_border_either(self):
        """**테두리도 찰나의 재료다** (REQ-20260829-011 2차 반려).

        사용자: "여전히 선택한 후에 카드의 테두리가 진하게 표시되고 있는 중이다."

        1차에서 손잡이의 밑줄·잉크는 걷어냈지만 테두리는 남겨 뒀다. 그런데 이
        화면에서 실선 잉크 테두리는 **키보드 포커스**의 말이고(카드·목록 행·
        버튼·스크롤 상자가 전부 그것으로 "지금 여기 있습니다"를 말한다), 점선은
        **드롭 자리**의 말이다(.col.dropok). 지속 상태가 그 재료를 빌리면
        1차에서 고친 것과 똑같은 잘못이다 — 포커스를 옮겨도 안 풀리는 포커스로
        읽힌다. 집힘은 낱말로만 말한다.

        키보드 포커스 표시(.card:focus-visible)는 접근성이라 그대로 둔다."""
        for sel, css in rules_for(self.src, ".card.picked"):
            if ":focus" in sel:
                continue
            flat = css.replace(" ", "")
            for prop in ("outline:", "border:", "box-shadow:"):
                self.assertNotIn(prop, flat,
                                 "집힘을 테두리로 그렸다: " + sel)

    def test_keyboard_focus_still_shows(self):
        """포커스 링은 접근성이다 — 집힘을 걷어내면서 함께 지우면 안 된다."""
        hit = [css for sel, css in rules_for(self.src, ".card:focus-visible")
               if "outline:" in css]
        self.assertTrue(hit, "카드의 키보드 포커스 링이 사라졌다")

    def test_the_word_is_loud_enough_to_find(self):
        """테두리를 걷어냈으니 낱말 혼자 열 장 중에서 눈에 걸려야 한다 —
        id 줄은 카드에서 가장 작고 흐린 줄이라, 거기 얹은 두 글자가 주변
        글자와 같은 크기·굵기면 스캔에 안 걸린다."""
        rules = dict(rules_for(self.src, ".pkst"))
        base = [c for s2, c in rules.items() if s2.endswith(".pkst")]
        self.assertTrue(base, ".pkst 규칙이 없다")
        flat = base[0].replace(" ", "")
        self.assertIn("font-weight:700", flat, "낱말이 주변 글자만큼 흐리다")
        self.assertRegex(flat, r"font-size:1[12](\.\d+)?px",
                         "낱말이 id 줄(10px)과 같은 크기라 눈에 걸리지 않는다")


if __name__ == "__main__":
    unittest.main()
