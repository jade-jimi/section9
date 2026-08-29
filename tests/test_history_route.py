"""화면을 옮기면 이력도 함께 옮겨지는가 (REQ-20260826-026-62x6).

증상은 "graph 에서 문서를 열고 뒤로가기를 눌렀더니 board 로 갔다" 였다.

원인은 이력이 아니라 **누락**이다. 그래프 캔버스의 노드 클릭은 tab 을 docs 로
바꾸고 문서를 그리면서 `pushRoute()` 를 부르지 않았다. 그래서 history 스택
꼭대기는 여전히 `#graph` 고, 뒤로가기는 그 아래(= 그래프로 들어오기 전 탭,
대개 board)로 튄다. 화면만 문서로 가 있고 이력은 따라오지 않은 상태다.

조용한 종류의 결함이다 — 이동 자체는 정상으로 보이고, 뒤로가기를 눌러야만
드러난다. 그래서 계약으로 못박는다: **tab 을 바꾸는 경로는 예외 없이
pushRoute() 를 부른다.**

픽셀이 아니라 이 계약만 검사한다. 실제 뒤로가기는 사람의 확인 몫이다.

실행: python3 tests/ history_route
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


class HistoryRoute(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    def test_graph_node_click_pushes_history(self):
        """그래프 노드 → 문서 이동이 history 에 쌓인다 (이 REQ의 실사고)."""
        m = re.search(r'canvas\.addEventListener\("pointerup".*?\n    \}',
                      self.src, re.S)
        self.assertIsNotNone(m, "그래프 캔버스 pointerup 핸들러를 찾지 못했다")
        body = m.group(0)
        self.assertIn('tab = "docs"', body,
                      "노드 클릭이 docs 로 가지 않는다 — 테스트가 낡았다")
        self.assertIn("pushRoute()", body,
                      "노드 클릭이 pushRoute() 를 부르지 않는다 — "
                      "뒤로가기가 그래프를 건너뛴다")

    def test_every_tab_switch_pushes(self):
        """tab 을 바꾸는 모든 곳이 pushRoute 를 부른다.

        한 곳이라도 빠지면 그 경로만 뒤로가기가 어긋나고, 다른 경로가
        멀쩡하니 재현 조건을 찾기 어려워진다.
        """
        # `tab = <값>` 대입 지점마다 뒤따르는 800자 안에 pushRoute 가 있는가.
        # (선언 `let tab = "board"` 와 popstate 경로의 applyRoute 는 제외 —
        #  전자는 초기값, 후자는 이미 브라우저가 이력을 옮긴 뒤다.)
        holes = []
        for m in re.finditer(r'(?<!let )\btab = (?:"(\w+)"|tabBtn\.dataset\.tab)',
                             self.src):
            after = self.src[m.end():m.end() + 800]
            if "pushRoute()" not in after:
                line = self.src.count("\n", 0, m.start()) + 1
                holes.append(f"{line}행: {m.group(0)}")
        self.assertEqual(holes, [],
                         "tab 을 바꾸면서 이력을 쌓지 않는 경로: "
                         + "; ".join(holes))

    def test_popstate_reapplies_route(self):
        """뒤로가기는 해시를 다시 화면에 반영한다 — 이 고리가 없으면
        URL 만 바뀌고 화면은 그대로다."""
        self.assertRegex(
            self.src,
            r'addEventListener\("popstate",\s*\(\)\s*=>\s*applyRoute\(')


if __name__ == "__main__":
    unittest.main()
