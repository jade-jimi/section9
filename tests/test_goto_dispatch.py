"""문서 본문 전이 버튼이 삼켜지지 않는가 (REQ-20260826-025-62x6).

`data-goto` 는 대시보드에서 두 뜻으로 쓰인다.
  ① 탭 이름 — `data-goto="graph"` (본문 안에서 다른 탭으로 건너뛰는 링크)
  ② 상태 전이 — `data-goto="REQ-…|in-progress|review"` (문서 본문의 전이 버튼)

두 분기가 **같은 click 리스너 안**에 있어서, 앞선 탭 분기가 전이 값까지
집어삼키고 `return` 하면 뒤쪽 전이 핸들러에 영영 닿지 못한다. 화면은 멀쩡한
버튼을 그대로 보여주므로 눌러도 아무 일이 없는 것으로만 보인다 — 실제로
사용자가 "보드에서는 되는데 본문에서는 안 된다"로 발견했다.

픽셀이 아니라 이 디스패치 계약만 검사한다. 실제 클릭은 사람의 확인 몫이다.

실행: python3 tests/ goto_dispatch
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class GotoDispatch(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    def test_both_meanings_still_exist(self):
        """전제 확인 — 두 뜻이 실제로 공존한다. 하나가 사라지면 이 테스트도 낡는다."""
        self.assertIn('data-goto="graph"', self.src)
        self.assertRegex(self.src, r'data-goto="\$\{esc\(m\.id\)\}\|\$\{to\}')

    def test_tab_branch_excludes_transition_values(self):
        """탭 분기는 파이프가 없는 값(=탭 이름)만 가져간다."""
        m = re.search(r'const go = e\.target\.closest\("\[data-goto\]"\);\s*'
                      r'if \((.+?)\)\{', self.src, re.S)
        self.assertIsNotNone(m, "탭 분기를 찾지 못했다")
        cond = m.group(1)
        self.assertIn('includes("|")', cond,
                      "탭 분기가 전이 값까지 가져가면 본문 버튼이 조용히 죽는다")
        self.assertIn("!", cond, "파이프가 '있을 때' 가져가면 정반대가 된다")

    def test_transition_handler_is_reachable(self):
        """전이 핸들러가 탭 분기보다 뒤에 있다 — 그래서 탭 분기의 조건이 중요하다."""
        tab_at = self.src.index('const go = e.target.closest("[data-goto]")')
        trans_at = self.src.index('const gt = e.target.closest("[data-goto]")')
        self.assertLess(tab_at, trans_at)
        # 그 사이에 리스너가 새로 열리지 않는다 = 같은 리스너 안 = return 이 치명적
        between = self.src[tab_at:trans_at]
        self.assertNotIn('addEventListener("click"', between,
                         "리스너가 갈리면 이 테스트의 전제가 달라진다")

    def test_reject_needs_reason_from_body(self):
        """본문에서의 review→in-progress 도 사유를 받는다 (보드와 같은 규율).

        사유 없는 반려는 재작업하는 쪽이 무엇을 고쳐야 할지 모른다.
        """
        m = re.search(r'const gt = e\.target\.closest.*?\n\s*\}', self.src, re.S)
        self.assertIsNotNone(m)
        blk = m.group(0)
        self.assertIn("rejectWithReason", blk)
        self.assertIn('from === "review"', blk)


if __name__ == "__main__":
    unittest.main(verbosity=2)
