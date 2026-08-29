"""탭 알약이 화면을 따라오는가 (REQ-20260829-007-62x6).

보드에서 `이어 말하기` 를 누르면 터미널이 뜨는데 상단 알약은 Board 에 그대로
남아 있었다. 화면과 표시가 갈린 것이다 — 사용자가 어디에 있는지 헤드가
거짓말을 한다.

원인은 사본이었다. `.active` 를 칠하는 코드가 네 자리에 손으로 적혀 있었고
(라우트 복원·탭 클릭·docOpen·그래프 노드 클릭), `tab` 을 옮기는 다섯 번째
길인 `docPick` 만 그 한 줄을 빠뜨렸다. 사본을 늘리는 한 다음 길이 또 빠진다.

그래서 이 시험은 "docPick 에 한 줄을 더했는가" 를 묻지 않는다. **자리를
하나로 모았는가** 를 묻는다 — `tabSync()` 가 `tab` 을 읽어 칠하고, 그리는
길목(render)이 매번 그것을 부른다. 그러면 화면을 옮기는 어떤 손도 표시를
따로 챙길 필요가 없다.

픽셀이 아니라 이 계약만 검사한다. 실제 클릭은 사람의 확인 몫이다.

실행: python3 tests/ tab_active_sync
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()

# 손으로 적은 사본의 모양 — `[data-tab]` 을 훑어 active 를 토글하는 줄
HAND_COPY = re.compile(
    r'querySelectorAll\("\[data-tab\]"\)[\s\S]{0,120}?classList\.toggle\('
    r'"active"')


class TabActiveSync(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    def test_one_place_paints_the_pill(self):
        """T1. 칠하는 자리는 하나다 — tabSync() 가 tab 을 읽어 결정한다."""
        m = re.search(r'function tabSync\(\)\{([\s\S]{0,400}?)\n\}', self.src)
        self.assertIsNotNone(m, "tabSync() 가 없다 — 사본이 다시 흩어진다")
        body = m.group(1)
        self.assertIn('querySelectorAll("[data-tab]")', body)
        self.assertIn('"active"', body)
        self.assertIn("dataset.tab === tab", body,
                      "인자로 받은 값이 아니라 상태(tab)를 읽어야 한다 — "
                      "부르는 쪽이 값을 챙기면 그게 다시 사본이다")

    def test_render_syncs_before_the_terminal_early_return(self):
        """T2. render() 가 매번 맞춘다 — 그것도 조기 반환보다 먼저.

        render() 는 살아있는 터미널 셸을 재빌드하지 않으려고 일찍 반환한다
        (REQ-040). 그 뒤에서 부르면 정작 이 결함이 난 자리에서 안 불린다.
        """
        m = re.search(r'\nfunction render\(\)\{([\s\S]*?)\n\}\n', self.src)
        self.assertIsNotNone(m, "render() 를 찾지 못했다")
        body = m.group(1)
        i_sync = body.find("tabSync()")
        i_ret = body.find('if (tab === "terminal" && TERM')
        self.assertGreaterEqual(i_sync, 0, "render() 가 tabSync() 를 부르지 않는다")
        self.assertGreaterEqual(i_ret, 0, "터미널 조기 반환을 찾지 못했다")
        self.assertLess(i_sync, i_ret,
                        "tabSync() 가 조기 반환 뒤에 있다 — 터미널로 옮겨갈 때 "
                        "정확히 안 불리는 자리다")

    def test_doc_pick_moves_the_tab_and_renders(self):
        """T3. 이어 말하기는 tab 을 옮기고 그린다 — 표시는 render 가 맡는다."""
        m = re.search(r'function docPick\(id, jump\)\{([\s\S]*?)\n\}\n',
                      self.src)
        self.assertIsNotNone(m, "docPick() 을 찾지 못했다")
        body = m.group(1)
        self.assertIn('tab = "terminal"', body)
        self.assertIn("render()", body)
        self.assertNotRegex(body, HAND_COPY,
                            "docPick 이 표시를 직접 칠한다 — 그러면 또 사본이다")

    def test_no_hand_written_copies_left(self):
        """T4. 손으로 적은 사본이 남아 있지 않다.

        넷이 흩어져 있었기에 다섯 번째 길이 빠졌다. tabSync() 안의 한 벌만
        남기고 전부 그 함수를 부르게 한다.
        """
        hits = HAND_COPY.findall(self.src)
        self.assertEqual(len(hits), 1,
                         f"[data-tab] active 토글이 {len(hits)} 곳에 있다 — "
                         "tabSync() 안의 한 벌만 남겨라")

    def test_the_paths_that_move_the_screen_call_it(self):
        """회귀: 화면을 옮기는 손들이 모두 tabSync() 를 지난다.

        render() 를 거치지 않는 길(라우트 복원의 doRender=false)도 있으므로
        부르는 자리가 하나로는 부족하다.
        """
        for fn, needle in (("applyRoute", "dlgCheckNav();   // 뒤로가기"),
                           ("docOpen", "function docOpen(id){")):
            self.assertIn(needle, self.src, f"{fn} 자리가 바뀌었다")
        # 라우트 복원은 doRender 가 꺼져 있어도 표시를 맞춰야 한다
        m = re.search(r'dlgCheckNav\(\);   // 뒤로가기[\s\S]{0,200}?'
                      r'if \(doRender\) render\(\);', self.src)
        self.assertIsNotNone(m, "라우트 복원 자리를 찾지 못했다")
        self.assertIn("tabSync()", m.group(0),
                      "라우트 복원이 tabSync() 를 부르지 않는다 — "
                      "doRender=false 면 표시가 안 맞는다")
        self.assertRegex(self.src,
                         r'function docOpen\(id\)\{[\s\S]{0,300}?tabSync\(\)')


if __name__ == "__main__":
    unittest.main()
