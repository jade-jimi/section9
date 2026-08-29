"""카드는 확인 포인트를 **얼마나** 내주는가 (REQ-20260829-009).

사용자: "확인 메시지가 너무 기니까 잘린다. 잘리는게 맞나? 그리고 이렇게까지
길게 보여주는게 맞을까? 너무 길면 결국 가독성이 떨어져서 본문으로 들어가서
보게 되는데 말이야."

판정한 것:

① **잘리는 게 맞다.** 보드 열에서 사람이 내리는 결정은 "어느 건을 지금 볼
   것인가"이지 판정 자체가 아니다. 폭 210~250px 짜리 열에 스무 줄 문단을
   넣는 것은 읽으라고 준 것이 아니라 있다고 보여준 것이다 — 사용자가 본문으로
   들어가 읽게 되는 것이 그 증거다. 전문을 펴는 자리는 문서 뷰어의 확인 요청
   callout(.gate)이고, 거기엔 갈래 분리·문서 링크·첨부 그림이 이미 다 있다.
② 그래서 카드 몫은 **세 줄**이다. 배경 줄(무엇을) 2줄 + 확인 요청 3줄 =
   판정 블록 다섯 줄 상한. 카드 높이에 천장이 생겨야 열의 리듬이 서고,
   승인·반려 버튼이 긴 글에 밀려 화면 밖으로 나가지 않는다.
③ 잘렸다는 사실은 **카드가 직접 말한다** — 잘렸을 때만 뜨는 한 줄 손잡이.
   말줄임표는 "끊겼다"만 말하고 "나머지가 어디 있는지"는 말하지 않는다.

   그 손잡이가 **Docs 로 보내던 것**은 반려됐다. 사용자: "전문 보기 기능은
   의미 없다. 그냥 카드를 클릭하면 전문이 있는 문서로 가는데 굳이?? 전문 보기를
   눌러서 보드탭의 카드에서 전문을 다 보이는거면 모를까, docs 탭으로 이동이
   되는 전문 보기는 쓸데없는 기능같다." 맞는 말이다 — 카드 전체가 이미 그
   목적지의 손잡이라, 같은 자리에 같은 목적지가 둘이면 하나는 없느니만 못하다.
   그래서 손잡이는 **카드 안에서 그 자리에 편다.**

   펴되 셋을 지킨다. ⓐ **눌러서 열고 눌러서 닫는다** — 스치기만 해도 열리던
   호버 전개로 돌아가지 않는다(그게 애초의 결함이었다). ⓑ **펼친 글은 자기
   상자 안에서 스크롤한다** — 카드 높이에 천장이 있어야 열의 리듬이 서고
   승인·반려 버튼이 카드 밖으로 밀려나지 않는다. ⓒ **펼 것이 없으면 손잡이도
   없다.**
④ **호버로 펼치지 않는다.** 마우스를 얹으면 클램프를 풀던 규칙(calm)이
   사용자가 신고한 바로 그 화면을 만든다: 스무 줄이 카드 안으로 돌아오고,
   아래 카드들이 통째로 밀리고, 마우스를 떼면 읽던 글이 사라진다.
⑤ 클램프는 **모든 스킨에서** 성립한다. 지금은 calm 한 벌에만 있어 ledger·
   glass·terminal 에서는 문단이 통째로 실린다.

픽셀이 아니라 이 구조 계약만 검사한다 (단일 파일 JS라 정적 계약으로 검증).

실행: python3 tests/ review_clamp
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


def _rules(src, needle):
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"(?m)^([^\n{}]+)\{([^{}]*)\}", src)
            if needle in m.group(1)]


def css_rule(src, selector):
    """스킨 블록이 아닌 **베이스** 규칙 본문을 돌려준다 (없으면 None)."""
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", src)
    return m.group(1) if m else None


class ReviewClamp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r"function cardHTML\(r\)\{(.+?)\n\}\n", cls.src, re.S)
        assert m, "cardHTML 을 찾지 못했다"
        cls.card = m.group(1)
        m = re.search(r"function rvClamped\(cap, text, key, open\)\{(.+?)\n\}", cls.src, re.S)
        assert m, "rvClamped 를 찾지 못했다"
        cls.rv = m.group(1)

    # --- ① 카드 몫은 세 줄 ---

    def test_review_point_body_has_its_own_span(self):
        """확인 요청 본문은 캡션과 분리된 span 이다 — 캡션이 세 줄 중 한 줄을
        먹으면 실제로 읽히는 것은 두 줄뿐이다."""
        self.assertIn('class="rvtx"', self.rv,
                      "확인 포인트 본문이 별도 span(.rvtx) 으로 싸이지 않았다")
        self.assertIn('class="rvcap"', self.rv)
        # 캡션이 클램프 박스 밖에 있어야 한다
        self.assertLess(self.rv.index('class="rvcap"'), self.rv.index('class="rvtx"'))

    def test_long_card_text_is_built_in_one_place(self):
        """확인 요청과 대기 사유는 같은 종류의 글이다 — 한 함수로 지어야
        한쪽만 고쳐져 blocked 카드가 문장 벽으로 남는 일이 없다."""
        self.assertRegex(self.card, r"rvClamped\(\s*\"확인 요청\"\s*,\s*r\.review_point")
        self.assertRegex(self.card, r"rvClamped\(\s*\"대기 사유\"\s*,\s*r\.block_reason")

    def test_clamp_is_in_the_base_not_one_skin(self):
        """세 줄 클램프는 베이스 CSS 에 있다 — 스킨이 열 벌이 넘는다."""
        body = css_rule(self.src, ".rvpt .rvtx")
        self.assertIsNotNone(body, "베이스에 .rvpt .rvtx 클램프 규칙이 없다")
        self.assertIn("line-clamp:3", body.replace(" ", ""),
                      "확인 요청 본문이 세 줄로 접히지 않는다")
        self.assertIn("overflow:hidden", body.replace(" ", ""))

    # --- ③ 잘렸다는 사실을 카드가 말한다 ---

    def test_card_offers_to_open_it_here(self):
        """잘렸을 때 펴는 손잡이가 카드에 있다."""
        self.assertIn('class="rvmore"', self.rv,
                      "잘린 글을 펴는 손잡이가 없다")
        # 손잡이는 클램프 박스 **밖**이다 — 안에 넣으면 자기가 잘린다.
        self.assertLess(self.rv.index("</div>"), self.rv.index('class="rvmore"'))

    def test_the_handle_opens_in_place_not_in_another_tab(self):
        """카드 전체가 이미 Docs 로 가는 손잡이다 — 같은 자리에 같은 목적지가
        둘이면 하나는 없느니만 못하다 (REQ-20260829-009 반려)."""
        self.assertIn("data-expand", self.rv,
                      "손잡이가 이 화면의 펼침 문법(data-expand)을 쓰지 않는다")
        self.assertNotIn("data-doc-open", self.rv)
        self.assertNotIn("docOpen", self.rv, "손잡이가 아직 문서로 건너뛴다")
        self.assertNotIn("tab =", self.rv, "손잡이가 탭을 옮긴다")

    def test_opening_survives_the_poll(self):
        """15초 폴링이 보드를 다시 그린다 — 열어 둔 것이 그때마다 접히면
        읽던 자리를 잃는다. 이 화면이 이미 쓰는 기억(expanded)에 얹는다."""
        self.assertRegex(self.card, r'expanded\.has\("rv:"',
                         "열림이 다시 그리면 사라진다")

    def test_the_opened_text_scrolls_inside_its_own_box(self):
        """카드 높이에 **천장**이 있어야 열의 리듬이 서고, 승인·반려 버튼이
        긴 글에 밀려 카드 밖으로 나가지 않는다."""
        rules = [css for sel, css in _rules(self.src, ".rvpt.open .rvtx")]
        self.assertTrue(rules, "펼친 글의 상자 규칙이 없다")
        flat = " ".join(rules).replace(" ", "")
        self.assertIn("max-height:", flat, "펼치면 카드가 끝없이 자란다")
        self.assertIn("overflow:auto", flat, "천장을 씌우고 나머지를 잘라 버렸다")
        self.assertIn("line-clamp:unset", flat, "펼쳤는데 세 줄 그대로다")

    def test_the_opened_box_is_scrollable_by_keyboard(self):
        """마우스 휠만 되는 상자는 키보드 사용자에게 잘린 글이다 (WCAG 2.1.1) —
        이 저장소가 첨부 발췌(.attx.open)에서 이미 세운 규칙이다."""
        self.assertRegex(self.rv, r'tabindex="0"',
                         "펼친 상자에 키보드가 닿지 않는다")
        self.assertIn("aria-expanded", self.rv, "손잡이가 열림/닫힘을 말하지 않는다")

    def test_the_open_card_can_be_seen_without_hands(self):
        """펼친 화면은 눌러야만 생긴다 — 헤드리스로 확인할 길이 있어야
        "코드상 맞다"로 끝나지 않는다 (`?dlg=`·`?pick=` 의 선례)."""
        self.assertIn("[?&]rvopen=", self.src, "펼친 카드를 세워 볼 길이 없다")

    def test_the_handle_stays_while_open_so_it_can_be_closed(self):
        """열어 놓고 접을 수 없으면 여는 것이 파괴적 행동이 된다."""
        self.assertRegex(self.src, r"\.rvpt\.open\s*\+\s*\.rvmore\{",
                         "열린 상태에서 손잡이가 사라져 접을 수 없다")

    def test_more_handle_shows_only_when_actually_cut(self):
        """안 잘린 한 줄짜리 확인 요청에 손잡이가 붙으면 그건 소음이다."""
        hidden = css_rule(self.src, ".rvmore")
        self.assertIsNotNone(hidden, ".rvmore 규칙이 없다")
        self.assertIn("display:none", hidden.replace(" ", ""))
        self.assertRegex(self.src, r"\.rvpt\.iscut\s*\+\s*\.rvmore\{",
                         "잘린 경우에만 손잡이를 여는 규칙이 없다")

    def test_more_handle_is_ink_not_a_filled_button(self):
        """색면 금지 — 손잡이는 글자와 밑줄로만 (`+ N개 더 보기` 와 같은 문법)."""
        body = css_rule(self.src, ".rvmore")
        flat = body.replace(" ", "")
        self.assertIn("background:none", flat)
        self.assertIn("border:0", flat)

    def test_cut_is_measured_not_guessed(self):
        """잘림 여부는 스킨·밀도·열 폭에 따라 다르다 — 글자 수로 짐작하지 않고 실측한다."""
        m = re.search(r"function markClamped\((.*?)\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "markClamped 실측 함수가 없다")
        body = m.group(2)
        self.assertIn("scrollHeight", body)
        self.assertIn("clientHeight", body)
        self.assertIn("iscut", body)
        # 문턱은 px 상수가 아니라 줄 높이다 — 클램프가 자르면 최소 한 줄이
        # 남는다. 1px 상수로 쟀더니 넓은 창에서 딱 세 줄로 끝난 대기 사유가
        # (말줄임표도 없이) 잘렸다고 보고돼 손잡이가 붙었다.
        self.assertIn("lineHeight", body,
                      "잘림 문턱을 줄 높이로 잡지 않았다 — 반올림 오차가 손잡이를 띄운다")

    def test_measure_runs_after_board_render_and_on_resize(self):
        """카드를 다시 그리거나 창 폭이 바뀌면 잘림 여부도 바뀐다."""
        m = re.search(r"function renderBoard\(rows\)\{(.+?)\n\}\n", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("markClamped", m.group(1), "보드를 그린 뒤 잘림을 재지 않는다")
        self.assertRegex(self.src, r'addEventListener\("resize",\s*[^)]*[Cc]lamp',
                         "창 크기가 바뀔 때 잘림을 다시 재지 않는다")

    # --- ④ 호버로 펼치지 않는다 ---

    def test_no_hover_expansion(self):
        """마우스를 얹었다고 카드가 자라면 아래 카드가 통째로 밀린다 — 그리고
        그 화면이 사용자가 신고한 화면이다."""
        for m in re.finditer(r"(?m)^([^\n{]*:hover[^\n{]*\.rvpt[^{]*)\{([^}]*)\}", self.src):
            self.assertNotIn("line-clamp:unset", m.group(2).replace(" ", ""),
                             "호버로 클램프를 푸는 규칙이 남아 있다: " + m.group(1).strip())
            self.assertNotIn("max-height:60em", m.group(2).replace(" ", ""),
                             "호버로 카드를 늘리는 규칙이 남아 있다: " + m.group(1).strip())

    # --- ⑤ 전문을 펴는 자리는 문서다 ---

    def test_document_still_opens_the_full_text(self):
        """카드가 자른 나머지는 문서 뷰어의 확인 요청 callout 이 편다."""
        self.assertIn("gateNote", self.src)
        self.assertIn('class="gate-b"', self.src)


if __name__ == "__main__":
    unittest.main()
