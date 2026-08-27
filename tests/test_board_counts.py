"""열 머리 숫자와 띠 숫자 (REQ-20260827-070-62x6).

사용자: "cancelled 카운트 숫자가 다르다."

전수로 세어 보면 **계산은 틀리지 않았다**. 상단 띠는 전체를 세고(cancelled 4),
열 머리는 그 열에 실제로 있는 것만 센다(3). 차이는 REQ-20260827-057 의 하루
자르기다 — 끝난 열에서는 하루가 지난 요청을 내린다.

그래도 **같은 낱말에 다른 수**가 보이면 사람은 고장으로 읽는다. 그리고 그게
맞다: 띠는 열을 여닫는 **필터**라, 띠의 수는 눌렀을 때 나올 수와 같아야 한다.
그래서 세는 집합을 하나로 만든다 — 보드가 실제로 담는 것.

계약은 넷이다.

  ① 띠는 **보드가 담는 집합**에서 센다 — 끝난 상태는 하루 자르기를 거친 것만.
  ② `전체 요청` 은 그 다섯 수의 합이다.
  ③ 띠는 그대로 둔다 — `data-statf` 로 상태 필터가 걸리는 컨트롤이다.
  ④ `3/4` 같은 슬래시 표기도, 설명 문구도 붙이지 않는다. 두 수가 다르다는 것을
     설명하는 표기는 같은 짐을 그대로 진다.

실행: python3 tests/ board_counts
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class BoardCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        cls.fn = cls._grab(cls.src, "renderBoard")

    @staticmethod
    def _grab(src, name):
        m = re.search(r"function %s\([^)]*\)\{[\s\S]*?\n\}" % name, src)
        assert m, name
        return m.group(0)

    # ---------- ① 같은 집합에서 센다 ----------

    def test_strip_counts_what_the_board_holds(self):
        """띠가 세는 대상 = 열이 담는 대상."""
        self.assertIn("const onBoard = reqs.filter", self.fn,
                      "보드가 담는 집합을 따로 세우지 않는다")
        self.assertIn("TERMINAL_WINDOW_MS", self.fn, "하루 자르기를 적용하지 않는다")
        self.assertIn("termAt(r)", self.fn, "열이 쓰는 그 시각으로 자르지 않는다")
        self.assertRegex(self.fn, r"onBoard\.forEach\(r => counts\[r\.status\]",
                         "띠를 여전히 전체에서 센다")
        # 열 머리도 같은 잣대를 쓴다 (colHTML 의 live)
        col = self._grab(self.src, "colHTML")
        self.assertIn("TERMINAL_WINDOW_MS", col, "열이 다른 잣대를 쓴다")
        self.assertIn("termAt(r)", col)
        self.assertIn('<span class="n">${live.length}</span>', col,
                      "열 머리가 자르기 전 수를 보여 준다")

    def test_total_is_the_sum_of_the_five(self):
        """`전체 요청` 은 다섯 수의 합이다 — 다른 셈이 섞이면 또 어긋난다."""
        self.assertIn('data-statf=""><b>${onBoard.length}</b> 전체 요청', self.fn,
                      "전체 요청이 다른 집합을 센다")
        self.assertNotRegex(self.fn, r"<b>\$\{reqs\.length\}</b> 전체 요청",
                            "옛 셈이 남아 있다")

    # ---------- ③ 띠는 컨트롤이다 ----------

    def test_the_strip_is_still_a_filter(self):
        """띠를 지우지 않는다 — 상태 필터가 걸리는 컨트롤이다."""
        self.assertIn('data-statf="${s}"', self.fn, "상태 칩이 필터가 아니다")
        self.assertIn('data-statf=""', self.fn, "전체로 돌아갈 길이 없다")
        self.assertIn("window.__statusFilter", self.fn, "필터 상태를 읽지 않는다")

    # ---------- ④ 설명으로 메우지 않는다 ----------

    def test_no_slash_notation_and_no_excuse_line(self):
        """`3/4` 도, 설명 문구도 없다."""
        strip = self.fn[self.fn.index('<div class="stats">'):
                        self.fn.index('</div>`', self.fn.index('<div class="stats">'))]
        self.assertNotIn("/${", strip, "두 수를 나란히 적는 표기가 남아 있다")
        for word in ("하루", "제외", "기준", "가려", "숨긴"):
            self.assertNotIn(word, strip, "띠에 변명하는 문구를 붙였다: %s" % word)


if __name__ == "__main__":
    unittest.main(verbosity=2)
