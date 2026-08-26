"""문서 본문 전이 버튼이 삼켜지지 않는가 (REQ-20260826-025-62x6).

한때 `data-goto` 하나가 두 뜻으로 쓰였다.
  ① 탭 이름 — `data-goto="graph"` (본문 안에서 다른 탭으로 건너뛰는 링크)
  ② 상태 전이 — `data-goto="REQ-…|in-progress|review"` (문서 본문의 전이 버튼)

두 분기가 **같은 click 리스너 안**에 있어서, 앞선 탭 분기가 전이 값까지
집어삼키고 `return` 하면 뒤쪽 전이 핸들러에 영영 닿지 못했다. 화면은 멀쩡한
버튼을 그대로 보여주므로 눌러도 아무 일이 없는 것으로만 보인다 — 실제로
사용자가 "보드에서는 되는데 본문에서는 안 된다"로 발견했다.

고침은 이름을 가르는 것이다: 전이는 `data-trans`, 탭 점프는 `data-goto`.
한 이름을 두 뜻으로 쓰는 한, 조건을 아무리 정교하게 걸어도 다음 사람이 또
밟는다. 이 테스트는 **둘이 다시 한 이름으로 합쳐지는 것**을 막는다.

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

    def test_transition_buttons_use_their_own_name(self):
        """전이 버튼은 data-trans 다 — data-goto 로 되돌아가면 다시 삼켜진다."""
        self.assertRegex(self.src,
                         r'data-trans="\$\{esc\(m\.id\)\}\|\$\{to\}')
        self.assertNotRegex(self.src,
                            r'data-goto="\$\{esc\(m\.id\)\}\|')

    def test_handler_reads_the_same_name(self):
        """마크업과 핸들러가 같은 이름을 본다 — 갈리면 버튼이 조용히 죽는다.

        실제로 한 번 갈렸다: 마크업만 data-trans 로 바뀌고 핸들러는 data-goto
        를 보고 있어서, 고쳤다고 커밋된 뒤에도 버튼은 여전히 죽어 있었다.
        """
        self.assertIn('closest("[data-trans]")', self.src)
        self.assertIn("dataset.trans.split", self.src)

    def test_tab_branch_only_takes_tab_names(self):
        """탭 점프 분기는 여전히 살아 있고, 전이 값은 넘보지 않는다."""
        self.assertIn('data-goto="graph"', self.src)
        m = re.search(r'const go = e\.target\.closest\("\[data-goto\]"\);\s*'
                      r'if \((.+?)\)\{', self.src, re.S)
        self.assertIsNotNone(m, "탭 분기를 찾지 못했다")
        self.assertIn('includes("|")', m.group(1),
                      "이름을 갈랐어도 이 가드는 남긴다 — 재사용 유혹이 다시 온다")

    def test_reject_needs_reason_from_body(self):
        """본문에서의 review→in-progress 도 사유를 받는다 (보드와 같은 규율).

        사유 없는 반려는 재작업하는 쪽이 무엇을 고쳐야 할지 모른다.
        """
        m = re.search(r'const gt = e\.target\.closest\("\[data-trans\]"\).*?'
                      r'\n\s*\}', self.src, re.S)
        self.assertIsNotNone(m)
        blk = m.group(0)
        self.assertIn("rejectWithReason", blk)
        self.assertIn('from === "review"', blk)


if __name__ == "__main__":
    unittest.main(verbosity=2)
