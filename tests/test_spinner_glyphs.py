"""웨이팅 스피너 글리프의 이모지 오염 방지 (REQ-20260825-017 반려 재작업).

반려 사유: "초록 이모지가 여전히 섞여있다" — 스피너 프레임의 ✳(U+2733)이
이모지 후보 코드포인트라 이모지 폰트 폴백(REQ-012)이 초록 컬러 타일로 렌더.
v2에서 ✳을 비이모지 ✱(U+2731)로 대체했다. 이 테스트는 그 결정을 계약으로
고정한다: 스피너 프레임(ccglyph keyframes·ccspin 기본 글리프)에 이모지 후보
코드포인트가 다시 들어오면 실패한다 — 변형 선택자(\\FE0E) 지원 여부에 기대는
수정은 브라우저/폰트에 따라 깨지므로(v1의 실패) 후보 자체를 금지한다.

REQ-20260825-022(글리프 다양화)로 프레임을 늘릴 때도 이 검사를 통과하는
비이모지 글리프만 써야 한다 (예: ✢ ✱ ✶ ✻ ✽ ❋ ✧ — ✳ ✴ ❇ ☀ 등은 금지).

실행: python3 tests/ spinner
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()

# Unicode Emoji=Yes 코드포인트 중 스피너류 글리프가 속할 수 있는 구간
# (Miscellaneous Symbols 2600-26FF · Dingbats 2700-27BF, UTS #51 emoji-data 발췌).
# 0x1F000 이상 전 구간은 아래 _is_emoji_candidate에서 일괄 금지한다.
EMOJI_BMP = frozenset(
    list(range(0x2600, 0x2605)) + [0x260E, 0x2611, 0x2614, 0x2615, 0x2618,
    0x261D, 0x2620, 0x2622, 0x2623, 0x2626, 0x262A, 0x262E, 0x262F] +
    list(range(0x2638, 0x263B)) + [0x2640, 0x2642] +
    list(range(0x2648, 0x2654)) + [0x265F, 0x2660, 0x2663, 0x2665, 0x2666,
    0x2668, 0x267B, 0x267E, 0x267F] + list(range(0x2692, 0x2698)) +
    [0x2699, 0x269B, 0x269C, 0x26A0, 0x26A1, 0x26A7, 0x26AA, 0x26AB,
    0x26B0, 0x26B1, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26C8, 0x26CE, 0x26CF,
    0x26D1, 0x26D3, 0x26D4, 0x26E9, 0x26EA] + list(range(0x26F0, 0x26F6)) +
    list(range(0x26F7, 0x26FB)) + [0x26FD,
    0x2702, 0x2705] + list(range(0x2708, 0x270E)) + [0x270F, 0x2712, 0x2714,
    0x2716, 0x271D, 0x2721, 0x2728, 0x2733, 0x2734, 0x2744, 0x2747, 0x274C,
    0x274E] + list(range(0x2753, 0x2756)) + [0x2757, 0x2763, 0x2764] +
    list(range(0x2795, 0x2798)) + [0x27A1, 0x27B0, 0x27BF]
)


def _is_emoji_candidate(ch):
    cp = ord(ch)
    return cp >= 0x1F000 or cp in EMOJI_BMP or cp == 0xFE0F


class TestSpinnerGlyphs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.html = f.read()

    def _spinner_contents(self):
        """ccglyph keyframes와 .ccspin::before의 content 문자열 전부."""
        out = []
        kf = re.search(r"@keyframes ccglyph\{(.*?)\}\s*(?:@|\.|/\*)",
                       self.html, re.S)
        self.assertIsNotNone(kf, "@keyframes ccglyph 정의가 index.html에 없다")
        out += re.findall(r'content:"([^"]*)"', kf.group(1))
        sp = re.search(r"\.ccspin::before\{([^}]*)\}", self.html)
        self.assertIsNotNone(sp, ".ccspin::before CSS 규칙이 없다")
        out += re.findall(r'content:"([^"]*)"', sp.group(1))
        return out

    def test_frames_exist(self):
        """진행이 ≥5단계다 — 정지 화면이 아니다. 글리프 교체(content)든
        스케일 펄스(transform)든 진행 표현 방식은 무관하다 (REQ-058: 폰트
        폴백 지터 때문에 글리프 교체 → 스케일 펄스로 전환)."""
        i = self.html.index("@keyframes ccglyph")
        block = self.html[i:self.html.index("}\n", i + 1200) + 1] \
            if "}\n" in self.html[i:i + 2000] else self.html[i:i + 2000]
        steps = len(re.findall(r"content:", block)) or \
            len(re.findall(r"transform:scale", block))
        self.assertGreaterEqual(steps, 5, f"진행 단계 부족: {steps}")

    def test_no_emoji_candidate_glyphs(self):
        """어떤 프레임에도 이모지 후보 코드포인트가 없다 (반려 원인 재발 방지)."""
        for content in self._spinner_contents():
            # CSS 이스케이프(\FE0E 등)가 남아 있으면 후보 글리프에 기대고 있다는 신호
            self.assertNotRegex(
                content, r"\\FE0", f"변형 선택자 의존 금지: content:\"{content}\"")
            for ch in content:
                self.assertFalse(
                    _is_emoji_candidate(ch),
                    f"이모지 후보 글리프 U+{ord(ch):04X}({ch})가 스피너 프레임에 "
                    f"있다 — 이모지 폰트 폴백이 컬러 타일로 렌더한다. "
                    f"비이모지 글리프로 교체하라 (REQ-20260825-017)")


class TestSpinnerWidth(unittest.TestCase):
    """글리프 폭 고정 (REQ-20260825-057): 프레임마다 폭이 달라 뒤 텍스트가
    흔들리던 문제 — 고정폭 박스 + mono 강제 + 이모지 표현 차단."""
    def setUp(self):
        import os as _os
        here = _os.path.dirname(_os.path.abspath(__file__))
        with open(index_path(),
                  encoding="utf-8") as f:
            self.html = f.read()

    def test_fixed_width_box(self):
        import re as _re
        m = _re.search(r"\.ccspin\{([^}]*)\}", self.html)
        self.assertIsNotNone(m, ".ccspin 규칙이 없다")
        css = m.group(1)
        self.assertIn("display:inline-block", css)
        self.assertIn("text-align:center", css)
        self.assertRegex(css, r"width:\s*[\d.]+(ch|em|px)")
        self.assertIn("font-family:var(--mono)", css)   # 이모지 폰트 폴백 차단


if __name__ == "__main__":
    unittest.main(verbosity=2)
