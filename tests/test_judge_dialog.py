"""판정 대화상자 — 브라우저 얼굴을 이 제품의 얼굴로 (REQ-20260827-071-62x6).

사용자: "리뷰, 반려 시 작성하는 프롬프트 창도 너무 기본 브라우저 기능이라
안예쁘다. 스킨에 걸맞는 디자인으로 보이게 해줘."

REQ-20260827-056 과 정확히 같은 실패다 — 네이티브 위젯. `prompt`/`confirm`/
`alert` 는 브라우저와 OS 가 그리는 상자라 이 제품의 서체도 색도 깊이도 정렬도
하나도 쓰지 않는다. 그리고 하필 그 자리가 **판정 경로**다: 이 제품에서 가장
중요한 순간에 남의 얼굴이 나온다.

계약은 여섯이다.

  ① 네이티브 위젯이 판정 경로에 남아 있지 않다.
  ② 대화상자는 **하나**다. 입력(prompt)·예아니오(confirm)·알림(alert)은 한
     컴포넌트의 세 변형이다. 네 군데에 각각 창을 만들면 한 벌만 고쳐진다 —
     이 저장소가 반복해 겪은 실패를 화면에서 되풀이하지 않는다.
  ③ **탭을 잠그지 않는다.** 네이티브 prompt 는 브라우저를 통째로 멈춰서
     뒤의 문서를 보면서 사유를 쓸 수 없었다. 판정하는 사람이 근거를 보면서
     못 쓴다는 건 보기 문제가 아니다.
  ④ 필수 입력은 **벌주지 않는다.** 비었으면 확인이 안 눌릴 뿐, 창을 다시
     띄워 다그치지 않는다(전에는 빈 값이면 두 번째 prompt 가 떴다).
  ⑤ 키보드로 전부 된다: 열리면 입력에 포커스, Esc 로 닫기, 닫으면 원래 있던
     곳으로 포커스 복귀. **Enter 는 확인, Shift+Enter·Ctrl+Enter 는 줄바꿈**
     — 터미널 입력줄(REQ-20260827-038)과 같은 규칙이다. 처음에는 반대로
     정했다가(Enter=줄바꿈, ⌘/Ctrl+Enter=확인) 뒤집었다: 같은 화면의 두 입력
     상자에서 같은 손가락이 정반대 결과를 내면 배울 수 있는 규칙이 아니다.
  ⑥ 껍데기는 물려받되 **판의 무게는 다르다** (2026-08-27 반려). 판은 여전히
     hovercard, 버튼은 .acts 다 — 그래야 10스킨 대응이 따라온다. 다만 쪽지는
     났다 사라지는 읽기 전용이고 대화상자는 머물러 행위를 하는 판이라, 무게가
     같으면 "팝업 느낌이 덜하고 이질감이 있다"가 된다. 무게는 3단 규칙선 구조 ·
     가장자리와 부양 한 급 · 주 행동 버튼의 잉크 반전으로 준다. 색면은 금지.
  ⑦ **어느 버튼에서 열든 같은 자리에 같은 폭** (2026-08-27 반려). 1차는 누른
     버튼에 창을 물렸는데, 승인과 반려 버튼이 카드 안 다른 자리라 같은 종류의
     행위가 매번 다른 곳에 다른 크기로 떴다. 근접성으로 얻으려던 것(무엇을
     판정하는지)은 창 안의 제목이 이미 하고 있다.

실행: python3 tests/ judge_dialog
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")

# 판정 경로에서 네이티브 위젯이 사라져야 하는 자리
NATIVE = re.compile(r"(?<![.\w])(?:window\.)?(prompt|confirm|alert)\s*\(")


class JudgeDialog(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()
        # 주석·문자열 안의 낱말은 계약의 대상이 아니다 — 실행되는 줄만 본다
        self.code = re.sub(r"/\*[\s\S]*?\*/", "", self.src)
        self.code = re.sub(r"(?m)^\s*//.*$", "", self.code)

    # ---------- ① 네이티브 위젯이 없다 ----------

    def test_no_native_dialogs_left(self):
        """prompt·confirm·alert 가 실행 경로에 남아 있지 않다."""
        hits = [m.group(1) for m in NATIVE.finditer(self.code)]
        self.assertEqual(hits, [],
                         "네이티브 위젯이 남았다: %s" % ", ".join(sorted(set(hits))))

    # ---------- ② 대화상자는 하나 ----------

    def test_one_dialog_serves_all_three_shapes(self):
        """한 컴포넌트의 세 변형 — prompt·confirm·alert."""
        fn = self._fn("s9dlg")
        for kind in ("prompt", "confirm", "alert"):
            self.assertIn('"%s"' % kind, fn, "%s 변형이 없다" % kind)
        # 판을 두 벌 만들지 않는다 — DOM 에 한 번만 붙인다
        self.assertEqual(self.src.count('dlg.className = "dlg '), 1,
                         "대화상자 판이 여러 벌이다")

    def test_every_judgement_path_uses_it(self):
        """반려·전이 메모·승인 메모·취소 확인·오류 알림이 모두 이것을 쓴다."""
        for fn in ("rejectWithReason", "postStatus"):
            self.assertIn("s9dlg(", self._fn(fn), "%s 가 아직 쓰지 않는다" % fn)
        self.assertGreaterEqual(self.code.count("s9dlg({"), 6,
                                "판정 경로 일부가 아직 옛 위젯 자리에 있다")

    # ---------- ③ 뒤가 읽힌다 ----------

    def test_it_does_not_lock_the_page(self):
        """뒤의 문서를 보면서 쓸 수 있어야 한다 — 판을 덮는 막을 두지 않는다."""
        css = self._css()
        # 전면 스크림(inset:0 + 배경)은 뒤를 가린다
        for blk in re.findall(r"\.dlg[a-z]*\{([^}]*)\}", css):
            if "inset:0" in blk.replace(" ", ""):
                self.assertNotRegex(blk, r"background\s*:\s*(?!none|transparent)",
                                    "전면 막이 뒤를 가린다")
        self.assertNotIn('aria-modal="true"', self.src,
                         "모달로 선언하면 보조기술에도 뒤가 없는 것이 된다")

    def test_it_closes_when_the_screen_moves(self):
        """화면을 떠나면 창도 닫힌다 (REQ-20260827-084).

        사용자: "팝업이 탭을 옮겨다녀도 계속 떠있는건 의도된게 맞는건가?"
        아니다. 이 창은 **특정 문서를 판정하는 자리**라, 그 문서가 있던 화면을
        떠나면 무엇을 판정하는지가 사라진다. 게다가 뒤를 가리지 않는 설계라
        다른 화면 위에 유령처럼 얹힌다. 취소와 같은 취급 — 적던 사유는 버린다.
        같은 화면 안의 해시 정규화로는 닫지 않는다: 화면이 그대로인데 창만
        사라지면 그게 더 놀랍다.
        """
        fn = self._fn("applyRoute")
        self.assertIn("if (moved && dlgClose) dlgClose(null);", fn,
                      "탭을 옮겨도 창이 남는다")
        m = re.search(r"const moved = ([\s\S]*?);\n", fn)
        self.assertIsNotNone(m, "화면이 실제로 바뀌었는지 재지 않는다")
        self.assertIn("t !== tab", m.group(1), "탭 이동을 세지 않는다")
        for k in ("selectedDoc", "settingsSection", "selectedStream"):
            self.assertIn(k, m.group(1), "%s 이동을 세지 않는다" % k)
        # 닫는 자리가 정규화(replaceState)보다 뒤여야 한다 — 같은 화면 안의
        # 주소 손질로 닫히면 안 된다
        self.assertLess(fn.index("history.replaceState"), fn.index("const moved"),
                        "주소 정규화만으로 창이 닫힌다")

    def test_it_stands_in_the_same_place_at_the_same_width(self):
        """어느 버튼에서 열든 같은 자리에 같은 폭으로 선다 (2026-08-27 반려).

        1차는 누른 버튼에 창을 물려 세웠다 — 승인 버튼과 반려 버튼이 카드 안
        다른 자리에 있어 **같은 종류의 행위가 매번 다른 곳에 다른 크기로** 떴고,
        사용자가 "의도가 있는건가"라고 물었다. 무엇을 판정하는지는 창 안의
        제목이 이미 말한다.
        """
        fn = self._fn("s9dlg")
        self.assertNotRegex(fn, r"getBoundingClientRect\(\)|placeDlg\(",
                            "여는 자리에 따라 창이 옮겨 다닌다")
        self.assertNotIn("placeDlg", self.src, "자리 계산 함수가 아직 살아 있다")
        box = self._rule(".dlgbox")
        self.assertIn("position:fixed", box.replace(" ", ""), "화면에 고정되지 않는다")
        self.assertRegex(box, r"left:50%", "가로 가운데가 아니다")
        self.assertRegex(box, r"top:", "세로 자리가 고정이 아니다")
        self.assertRegex(box, r"width:min\(", "폭이 내용에 따라 달라진다")
        # 윗변 고정 — 세로 가운데 정렬이면 내용이 긴 창과 짧은 창의 윗변이 어긋난다
        self.assertNotRegex(box, r"translate\([^)]*,[^)]*-50%",
                            "세로 가운데 정렬은 창마다 윗변을 어긋나게 한다")

    # ---------- ④ 벌주지 않는다 ----------

    def test_required_disables_instead_of_re_asking(self):
        """비었으면 확인이 안 눌릴 뿐, 창을 다시 띄우지 않는다."""
        fn = self._fn("s9dlg")
        self.assertIn("disabled", fn, "빈 값일 때 확인을 막지 않는다")
        rj = self._fn("rejectWithReason")
        self.assertEqual(len(re.findall(r"s9dlg\(", rj)), 1,
                         "사유를 두 번 묻는 흐름이 남아 있다 — 그건 벌주는 흐름이다")

    # ---------- ⑤ 키보드 ----------

    def test_keyboard_contract(self):
        """열면 포커스, Esc 로 닫기, 닫으면 원래 자리로 복귀."""
        fn = self._fn("s9dlg")
        self.assertRegex(fn, r'"Escape"', "Esc 로 닫히지 않는다")
        self.assertIn(".focus()", fn, "열릴 때 포커스를 주지 않는다")
        self.assertRegex(fn, r"activeElement", "닫은 뒤 돌아갈 자리를 기억하지 않는다")

    def test_enter_confirms_and_shift_or_ctrl_enter_breaks_the_line(self):
        """같은 제품에서 같은 키가 반대로 동작하면 안 된다.

        터미널 입력줄은 REQ-20260827-038 에서 사용자가 직접 정한 대로 Enter 로
        보내고 Shift+Enter·Ctrl+Enter 로 줄을 바꾼다. 대화상자도 같아야 한다 —
        한 화면의 두 입력 상자에서 같은 손가락이 정반대 결과를 내면 배울 수 없다.
        """
        fn = self._fn("s9dlg")
        self.assertIn("textarea", fn, "한 줄 입력이면 여러 줄 사유가 죽는다")
        self.assertRegex(fn, r"e\.shiftKey \|\| e\.ctrlKey \|\| e\.metaKey",
                         "줄바꿈 키(Shift·Ctrl+Enter)를 함께 받지 않는다")
        # Ctrl+Enter 는 textarea 가 스스로 줄을 넣지 않는다 — 손으로 넣어야
        # "아무 일도 안 일어나는 키"가 되지 않는다 (터미널이 쓰는 그 손질)
        self.assertIn("selectionStart", fn, "Ctrl+Enter 에 줄을 직접 넣지 않는다")
        # Enter 단독이 확인이다
        self.assertRegex(fn, r"yes\.click\(\)", "Enter 단독이 확인을 누르지 않는다")
        # 힌트가 사용자에게 같은 규칙을 말한다
        self.assertRegex(fn, r"<kbd>Enter</kbd> 로", "확인 키를 알려 주지 않는다")
        self.assertIn("Shift+Enter", fn, "줄바꿈 키를 알려 주지 않는다")

    # ---------- ⑥ 새 어휘를 만들지 않는다 ----------

    def test_it_wears_the_existing_card_and_buttons(self):
        """이미 있는 hovercard 판과 .acts 판정 버튼을 그대로 입는다."""
        # 판은 만들 때 한 번 입는다(hovercard), 버튼은 그릴 때 입는다(.acts)
        self.assertRegex(self.src, r'dlg\.className = "dlg hovercard',
                         "카드 어휘를 재사용하지 않는다")
        self.assertIn('<div class="acts">', self._fn("s9dlg"),
                      "판정 버튼 어휘를 재사용하지 않는다")

    def test_no_colour_fill_no_side_bar_no_hardcoded_colour(self):
        """색면 하이라이트·세로 띠 금지, 색은 토큰으로만."""
        css = self._css()
        # 잉크(--text)와 지면(--panel/--bg)을 섞은 값은 색면이 아니다 — 무채의
        # 획을 한 급 옮긴 것이다. 금하는 것은 **색상**을 깐 면이다(--c-*/--t-*).
        INK = {"none", "transparent", "var(--panel)", "var(--text)", "var(--bg)",
               "var(--border)", "var(--hairline)"}
        for bg in re.findall(r"background\s*:\s*([^;}]+)", css):
            v = bg.strip()
            if v in INK:
                continue
            if v.startswith("color-mix("):
                toks = set(re.findall(r"var\(--[a-z-]+\)", v))
                self.assertTrue(toks, "색면을 깔지 않는다: %s" % bg)
                self.assertTrue(toks <= INK, "색면을 깔지 않는다: %s" % bg)
                continue
            self.fail("색면을 깔지 않는다: %s" % bg)
        self.assertNotIn("border-left", css, "좌측 세로 띠 금지")
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b", "색 하드코딩 금지")
        self.assertNotRegex(css, r"\[data-(?:skin|theme)=",
                            "특정 스킨/톤 전용 스타일이 아니다")

    def test_buttons_say_what_they_do(self):
        """확인/취소 단독 금지 — 버튼은 동사+목적이다 (s9-design 6)."""
        calls = re.findall(r"s9dlg\(\{[\s\S]{0,400}?\}\)", self.code)
        self.assertTrue(calls, "s9dlg 호출을 찾지 못했다")
        oks = re.findall(r'ok:\s*[`"\']([^`"\']+)', "\n".join(calls))
        self.assertTrue(oks, "확인 버튼 문구를 정하지 않았다")
        for label in oks:
            self.assertNotIn(label.strip(), ("확인", "OK", "예"),
                             "모호한 확인 버튼: %r" % label)

    # ---------- helpers ----------

    def _fn(self, name):
        m = re.search(r"(?:async )?function %s\([^)]*\)\{[\s\S]*?\n\}" % name, self.src)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m.group(0)

    def _rule(self, sel):
        """선택자 하나의 선언 블록 — 여러 규칙에 나뉘어 있으면 이어 붙인다."""
        css = self._css()
        blks = re.findall(re.escape(sel) + r"\{([^}]*)\}", css)
        self.assertTrue(blks, "%s 규칙을 찾지 못했다" % sel)
        return ";".join(blks)

    def _css(self):
        m = re.search(r"/\* -+ 판정 대화상자[\s\S]*?\*/([\s\S]*?)\n\n", self.src)
        self.assertIsNotNone(m, "판정 대화상자 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
