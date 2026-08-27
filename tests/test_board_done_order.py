"""끝난 카드를 무엇으로 세우는가 (REQ-20260827-016-62x6).

사용자 지적: "done 카드 목록에서 우선순위 가중치가 높은 순으로 화면에 보여주는데
마지막 업데이트 시간 기준으로 보여줘."

맞는 말이다. **우선순위는 "다음에 무엇을 할 것인가"에 답하는 축인데, 이미 끝난
일에는 그 질문이 없다.** done 이 286건까지 쌓인 지금 가중치 계단으로 묶여 있으면,
방금 끝난 것을 찾으려고 계단마다 훑어야 한다. 이 컬럼에서 알고 싶은 것은
"무엇이 최근에 끝났나" 하나뿐이다.

실측(카탈로그 286건):

    예전 첫 3   !85(08-26T22:13) · !85(08-27T00:02) · !80(08-26T19:19)
    이제 첫 3   !50(08-27T10:07) · !50(08-27T10:07) · !50(08-27T09:16)

살아 있는 컬럼(open·in-progress·review)은 그대로 우선순위가 1차 키다 — 거기서는
그 질문이 여전히 유효하다. **끝난 것과 살아 있는 것에 같은 자를 대지 않는 것**이
이 변경의 요점이다.

실행: python3 tests/ board_done_order
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class BoardDoneOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r"for \(const st of STATUSES\)\{(.*?)\n  \}",
                      cls.src, re.S)
        cls.loop = m.group(1) if m else ""

    def test_b1_terminal_columns_sort_by_updated(self):
        """B1. 끝난 컬럼은 갱신 시각으로 세운다 (이 요청의 전부)."""
        self.assertTrue(self.loop, "보드 컬럼 루프를 찾지 못했다")
        self.assertIn("TERMINAL.has(st)", self.loop,
                      "끝난 컬럼을 따로 가르지 않는다")
        self.assertIn("b.updated || b.created", self.loop,
                      "갱신 시각으로 세우지 않는다")

    def test_b2_it_uses_the_shared_terminal_set(self):
        """B2. '끝났다'의 정의를 새로 쓰지 않고 이미 있는 것을 쓴다.

        `done` 만 손으로 적으면 `cancelled` 가 빠지고, 그 순간 같은 질문에 두
        가지 답이 생긴다 — 이 저장소가 오늘만 세 번 밟은 실패다.
        """
        self.assertRegex(
            self.src, r'const TERMINAL = new Set\(\["done",\s*"cancelled"\]\)')
        self.assertNotIn('st === "done"', self.loop,
                         "끝난 상태를 손으로 다시 적었다")

    def test_b3_live_columns_keep_priority(self):
        """B3. 살아 있는 컬럼의 순서는 건드리지 않는다.

        거기서는 "다음에 무엇을 할 것인가"가 여전히 유효한 질문이고, 우선순위
        축을 만든 이유가 그것이다(REQ-20260826-005). 끝난 것을 고치다 살아 있는
        것까지 뒤집으면 고침이 새 손실이 된다.
        """
        self.assertRegex(
            self.src,
            r"const workOrder = rows => \[\.\.\.rows\]\.sort\(\(a, b\) =>\s*"
            r"\n\s*\(prioOf\(b\) - prioOf\(a\)\)")

    def test_b4_the_original_list_is_not_mutated(self):
        """B4. 원본 배열을 제자리에서 뒤집지 않는다.

        `shown` 은 다른 계산(카운트·병목)이 함께 보는 배열이다. 제자리 정렬은
        그 계산들이 보는 순서를 조용히 바꾼다.
        """
        self.assertIn("[...grp].sort(", self.loop,
                      "복사본이 아니라 원본을 정렬한다")


if __name__ == "__main__":
    unittest.main()
