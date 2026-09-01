"""구역의 끝은 주석 밖의 빈 줄이다 (REQ-20260901-021).

실사고 2026-09-01: 아홉 시험 파일이 CSS 구역의 끝을 첫 `\n\n` 으로 재고
있었다. 뜻은 맞았다 — 이 저장소의 CSS 는 구역 사이를 빈 줄로 띄운다.
틀린 것은 **어디서 세느냐**다: 주석 안에서도 셌다. 그런데 이 저장소의
주석은 길고 문단을 빈 줄로 나눈다 — 주석 한가운데 빈 줄 하나가 생기는
순간 그 아래 규칙 전부가 시험 밖으로 조용히 빠졌다. 판정 대화상자 구역이
실제로 그랬다.

고정할 성질: **주석 안의 빈 줄은 구역을 끊지 않고, 주석 밖의 빈 줄은 끊는다.**

실행: python3 tests/ css_section
"""
import os
import unittest

import websrc

HERE = os.path.dirname(os.path.abspath(__file__))
OVERLAY = os.path.join(HERE, "..", "web", "css", "overlay.css")


class CssSectionEndsAtRealBlankLine(unittest.TestCase):
    def test_a_blank_line_inside_a_comment_does_not_cut(self):
        src = ("/* ---- 어떤 구역 ---- */\n"
               ".a{color:red}\n"
               "/* 긴 주석은 문단을 나눈다.\n"
               "\n"
               "   둘째 문단. */\n"
               ".b{color:blue}\n")
        sec = websrc.css_section(self, src, r"/\* -+ 어떤 구역")
        self.assertIn(".a{", sec, "구역이 시작도 못 했다")
        self.assertIn(".b{", sec,
                      "주석 안의 빈 줄이 구역을 끊었다 — 아래 규칙이 시험 밖이다")

    def test_a_blank_line_between_rules_still_cuts(self):
        src = ("/* ---- 어떤 구역 ---- */\n"
               ".a{color:red}\n"
               "\n"
               "/* ---- 다음 구역 ---- */\n"
               ".b{color:blue}\n")
        sec = websrc.css_section(self, src, r"/\* -+ 어떤 구역")
        self.assertIn(".a{", sec)
        self.assertNotIn(".b{", sec, "구역이 남의 구역까지 삼켰다")

    def test_the_last_section_runs_to_the_end(self):
        src = "/* ---- 끝 구역 ---- */\n.a{color:red}\n"
        self.assertIn(".a{", websrc.css_section(self, src, r"/\* -+ 끝 구역"))

    def test_a_missing_head_fails_loudly(self):
        """조용히 빈 문자열을 주면 시험이 아무것도 안 보면서 통과한다."""
        with self.assertRaises(AssertionError):
            websrc.css_section(self, ".a{color:red}", r"/\* -+ 없는 구역")

    def test_the_real_dialog_section_reaches_past_its_comments(self):
        """실물로 고정한다 — 이 구역이 그 사고가 난 자리다."""
        with open(OVERLAY, encoding="utf-8") as f:
            src = f.read()
        sec = websrc.css_section(self, src, r"/\* -+ 판정 대화상자")
        for sel in (".dlgbox{", ".dlgfoot{", ".dlgatt{"):
            self.assertIn(sel, sec, "%s 가 구역 밖으로 빠졌다" % sel)


if __name__ == "__main__":
    unittest.main()
