"""고른 문서는 **제자리에서 살짝** 구분된다 (REQ-20260831-007).

이 파일은 `tests/test_doc_pin_release.py` 를 **대체한다** — 그 파일이 지키던
규칙("지금 보는 문서를 목록 맨 위에 못 박는다", REQ-20260828-009 → -20260829-012)을
사용자가 뒤집었기 때문이다. 뒤집힌 규칙을 지키는 시험을 남겨 두면 회귀 그물이
사용자의 최신 판정과 반대편에 선다.

사용자: "docs 탭에서 좌측 문서에서 현재 보고 있는 문서를 최상단 row 로 하나
뽑기보다는 그냥 목록들 사이에서 살짝 강조만 되면 좋을 것 같다. 그리고 좌측 문서
목록들을 번갈아가면서 선택하다보면 문서 목록이 자꾸 바뀐다."

## 둘은 같은 하나였다

실브라우저(CDP)로 잰 것: 목록 id 배열을 A→B→A→B 로 갈아타며 찍었더니 매번
달라졌다. 원인은 폴링도, 정렬 축도 아니었다 — 순서 얼림(stableOrder)은 15초
폴링을 35초 관찰해도 흔들리지 않았다. 흔든 것은 **못 박기 자체**다: 고른 줄을
제 무리에서 빼내 맨 위에 세우므로, A 에서 B 로 옮기면 A 가 제자리로 돌아가고
B 가 빠져나가 그 사이의 줄이 전부 한 칸씩 밀린다.

## 못 박기가 풀려던 문제는 다른 길로 푼다

"묻혀 있으면 못 찾는다"(009)는 참이다. 자리를 옮기는 대신 **보이게** 한다 —
한도(20) 밖이면 거기까지 펴고(docReach, 줄지 않는다), 사람이 방금 고른 것이면
그 줄로 스크롤한다(붙박이 타입바 두께만큼 물러서서).

실행: python3 tests/ doc_place_emphasis
"""
import os
import re
import unittest
from webasset import index_path

INDEX = index_path()


def rules_for(src, needle):
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"(?m)^([^\n{}]+)\{([^{}]*)\}", src)
            if needle in m.group(1)]


class DocPlaceEmphasis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r"async function renderDocs\(rows\)\{(.+?)\n\}\n", cls.src, re.S)
        assert m, "renderDocs 를 찾지 못했다"
        cls.rd = m.group(1)

    # --- ① 뽑아 올리지 않는다 ---

    def test_nothing_is_lifted_out_of_its_group(self):
        """고른 줄을 무리에서 빼내는 순간 목록은 고를 때마다 흔들린다."""
        self.assertNotIn("const pin = selectedDoc", self.rd,
                         "고른 문서를 따로 뽑아내는 길이 남아 있다")
        self.assertNotIn("rowHTML(pin)", self.rd, "뽑은 줄을 맨 위에 세우고 있다")
        self.assertNotIn("pinhead", self.src, "뽑은 줄의 머리글이 남아 있다")

    def test_every_row_goes_into_its_group(self):
        """무리 나누기에 예외가 없어야 자리가 사람의 선택과 무관해진다.

        고정할 성질은 **"고른 줄을 예외로 두지 않는다"** 하나다 — 어느 무리가
        서는지(선언한 다섯인지, 만나는 대로 만드는지)는 다른 축의 결정이고,
        REQ-20260831-026 이 프로젝트를 제 탭으로 보내면서 그 축이 바뀌었다."""
        m = re.search(r"ordered\.forEach\(([\s\S]{0,160}?)\);\n", self.rd)
        self.assertTrue(m, "무리 나누기 한 줄을 못 찾았다")
        body = m.group(1)
        self.assertIn("groups[r.type]", body, "무리로 나누지 않는다")
        for word in ("selectedDoc", "sel", "pin"):
            self.assertNotIn(word, body,
                             "무리 나누기가 선택을 예외로 두고 있다: %s" % word)

    def test_the_freeze_rule_is_untouched(self):
        """순서 얼림은 이번 개편이 건드리지 않는다 — 15초마다 순서가 뒤섞이면
        REQ-20260828-009 가 고친 결함이 돌아온다.

        묻는 것은 "**판이 이미 서 있나**" 하나다. 판을 찾는 셀렉터에 주인 이름이
        붙은 것은 REQ-20260831-026 이 같은 셸을 쓰는 탭을 하나 더 세웠기 때문이고
        (그 이름이 없으면 남의 판을 제 것으로 착각한다), 얼음의 뜻은 그대로다."""
        self.assertRegex(
            self.src,
            r'const refreeze = !\(\$\(\'#view \.docs\[data-pane="docs"\] \.doclist\'\)'
            r' && \$\("#viewer"\)\);',
            "얼음 조건이 바뀌었다")

    # --- ② 제자리에서 살짝 ---

    def test_the_mark_is_ink_not_a_field(self):
        """이 화면이 금하는 둘: 색면 하이라이트 · 왼쪽 세로 띠. 남는 것은 잉크다."""
        base = dict(rules_for(self.src, ".doclist .row.sel"))
        rest = [c for s, c in base.items()
                if s.endswith(".row.sel:not(:hover)") or s.endswith(".row.sel")]
        self.assertTrue(rest, "고른 줄의 쉼 얼굴이 정해져 있지 않다")
        flat = "".join(rest).replace(" ", "")
        self.assertIn("background:none", flat, "쉼 얼굴에 면이 깔렸다")
        for sel, body in base.items():
            b = body.replace(" ", "")
            self.assertNotIn("border-left", b, "왼쪽 세로 띠는 금지다: " + sel)
            self.assertNotRegex(b, r"box-shadow:inset\d*px",
                                "왼쪽 세로 띠(inset 바)는 금지다: " + sel)

    def test_the_mark_the_ink_and_the_weight_all_stand(self):
        """살짝이되 셋이 함께여야 이웃 스무 줄 사이에서 읽힌다."""
        self.assertRegex(self.src, r'\.doclist \.row\.sel \.id::before\{content:"●"',
                         "지금 이것을 가리키는 표식이 없다")
        self.assertRegex(self.src, r"\.doclist \.row\.sel \.id\{color:var\(--text\)\}",
                         "고른 줄의 번호가 이웃과 같은 잉크다")
        self.assertRegex(self.src, r"\.doclist \.row\.sel>div:nth-child\(3\)\{font-weight:",
                         "고른 줄의 제목이 이웃과 같은 굵기다")

    def test_the_mark_inherits_its_ink(self):
        """줄을 통째로 잉크로 반전하는 스킨(terminal)에서 값을 박은 ● 는 배경과
        같은 색이 되어 사라진다 — `.row.sel *` 의 !important 는 의사요소에 닿지
        않는다. 물려받으면 어느 스킨에서도 그 스킨의 대비를 그대로 쓴다."""
        m = re.search(r"\.doclist \.row\.sel \.id::before\{([^}]*)\}", self.src)
        self.assertIsNotNone(m)
        self.assertIn("color:currentColor", m.group(1).replace(" ", ""),
                      "● 의 색을 박아 두었다")

    def test_the_hovered_face_is_not_swallowed(self):
        """쉼 얼굴의 면만 걷는다. `:not(:hover)` 없이 쓰면 바로 위 줄의 hover
        틴트까지 삼켜, 고른 줄만 손이 얹혀도 대꾸가 없는 죽은 줄이 된다."""
        for sel, body in rules_for(self.src, ".doclist .row.sel"):
            if "background:none" in body.replace(" ", ""):
                self.assertIn(":not(:hover)", sel,
                              "고른 줄이 hover 얼굴을 잃는다: " + sel)

    # --- ③ 묻히지 않게 하되, 자리는 그대로 ---

    def test_the_reach_only_grows(self):
        """한도 밖 문서를 열어 무리를 폈다가 다음 선택에서 도로 짧아지면,
        뽑아 올리기를 걷어내고도 목록이 다시 흔들린다."""
        self.assertRegex(self.src, r"(?m)^let docReach", "펴 놓은 만큼의 기억이 없다")
        self.assertRegex(self.rd, r"docReach\[g\] = Math\.max\(docReach\[g\] \|\| 0, si \+ 1\)",
                         "펴 놓은 자리가 줄어들 수 있다")
        self.assertRegex(self.rd, r"if \(refreeze \|\| docReachKey !== okey\)",
                         "조건이 바뀌어도 옛 폄이 남는다")

    def test_the_eye_moves_not_the_row(self):
        """자리를 옮기는 대신 눈을 그 자리로 옮긴다 — 그리고 배경 갱신마다
        움직이면 읽으려고 내려 둔 목록을 판이 도로 끌어올린다."""
        self.assertRegex(self.rd, r"if \(selectedDoc && \(fresh \|\| refreeze\)\)",
                         "사람이 고른 때와 배경 갱신을 가르지 않고 스크롤한다")
        self.assertIn('scrollIntoView({block: "nearest"})', self.rd,
                      "고른 줄을 화면 안으로 들이지 않는다")

    def test_the_sticky_bar_does_not_bury_the_row(self):
        """붙박이(타입바·무리 머리글)는 자리를 비워 두지 않는다 — 그 두께만큼
        물러서지 않으면 방금 연 문서가 스크롤되고도 타입바 밑에 깔린다(실측)."""
        m = re.search(r"(?m)^\.doclist \.row\{([^{}]*)\}", self.src, re.S)
        self.assertIsNotNone(m, "목록 행 규칙을 찾지 못했다")
        body = m.group(1)
        self.assertIn("scroll-margin-top", body.replace(" ", ""),
                      "붙박이 두께만큼 물러서지 않는다")
        self.assertIn("--tbh", body, "타입바 높이를 실측값으로 쓰지 않는다")

    # --- ④ 풀 수 있다 (REQ-20260829-012 가 세운 능력) ---

    def test_the_release_handle_lives_in_the_row(self):
        """푸는 손잡이는 푸는 대상 위에 산다. 머리글이 사라졌으니 자리도 따라
        옮긴다 — 고른 줄 자신의 번호 칸 끝이다. 오른쪽 문서 판에 두면 승인·반려
        옆에 서서 '요청을 닫는다(완료)'로 읽힌다."""
        m = re.search(r"const rowHTML = r => \{(.+?)\n  \};", self.rd, re.S)
        self.assertIsNotNone(m, "목록 행을 짓는 자리를 찾지 못했다")
        self.assertIn("data-seloff", m.group(1), "손잡이가 줄 안에 없다")
        self.assertRegex(m.group(1), r'const off = on \?',
                         "손잡이가 고른 줄에만 서지 않는다")

    def test_the_handle_is_caught_before_the_row(self):
        """줄 안에 있으므로, 먼저 잡히지 않으면 놓으려던 누름이 그 문서를 다시
        여는 누름이 된다."""
        self.assertRegex(self.src, r'closest\("\[data-seloff\]"\)',
                         "손잡이를 눌러도 아무 일도 일어나지 않는다")
        off = self.src.index('closest("[data-seloff]")')
        row = self.src.index('closest("[data-doc]")')
        self.assertLess(off, row, "행을 여는 길이 손잡이보다 먼저 잡힌다")

    def test_the_handle_is_ink_and_reachable_by_keyboard(self):
        """색면·테두리 없는 mono 글자 + hover 밑줄 — `+ N개 더 보기` 와 같은 어휘.
        진짜 button 이라 Tab 으로 닿고 Enter 로 눌린다."""
        self.assertRegex(self.src, r'<button type="button" class="seloff"',
                         "손잡이가 진짜 button 이 아니다")
        body = dict(rules_for(self.src, ".seloff"))
        base = [c for s, c in body.items() if s.endswith(".seloff")]
        self.assertTrue(base, ".seloff 규칙이 없다")
        flat = base[0].replace(" ", "")
        self.assertIn("background:none", flat)
        self.assertIn("border:0", flat)
        self.assertIn("color:inherit", flat, "잉크를 박으면 반전 스킨에서 묻힌다")
        self.assertTrue(any(":focus-visible" in s for s in body),
                        "키보드로 닿은 자리가 보이지 않는다")

    def test_the_handle_does_not_change_the_row_height(self):
        """고르는 순간 줄 높이가 변하면 그것이 곧 목록이 흔들리는 것이다."""
        body = dict(rules_for(self.src, ".seloff"))
        base = [c for s, c in body.items() if s.endswith(".seloff")][0].replace(" ", "")
        self.assertIn("font-size:10px", base, "번호 칸보다 큰 글자가 줄을 키운다")
        self.assertIn("line-height:inherit", base)

    def test_letting_go_clears_the_selection_everywhere(self):
        """푼다는 것은 주소에서도 빠진다는 뜻이다 — 새로고침에 되살아나면 안 푼 것이다."""
        m = re.search(r"function docDeselect\(\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "선택을 푸는 함수가 없다")
        fn = m.group(1)
        self.assertIn("selectedDoc = null", fn)
        self.assertIn("pushRoute()", fn, "주소에 문서가 남아 새로고침하면 되살아난다")

    def test_letting_go_shows_the_empty_state(self):
        """오른쪽 판이 방금 푼 문서를 계속 그리고 있으면 아무것도 안 푼 것이다."""
        m = re.search(r"function docDeselect\(\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("문서를 선택하세요", m.group(1),
                      "푼 뒤에 오른쪽이 무엇을 보여 주는지 정해지지 않았다")

    # --- 물려받은 규율 (REQ-20260829-012 에서 그대로 옮겨 온다) ---

    def test_switching_documents_rebuilds_the_list(self):
        """`loadDoc` 만 부르는 길이 남으면 표식이 지난 문서에 붙들린다."""
        m = re.search(r"function docOpen\(id\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "docOpen 을 찾지 못했다")
        fn = m.group(1)
        self.assertIn("render()", fn, "문서를 바꿔도 목록을 다시 그리지 않는다")
        self.assertNotIn("loadDoc(", fn, "목록을 건너뛰고 뷰어만 갈아 끼우는 길이 남아 있다")

    def test_the_human_path_and_the_poll_path_stay_apart(self):
        """사람이 누른 것은 위에서부터 새로 펴고, 15초 폴링은 읽던 자리를 지킨다."""
        self.assertRegex(self.src, r"(?m)^let docFresh",
                         "사람이 고른 경로를 구별하는 표시가 없다")
        self.assertRegex(self.rd, r"const fresh = docFresh; docFresh = false;",
                         "겹친 렌더가 서로의 표시를 가져간다 — 맨 위에서 읽고 끈다")
        self.assertIn("loadDoc(selectedDoc, !fresh)", self.rd,
                      "사람이 고른 문서도 배경 갱신처럼 연다")

    def test_the_switch_can_be_reproduced_without_hands(self):
        """이 결함은 **누른 순간에만** 났다 — 갈아타 볼 길이 없으면 다음에 또
        코드만 읽고 넘어간다."""
        self.assertIn("[?&]swap=", self.src, "문서를 갈아탄 화면을 세워 볼 길이 없다")
        self.assertRegex(self.src, r"docOpen\(r\.id\)")

    def test_escape_does_not_drop_the_document(self):
        """Esc 는 떠 있는 것을 닫는 키다. 판의 상태까지 지우면 호버카드를
        닫으려고 누른 Esc 가 읽던 문서를 되돌리기 없이 지운다."""
        m = re.search(r'if \(e\.key !== "Escape"\) return;(.+?)\}\);', self.src, re.S)
        self.assertIsNotNone(m, "전역 Escape 핸들러를 찾지 못했다")
        self.assertNotIn("selectedDoc", m.group(1),
                         "Esc 가 문서 선택까지 지운다 — 같은 키에 두 층이 얹혔다")
        self.assertNotIn("docDeselect", m.group(1))


if __name__ == "__main__":
    unittest.main()
