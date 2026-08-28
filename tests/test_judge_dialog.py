"""판정 대화상자 — 브라우저 얼굴을 이 제품의 얼굴로 (REQ-20260827-071-62x6).

사용자: "리뷰, 반려 시 작성하는 프롬프트 창도 너무 기본 브라우저 기능이라
안예쁘다. 스킨에 걸맞는 디자인으로 보이게 해줘."

REQ-20260827-056 과 정확히 같은 실패다 — 네이티브 위젯. `prompt`/`confirm`/
`alert` 는 브라우저와 OS 가 그리는 상자라 이 제품의 서체도 색도 깊이도 정렬도
하나도 쓰지 않는다. 그리고 하필 그 자리가 **판정 경로**다: 이 제품에서 가장
중요한 순간에 남의 얼굴이 나온다.

계약은 여덟이다.

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
     곳으로 포커스 복귀. **여러 줄 쓰는 상자에서는 Enter 가 줄바꿈이고
     ⌘/Ctrl+Enter 가 확인이다** (REQ-20260828-007 로 되돌림).

     이 계약은 두 번 뒤집혔다. 1차(071)에 Enter=줄바꿈으로 만들었고, "터미널
     입력줄과 같은 손버릇이어야 한다"는 이유로 Enter=확인으로 뒤집었다가,
     사용자가 겪고 되돌렸다: "판정 메시지 입력란이 큰데, 엔터키를 누르면
     줄바꿈이 아니라 승인이든, 반려든 메시지가 전송이 되어 버린다."

     뒤집었던 논거가 틀렸다. 터미널 입력줄은 **한 줄짜리 보내기 상자**고 이
     창은 **여러 줄 짜는 상자**다. 상자의 성격이 다르면 키도 다른 것이 맞다.
     그리고 잘못 눌렀을 때의 값이 다르다 — 채팅은 한 줄 더 치면 되지만 판정은
     문서의 상태를 옮겨 버린다. 되돌릴 수 없는 쪽에 더 어려운 키를 준다.
  ⑥ 껍데기는 물려받되 **판의 무게는 다르다** (2026-08-27 반려). 판은 여전히
     hovercard, 버튼은 .acts 다 — 그래야 10스킨 대응이 따라온다. 다만 쪽지는
     났다 사라지는 읽기 전용이고 대화상자는 머물러 행위를 하는 판이라, 무게가
     같으면 "팝업 느낌이 덜하고 이질감이 있다"가 된다. 무게는 3단 규칙선 구조 ·
     가장자리와 부양 한 급 · 주 행동 버튼의 잉크 반전으로 준다. 색면은 금지.
  ⑦ **어느 버튼에서 열든 같은 자리에 같은 폭** (2026-08-27 반려). 1차는 누른
     버튼에 창을 물렸는데, 승인과 반려 버튼이 카드 안 다른 자리라 같은 종류의
     행위가 매번 다른 곳에 다른 크기로 떴다. 근접성으로 얻으려던 것(무엇을
     판정하는지)은 창 안의 제목이 이미 하고 있다.
  ⑨ **화면은 '전이'라고 말하지 않는다. 상태 이름은 번역하지 않는다**
     (REQ-20260828-007 반려). 사용자: "승인,반려에 대한 판정인데, 전이 라는
     용어가 갑자기 등장한다. 그리고 다른 상태에서는 open, in-progress, done인데
     리뷰 단계에서만 … 한글로 승인/반려 라고 표시된다. 용어를 통일할 필요가 있다."

     두 갈래로 답한다.
     (a) '전이'는 코드·CLI 가 쓰는 말이라 화면에서 지운다. 창머리는 '판정' 하나로
         모은다 — 승인·반려·상태 옮기기·취소는 다 같은 성격의 행위다.
     (b) `done`·`in-progress` 는 **번역하지 않는다.** 그 글자는 화면에만 있는 것이
         아니라 문서 앞머리·CLI 출력·커밋 메시지에 같은 글자로 박혀 있다. 화면만
         한글로 바꾸면 화면에서 본 말과 문서에서 읽는 말이 달라진다. 대신 **이름은
         이름처럼(mono 식별자), 행위는 행위처럼(문장 속 동사)** 보이게 해서 같은
         줄에 서도 헷갈리지 않게 한다. 그리고 승인하면 무엇이 되는지를 귀띔이
         아니라 **창 안 문장**에 넣는다.

  ⑧ **무엇을 판정하는지 창 안에서 읽힌다** (REQ-20260828-007). 사용자:
     "팝업에 표시되는 문서제목이 코드로만 보이고, 제목은 보이지 않아서 무엇에
     대해서 판정하려 했는지 모르겠다." 넷(반려·승인·전이·취소)이 각자 문장을
     지어 쓰다 넷 다 id 만 적고 있었다 — 한 곳(dlgFor)에서 짓는다. 주소는 카드가
     그러듯 작은 글씨로 머리에, 제목은 본문에 크게. 아주 긴 제목은 자르되
     **뒤따르는 동사가 잘려 나가지 않을 만큼만** 자른다.

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
        """화면을 떠나면 창도 닫힌다 (REQ-20260827-084 → REQ-20260828-007 재작업).

        사용자: "팝업이 탭을 옮겨다녀도 계속 떠있는건 의도된게 맞는건가?"
        아니다. 이 창은 **특정 문서를 판정하는 자리**라, 그 문서가 있던 화면을
        떠나면 무엇을 판정하는지가 사라진다.

        **계약을 다시 쓴 이유**: 1차 고침은 `applyRoute` 안에서 "화면이 바뀌었나"를
        셌고, 이 테스트는 그 셈식(`const moved = …`)의 모양을 검사했다. 그런데
        사람이 화면을 옮기는 길 셋(헤더 탭 버튼·문서 링크/카드·그래프 노드)은
        **하나도 applyRoute 를 거치지 않는다** — 전부 tab/selectedDoc 을 직접 바꾸고
        pushRoute() 를 부른다. applyRoute 는 첫 진입과 뒤로가기에서만 돈다. 그래서
        테스트도 진단(?dlgnav)도 통과했는데 사용자는 계속 겪었다: 검사한 것이
        **사람이 쓰지 않는 길**이었다.

        그래서 특정 함수의 셈식이 아니라 **동작의 성질**을 계약으로 둔다:
        창은 열릴 때 화면 이름을 적어 두고, 화면이 바뀔 수 있는 길목마다 견줘
        다르면 닫는다. 15초 카탈로그 갱신처럼 화면 이름이 그대로인 재그리기에는
        닫히지 않는다 — 사유를 쓰는 중에 창이 사라지면 그게 더 나쁘다.
        """
        # 창이 매인 화면을 열 때 적어 둔다 — prompt 판과 고르는 판 둘 다
        self.assertEqual(self.code.count("dlgAt = dlgScreen()"), 2,
                         "창이 어느 화면에서 열렸는지 적어 두지 않는다")
        chk = self._fn("dlgCheckNav")
        self.assertIn("dlgScreen() !== dlgAt", chk,
                      "열린 화면과 지금 화면을 견주지 않는다")
        self.assertIn("dlgClose(null)", chk, "달라도 닫지 않는다")
        # 화면 이름에는 탭뿐 아니라 **같은 탭 안의 대상**도 들어간다 — docs 탭에서
        # 다른 문서로 옮겨 가는 것도 화면 이동이다
        scr = self._fn("dlgScreen")
        for k in ("tab", "selectedDoc", "selectedStream", "settingsSection"):
            self.assertIn(k, scr, "%s 이동을 세지 않는다" % k)
        # 길목 둘: 화면을 옮기는 모든 손이 지나는 pushRoute, 그리고 그리는 자리
        self.assertIn("dlgCheckNav()", self._fn("pushRoute"),
                      "탭 버튼·문서 링크·그래프 노드 클릭 경로에서 닫히지 않는다")
        self.assertIn("dlgCheckNav()", self._fn("render"),
                      "다시 그릴 때 화면이 바뀐 것을 보지 않는다")
        self.assertIn("dlgCheckNav()", self._fn("applyRoute"),
                      "뒤로가기로 옮겨도 창이 남는다")

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

    def test_enter_breaks_the_line_and_cmd_enter_confirms(self):
        """여러 줄 쓰는 상자에서 Enter 는 줄바꿈이다 (REQ-20260828-007).

        **계약을 다시 쓴 이유**: 앞선 계약(Enter=확인)은 "터미널 입력줄과 같은
        손버릇"을 근거로 삼았다. 그 근거가 틀렸다 — 터미널 입력줄은 한 줄짜리
        보내기 상자고 이 창은 여러 줄 짜는 상자다. 사용자가 겪은 것: "판정 메시지
        입력란이 큰데, 엔터키를 누르면 줄바꿈이 아니라 승인이든, 반려든 메시지가
        전송이 되어 버린다." 채팅에서 잘못 누르면 한 줄 더 치면 되지만, 여기서
        잘못 누르면 문서의 상태가 옮겨진다. 값이 큰 쪽에 더 어려운 키를 준다.
        """
        fn = self._fn("s9dlg")
        self.assertIn("textarea", fn, "한 줄 입력이면 여러 줄 사유가 죽는다")
        # 쓰는 창에서 맨 Enter 는 **가로채지 않는다** — textarea 가 줄을 넣는다
        m = re.search(r"if \(ask\)\{([\s\S]*?)\n      \}", fn)
        self.assertIsNotNone(m, "쓰는 창의 Enter 처리를 찾지 못했다")
        self.assertIn("!(e.ctrlKey || e.metaKey)", m.group(1),
                      "수식키 없는 Enter 를 그냥 흘려보내지 않는다")
        self.assertNotIn("selectionStart", fn,
                         "줄을 손으로 끼워 넣을 이유가 없다 — 이제 기본 동작이다")
        # ⌘/Ctrl+Enter 가 확인이다
        self.assertRegex(fn, r"yes\.click\(\)", "확인을 누르는 자리가 없다")
        # 힌트가 사용자에게 같은 규칙을 말한다 — 자판에 새겨진 글자로
        self.assertRegex(fn, r"<kbd>\$\{DLG_CMD\}\+Enter</kbd> 로",
                         "확인 키를 알려 주지 않는다")
        self.assertRegex(fn, r"<kbd>Enter</kbd> 로 줄바꿈", "줄바꿈 키를 알려 주지 않는다")
        self.assertRegex(self.code, r'DLG_CMD = [\s\S]{0,120}Mac[\s\S]{0,120}"⌘"',
                         "맥에서 Ctrl 이라고 적으면 힌트가 거짓말이 된다")

    def test_it_says_which_document_is_being_judged(self):
        """제목이 창 안에서 읽힌다 (REQ-20260828-007 ⑧).

        사용자: "팝업에 표시되는 문서제목이 코드로만 보이고, 제목은 보이지 않아서
        무엇에 대해서 판정하려 했는지 모르겠다."
        """
        # 문장을 짓는 곳은 하나다 — 넷이 각자 지으면 언젠가 하나만 제목을 잃는다
        mk = self._fn("dlgFor")
        self.assertIn("catFind(", mk, "카탈로그에서 제목을 찾지 않는다")
        self.assertIn("「", mk, "제목을 이름으로 감싸지 않는다")
        self.assertIn("doc: shortId(", mk, "주소를 머리에 넘기지 않는다")
        # 긴 제목은 자르되 뒤따르는 동사를 밀어내지 않는다
        self.assertRegex(mk, r"t\.length > \d+", "긴 제목을 자르지 않는다")
        self.assertIn("…", mk, "잘렸다는 표시가 없다")
        # 판정·전이 넷이 모두 이것을 쓴다
        for fn in ("rejectWithReason",):
            self.assertIn("dlgFor(", self._fn(fn), "%s 가 제목을 말하지 않는다" % fn)
        self.assertGreaterEqual(self.code.count("dlgFor("), 5,
                                "판정 경로 일부가 아직 id 만 적는다")
        # 주소는 카드의 .id 와 같은 어휘로 머리에 선다
        self.assertIn('class="dlgdoc"', self._fn("s9dlg"), "주소를 머리에 두지 않는다")
        rule = self._rule(".dlgdoc")
        self.assertIn("var(--mono)", rule, "주소가 mono 가 아니다")
        self.assertIn("text-overflow:ellipsis", rule, "긴 주소가 머리를 밀어낸다")

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

    # ---------- ⑨ 용어 ----------

    def test_the_screen_never_says_the_internal_word(self):
        """'전이'는 코드가 쓰는 말이지 사람에게 보여 줄 말이 아니다."""
        # 실행되는 줄(주석 제거)에 남은 '전이'는 곧 화면에 뜨는 글자다
        # 줄 끝에 달린 `//` 주석도 걷어낸다 — 남은 것만이 화면에 뜨는 글자다
        lines = [re.sub(r"\s//.*$", "", ln) for ln in self.code.split("\n")]
        bad = [ln.strip() for ln in lines
               if "전이" in ln and "반전이" not in ln and "진전이" not in ln]
        self.assertEqual(bad, [], "화면 문구에 '전이'가 남았다: %s" % bad[:3])

    def test_state_names_are_not_translated(self):
        """상태 이름은 이름이다 — 문서·CLI·커밋과 같은 글자여야 한다."""
        # 창머리는 하나로 모인다
        caps = set(re.findall(r'cap:\s*"([^"]+)"', self.code))
        self.assertIn("판정", caps)
        # 상태를 **이름의 자리에** 그릴 때는 식별자를 그대로 쓴다. (낱말 자체를
        # 금할 수는 없다 — "하루 안에 완료된 요청 없음" 같은 문장에서 그 낱말은
        # 상태의 이름이 아니라 우리말 서술어다. 금하는 것은 이름 자리의 번역이다.)
        self.assertIn('"→ " + to', self.code,
                      "상태 버튼이 식별자를 그대로 쓰지 않는다")
        # 승인/반려 창은 **어느 상태로 가는지**를 창 안 문장에서 말한다
        rj = self._fn("rejectWithReason")
        self.assertIn('stName("in-progress")', rj, "반려가 어디로 가는지 말하지 않는다")
        self.assertIn('stName("done")', self.code, "승인이 어디로 가는지 말하지 않는다")
        # 이름은 mono 로 선다
        self.assertRegex(self.src, r"\.dlgst\{[^}]*var\(--mono\)",
                         "문장 속 상태 이름이 이름처럼 보이지 않는다")

    def test_names_and_deeds_do_not_look_alike(self):
        """`→ done` 은 이름이고 `✓ 승인` 은 사람이 하는 일이다 — 글꼴로 가른다."""
        m = re.search(r"\.acts button\.deed\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, "행위 버튼이 이름과 같은 글꼴로 선다")
        self.assertIn("font-family:inherit", m.group(1), "행위가 mono 로 그려진다")
        self.assertIn("letter-spacing:0", m.group(1), "한글에 트래킹이 걸려 있다")
        # 보드 판정 카드·문서 본문 둘 다 그 옷을 입는다
        self.assertRegex(self.code, r'class="deed" data-approve', "보드 승인 버튼")
        self.assertRegex(self.code, r'class="deed" data-reject', "보드 반려 버튼")
        self.assertIn('rv ? "deed" : ""', self.code,
                      "문서 본문에서 이름과 행위가 같은 옷을 입는다")

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
