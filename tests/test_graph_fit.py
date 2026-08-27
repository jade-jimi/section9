"""줌아웃이 구석으로 쏠린다 (REQ-20260827-083-62x6).

사용자: "줌아웃을 하면 항상 대각선 방향으로 고정이되고 쏠리게 되는데 마음에
들지 않는다. 옵시디언도 이런식인가?"

**커서 기준 줌 자체는 옳다** — 옵시디언도 그렇게 한다. wheel 핸들러의 표준
공식(`tf.x = mx - (mx - tf.x) * k2 / tf.k`)은 건드리지 않는다.

진짜 문제는 **되돌릴 방법이 없다**는 것이었다. 화면 가장자리에서 줌아웃하면
내용이 그 구석에 남고, 손으로 끌어 되찾아야 하니 "고정된다"로 느껴진다.
옵시디언과 다른 점은 둘이다: 전체 보기 동작이 없었고, 줌아웃이 화면을 비웠다.

1차 반려: "비어있는곳을 더블클릭 하면 원복이 안된다. 직접 눈으로 보고 직접
행동해봐." 실제로 눌러 보니 세 군데가 틀려 있었다.

  ㉠ 옮기는 일을 프레임 루프에만 맡겼다. 프레임은 늘 도는 것이 아니다 —
     헤드리스 캡처에서 재 보니 3.3초에 세 장이었다(배경 탭·전원 절약도 같다).
     그러면 gFit() 은 불렸는데 화면은 그대로다 = "눌러도 아무 일이 없다".
  ㉡ 두 번 누른 것을 브라우저의 dblclick 하나로만 알았다. 이 캔버스는 끌기를
     놓치지 않으려 pointerdown 에서 포인터를 잡아 둔다(setPointerCapture).
     그 하나에만 기대면 안 된다 — 이제 우리가 직접 센다.
  ㉢ 맞출 자리를 월드 좌표로 쟀다. 화면 좌표는 깊이 가중(pfOf 0.72~1.24)을 한 번
     더 지나므로, 그 자로 "맞췄다"고 해도 화면에서는 어긋난다.

계약은 여덟이다.

  ① 커서 기준 줌 공식은 그대로다. 고칠 것은 그 줄이 아니다.
  ② 전체 보기 — 경계 상자를 재서 여백을 두고 화면에 꽉 채운다. 빈 곳
     더블클릭과 손잡이 버튼, 두 길 모두로 닿는다.
  ③ 순간이동하지 않는다 — 짧은 감속 이동. 움직임을 줄여 달라고 한 사람에게는
     옮기지 않고 바로 놓는다.
  ④ 그래프가 화면보다 작아지면 커서 기준을 놓고 가운데로 물린다. 사람이
     줌아웃하는 이유는 "다 보고 싶다"이지 "구석으로 보내고 싶다"가 아니다.
  ⑤ 손잡이는 **거의 나갔을 때만** 나온다. 늘 떠 있는 안내는 곧 안 읽힌다.
     물리가 도는 동안 깜빡이지 않게 뜸을 들이고, 돌아오면 즉시 사라진다.
  ⑥ 프레임이 돌지 않아도 도착한다. 약속한 것은 부드러움이 아니라 전체 보기다.
  ⑦ 빈 곳 두 번 누르기를 직접 센다 — dblclick 하나에 목숨을 걸지 않는다.
  ⑧ 재는 자와 그리는 자가 같다 — 화면 좌표(깊이 가중 포함)로 잰다.

실행: python3 tests/ graph_fit
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class GraphFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    # ---------- ① 커서 기준 줌은 옳다 ----------

    def test_cursor_anchored_zoom_is_left_alone(self):
        """표준 공식은 그대로 있어야 한다 — 고칠 것은 그 줄이 아니다."""
        self.assertIn("st.tf.x = mx - (mx - st.tf.x) * k2 / st.tf.k", self.src,
                      "커서 기준 줌 공식이 사라졌다")
        self.assertIn("st.tf.y = my - (my - st.tf.y) * k2 / st.tf.k", self.src)

    # ---------- ② 전체 보기 ----------

    def test_fit_measures_the_graph_and_leaves_a_margin(self):
        """경계 상자를 재서 여백을 두고 채운다."""
        self.assertIn("function gBBox", self.src, "경계 상자를 재지 않는다")
        fit = self._fn("gFitTf")
        self.assertIn("GFIT_PAD", fit, "여백 없이 가장자리에 붙인다")
        self.assertIn("W / 2 - b.cx * k", fit, "가운데로 맞추지 않는다")
        # 줌 한계 안에 머문다 — 노드가 하나뿐일 때 무한대로 확대되지 않는다
        self.assertRegex(self.src, r"gClampK = k => Math\.min\(4, Math\.max\(0\.25",
                         "줌 한계를 벗어난다")
        self.assertIn("gClampK", fit, "전체 보기가 줌 한계를 무시한다")

    def test_two_ways_to_reach_it(self):
        """빈 곳 더블클릭과 손잡이 버튼 — 둘 다 같은 동작으로."""
        self.assertRegex(self.src, r'addEventListener\("dblclick"[\s\S]{0,240}gFit\(\)',
                         "빈 곳 더블클릭으로 전체 보기가 안 된다")
        self.assertRegex(self.src, r'if \(hit\(mx, my\)\) return;',
                         "노드 위 더블클릭이 문서 열기와 겹친다")
        self.assertIn('class="gfit" id="gfit"', self.src, "손잡이가 없다")
        self.assertRegex(self.src, r'gfit\.addEventListener\("click"[^)]*\) => \{[^}]*gFit\(\)',
                         "손잡이를 눌러도 안 된다")
        # 조작법은 이미 있는 안내 줄에 한 항목으로 붙인다 — 새 안내를 만들지 않는다
        self.assertIn("빈 곳 더블클릭 = 전체 보기", self.src, "어떻게 하는지 어디에도 없다")

    def test_it_moves_instead_of_teleporting(self):
        """순간이동하면 어디로 갔는지 못 따라간다 — 짧게, 감속으로."""
        fn = self._fn("gFit")
        self.assertIn("REDUCE_MOTION", fn, "움직임을 줄여 달라는 설정을 무시한다")
        self.assertRegex(fn, r"ms: 2[0-4]0", "지속시간이 모션 규약(120~240ms) 밖이다")
        step = self._fn("gFitStep")
        self.assertIn("1 - Math.pow(1 - t, 3)", step, "감속(ease-out)이 아니다")
        # 손이 개입하면 옮기던 것은 멈춘다
        self.assertRegex(self.src, r"st\.fit = null;\s*//[^\n]*손이 개입",
                         "휠을 굴려도 이동이 계속된다")

    # ---------- ④ 줌아웃이 화면을 비우지 않는다 ----------

    def test_zoom_out_pulls_back_to_centre(self):
        """화면보다 작아지면 커서 기준을 놓고 가운데로 물린다."""
        w = self._wheel()
        self.assertIn("const s = gScreenBox(k2, st.tf.x, st.tf.y)", w,
                      "화면에 그려지는 자리가 아니라 월드 좌표로 잰다")
        self.assertIn("const fill = Math.max(s.w / (W - GFIT_PAD * 2), "
                      "s.h / (H - GFIT_PAD * 2))", w, "화면을 채우는 정도를 재지 않는다")
        self.assertIn("if (fill >= 1) return;", w,
                      "아직 화면을 넘치는데도 가운데로 끌어당긴다")
        self.assertIn("st.tf.x += (W / 2 - s.cx) * t", w, "가운데로 물리지 않는다")
        # 한 번에 끌어당기지 않는다 — 비율로 섞어야 톡 튀지 않는다
        self.assertRegex(w, r"const t = 0\.15 \+ 0\.5 \* \(1 - fill\)",
                         "여유와 무관하게 같은 세기로 끌어당긴다")

    # ---------- ⑤ 손잡이는 갇혔을 때만 ----------

    def test_handle_shows_only_when_the_graph_is_nearly_gone(self):
        """늘 떠 있는 안내는 곧 안 읽힌다 — 거의 나갔을 때만."""
        fn = self._fn("gAwaySync")
        self.assertRegex(fn, r"if \(seen >= 0\.25\)\{ st\.awayT = 0; btn\.hidden = true;",
                         "조금만 벗어나도 손잡이가 뜬다")
        self.assertRegex(fn, r"performance\.now\(\) - st\.awayT < 400",
                         "물리가 도는 동안 손잡이가 깜빡인다")
        self.assertIn("st.fit", fn, "옮기는 중에도 손잡이가 떠 있다")
        self.assertIn("hidden", self.src[self.src.index('class="gfit"'):
                                         self.src.index('class="gfit"') + 120],
                      "처음부터 떠 있다")

    def test_handle_measures_what_is_left_on_screen_not_box_area(self):
        """상자 넓이로 재면 확대만 해도 손잡이가 뜬다 — 그건 갇힌 게 아니다."""
        fn = self._fn("gSeen")
        self.assertIn("sxOf(n)", fn, "그리는 좌표가 아닌 것으로 잰다")
        self.assertRegex(fn, r"return on / nodes\.length",
                         "남아 있는 노드의 비율이 아니라 넓이로 잰다")

    def test_handle_wears_ink_not_a_colour_field(self):
        """색면 하이라이트·세로 띠 금지, 색은 잉크로."""
        css = self._css()
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b", "색 하드코딩 금지")
        self.assertNotRegex(css, r"\bborder-left\b", "좌측 세로 띠 금지")
        for v in re.findall(r"(?:background|color|border(?:-color)?)\s*:\s*([^;}\n]+)", css):
            v = v.strip()
            if v.startswith("1px solid "):
                v = v[len("1px solid "):]
            self.assertIn(v, ("none", "transparent", "var(--panel)", "var(--text)",
                              "var(--bg)", "var(--border)", "var(--hairline)"),
                          "잉크·지면 밖의 색: %s" % v)

    # ---------- ⑥ 프레임이 안 돌아도 도착한다 (반려 ㉠) ----------

    def test_it_arrives_even_when_no_frame_runs(self):
        """프레임은 늘 도는 것이 아니다 — 배경 탭·전원 절약·헤드리스."""
        fn = self._fn("gFit")
        self.assertIn("st.fitLand = setTimeout(", fn,
                      "옮기는 일을 프레임 루프에만 맡긴다 — 프레임이 없으면 안 움직인다")
        self.assertRegex(fn, r"if \(st\.fit && st\.fit\.to === to\)\{ st\.tf = \{\.\.\.to\}",
                         "시간이 지나도 목표 자리에 놓지 않는다")
        # 휠이 취소한 이동을 되살리면 안 된다 — 같은 이동인지 확인하고 놓는다
        self.assertIn("st.fit.to === to", fn, "취소된 이동을 되살린다")
        self.assertIn("clearTimeout(st.fitLand)", fn, "이동을 겹쳐 걸면 늦게 온 것이 덮는다")
        # 320ms = 이동(240ms)이 끝났어야 할 시각 조금 뒤
        self.assertRegex(fn, r"\}, 3[0-9]0\);", "구제 시각이 이동 시간과 어긋난다")

    # ---------- ⑦ 두 번 누르기를 직접 센다 (반려 ㉡) ----------

    def test_two_taps_are_counted_by_us_not_only_by_the_browser(self):
        """포인터를 잡아 둔 캔버스에서 dblclick 하나에 목숨을 걸지 않는다."""
        up = self.src[self.src.index('canvas.addEventListener("pointerup"'):]
        up = up[:up.index('canvas.addEventListener("dblclick"')]
        self.assertIn("st.tap", up, "두 번 누른 것을 직접 세지 않는다")
        self.assertRegex(up, r"t - st\.tap\.t < 4[0-9]0", "두 번으로 묶는 시간 기준이 없다")
        self.assertRegex(up, r"Math\.abs\(ux - st\.tap\.x\) < [0-9]+", "손떨림 허용이 없다")
        self.assertIn("gFit()", up, "두 번 눌러도 전체 보기가 불리지 않는다")
        self.assertIn("if (!panned || st.moved >= 4 || e.button !== 0)", up,
                      "노드를 끌거나 판을 옮긴 것·왼쪽이 아닌 버튼까지 두 번 누르기로 센다")
        # 브라우저가 dblclick 을 주는 환경에서 두 번 불리지 않는다
        dbl = self.src[self.src.index('canvas.addEventListener("dblclick"'):]
        self.assertIn("if (st.fit) return;", dbl[:400], "같은 손짓으로 두 번 부른다")

    # ---------- ⑧ 재는 자와 그리는 자가 같다 (반려 ㉢) ----------

    def test_it_measures_where_nodes_are_actually_drawn(self):
        """팬 오프셋은 깊이에 가중된다 — 월드 상자로 맞추면 화면에서 어긋난다."""
        box = self._fn("gScreenBox")
        self.assertIn("pfOf(n)", box, "깊이 가중을 빼고 잰다")
        self.assertIn("(tx + st.dx) * pf", box, "카메라 드리프트를 빼고 잰다")
        self.assertIn("n.r * k * (0.62 + 0.55 * n.near)", box, "노드 반지름을 빼고 잰다")
        # 전체 보기·손잡이·줌아웃 세 곳이 모두 같은 자를 쓴다
        self.assertIn("gScreenBox(k, x, y)", self._fn("gFitTf"), "전체 보기가 다른 자로 잰다")
        self.assertIn("gScreenBox", self._wheel(), "줌아웃이 다른 자로 잰다")

    def test_it_can_be_opened_without_hands(self):
        """헤드리스로 직접 보고 고칠 길 — 구석에 남은 상태·복귀·줌아웃·더블클릭."""
        for q in ("goff", "gfit", "gzoom", "gdbl"):
            self.assertIn("[?&]%s" % q, self.src, "진단 파라미터 ?%s 가 없다" % q)
        # 줌아웃 진단은 **실제 핸들러**를 태워야 증거가 된다
        self.assertIn('new WheelEvent("wheel"', self.src,
                      "줌아웃 진단이 실제 휠 경로를 지나지 않는다")
        # 더블클릭 진단도 마찬가지다 — 그 좌표에서 **실제로 이벤트를 받는 요소**를
        # 찾아 거기서 버블링시킨다. 캔버스에 바로 쏘면 위에 뭔가 덮여 있어도 통과한다.
        gd = self.src[self.src.index("if (/[?&]gdbl/"):]
        self.assertIn("document.elementFromPoint(cx, cy)", gd,
                      "덮인 요소가 있어도 진단이 통과해 버린다")
        self.assertIn('mk("dblclick", MouseEvent)', gd, "더블클릭을 실제로 하지 않는다")
        # 진단이 **죽은 판**을 재고 "잘 된다"고 말하지 않게 세대를 함께 본다
        self.assertIn("gen: myGen", self.src, "그래프 판의 세대를 표시하지 않는다")
        self.assertRegex(gd, r"gen\s+\$\{gen0\} → \$\{L\.gen\}", "세대를 보고하지 않는다")

    # ---------- helpers ----------

    def _wheel(self):
        w = self.src[self.src.index('canvas.addEventListener("wheel"'):]
        return w[:w.index("{ passive: false }")]

    def _fn(self, name):
        m = re.search(r"function %s\([^)]*\)\{[\s\S]*?\n  \}" % name, self.src)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m.group(0)

    def _css(self):
        m = re.search(r"/\* -+ 전체 보기 손잡이[\s\S]*?\*/([\s\S]*?)\n\.legend\{", self.src)
        self.assertIsNotNone(m, "손잡이 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
