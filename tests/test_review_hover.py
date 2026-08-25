"""보드 카드 리뷰 내용 호버 펼침 계약 (REQ-20260825-071 반려 재작업).

반려 사유: "보드 화면에서 카드만 봤을 때 리뷰 내용이 줄어들어서 내용을
파악할 수가 없다. 마우스 호버를 했을 때라도 내용을 확인이 되면 좋겠는데."

calm 스킨은 컬럼 리듬을 위해 .rvpt(확인 포인트/대기 사유)를 3줄로 접는다.
이 테스트는 그 접힘에 반드시 호버/포커스 펼침이 짝으로 존재함을 계약으로
고정한다: 어떤 스킨이든 .rvpt에 line-clamp를 걸면, 같은 스킨에 카드
호버(:hover)로 클램프를 해제하는 규칙이 있어야 한다 — 접기만 하고 펼칠
수단을 주지 않으면 이 반려가 재발한다.

실행: python3 tests/ hover
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class TestReviewHoverExpand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.html = f.read()

    def _skins_clamping_rvpt(self):
        """`.rvpt`에 -webkit-line-clamp:<n>을 거는 스킨 이름 집합."""
        skins = set()
        for m in re.finditer(
                r'\[data-skin="([^"]+)"\][^{}]*\.rvpt[^{}]*\{([^}]*)\}',
                self.html):
            if re.search(r"-webkit-line-clamp:\s*\d", m.group(2)):
                skins.add(m.group(1))
        return skins

    def test_calm_clamps_rvpt(self):
        """전제 확인: calm은 .rvpt를 접는다 (접힘 자체가 없어졌다면
        이 계약의 대상이 사라진 것이므로 테스트를 갱신하라)."""
        self.assertIn("calm", self._skins_clamping_rvpt())

    def test_every_clamp_has_hover_release(self):
        """접는 스킨마다 카드 :hover 에서 클램프를 해제하는 규칙이 있다."""
        for skin in self._skins_clamping_rvpt():
            pat = (r'\[data-skin="%s"\][^{}]*\.card:hover[^{}]*\.rvpt'
                   r'[^{}]*\{([^}]*)\}' % re.escape(skin))
            m = re.search(pat, self.html)
            self.assertIsNotNone(
                m, f"skin '{skin}'이 .rvpt를 접는데 .card:hover 펼침 규칙이 "
                   f"없다 — 리뷰 내용을 확인할 수단이 사라진다 (REQ-071 반려)")
            css = m.group(1)
            self.assertRegex(
                css, r"-webkit-line-clamp:\s*(unset|none|initial|\d{2,})",
                f"skin '{skin}'의 hover 규칙이 클램프를 해제하지 않는다")
            # max-height로도 잘리면 해제가 무효 — 함께 열려야 한다
            if re.search(r"max-height", self._rvpt_base_css(skin) or ""):
                self.assertRegex(
                    css, r"max-height:\s*(none|\d{2,}em|\d{3,}px)",
                    f"skin '{skin}'의 hover 규칙이 max-height를 열지 않는다")

    def _rvpt_base_css(self, skin):
        for m in re.finditer(
                r'\[data-skin="%s"\][^{}]*\.rvpt[^{}]*\{([^}]*)\}'
                % re.escape(skin), self.html):
            if re.search(r"-webkit-line-clamp:\s*\d", m.group(1)):
                return m.group(1)
        return None

    def test_keyboard_focus_release(self):
        """마우스 없는 사용자도 펼칠 수 있다 — :focus-within 짝 규칙."""
        for skin in self._skins_clamping_rvpt():
            self.assertRegex(
                self.html,
                r'\[data-skin="%s"\][^{}]*\.card:focus-within[^{}]*\.rvpt'
                % re.escape(skin),
                f"skin '{skin}'에 :focus-within 펼침이 없다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
