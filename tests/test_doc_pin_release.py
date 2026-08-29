"""못 박은 줄은 **목록의 첫 항목이 아니다** — 그리고 풀 수 있어야 한다 (REQ-20260829-012).

사용자: "docs 탭에서 문서 목록이나 문서 선택이 내 의도와 다른 것 같다.
그리고 선택한 문서를 취소할 수도 있게 해줘."

캡처에서 본 것: Docs 탭에 들어가자 예전에 열어 뒀던 REQ-20260827-067(cancelled)이
목록 맨 위, REQUEST 머리글 **위**에 홀로 서 있다. 지금 고른 적이 없는데 목록의
첫 줄처럼 보인다.

## 못 박기는 남는다 — 경계를 긋는다

REQ-20260828-009 의 결정("지금 보는 문서를 맨 위에 못 박는다")은 옳고 그대로
둔다. 묻혀 있으면 못 찾는다. 뒤집을 것은 그 줄의 **정체**다.

  못 박기는 "내가 고른 것"의 표시가 아니라 **"지금 오른쪽에 열려 있는 것"**의
  표시다.

그 경계를 지키면 되살아난 선택도 여전히 맨 위에 서야 한다 — 오른쪽 판이 실제로
그 문서를 그리고 있으니, 목록이 그것을 숨기면 두 판이 서로 다른 말을 한다(009 가
고친 바로 그 결함이다). 고칠 것은 둘이다.

  ① 그 줄이 **무엇인지 말한다.** 이 목록의 덩어리는 전부 머리글을 갖는다
     (REQUEST·ARTICLE·KNOWLEDGE…). 못 박은 줄만 없어서 목록의 1번으로 읽혔다.
     같은 문법(.grp — sticky · mono · 하단 헤어라인)으로 머리글 하나를 준다.
  ② **풀 수 있다.** 그 머리글 안에 닫는 손잡이를 둔다.

## Esc 는 쓰지 않는다

이 저장소에서 Esc 는 **떠 있는 것**을 닫는 키다 — 호버카드·터미널 미리보기·
대화상자·팔레트가 전부 그 층이고, 전역 핸들러 하나가 그 층만 걷는다. 문서 선택은
떠 있는 것이 아니라 **판의 상태**이고, 오른쪽 화면 전체가 그것이다. 같은 키에 두
층을 얹으면 떠 있는 것을 닫으려고 누른 Esc 가 읽던 문서까지 지운다 — 되돌리기
없이. 대신 손잡이가 키보드로 닿는다(Tab → Enter).

실행: python3 tests/ doc_pin_release
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


def rules_for(src, needle):
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"(?m)^([^\n{}]+)\{([^{}]*)\}", src)
            if needle in m.group(1)]


class DocPinRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r"async function renderDocs\(rows\)\{(.+?)\n\}\n", cls.src, re.S)
        assert m, "renderDocs 를 찾지 못했다"
        cls.rd = m.group(1)

    # --- ① 못 박기는 남되, 그 줄이 무엇인지 말한다 ---

    def test_the_pin_itself_stays(self):
        """REQ-20260828-009 의 결정은 뒤집지 않는다 — 묻히면 못 찾는다."""
        self.assertIn("const pin = selectedDoc", self.rd, "못 박기가 사라졌다")
        self.assertRegex(self.rd, r"if \(pin\) list \+=", "못 박은 줄을 맨 위에 세우지 않는다")

    def test_the_pinned_row_gets_a_header(self):
        """머리글 없는 줄은 목록의 1번으로 읽힌다 — 실제로 그렇게 읽혔다."""
        self.assertIn("pinhead", self.rd,
                      "못 박은 줄에 머리글이 없다 — 목록의 첫 항목과 구별되지 않는다")
        m = re.search(r"if \(pin\) list \+= (.+?);", self.rd, re.S)
        self.assertIsNotNone(m, "못 박은 줄을 세우는 자리를 찾지 못했다")
        line = m.group(1)
        self.assertLess(line.index("pinhead"), line.index("rowHTML(pin)"),
                        "머리글이 줄 아래에 붙었다 — 머리글은 위다")

    def test_the_header_speaks_the_lists_own_grammar(self):
        """새 컴포넌트를 만들지 않는다 — 이 목록이 이미 쓰는 머리글(.grp) 그대로."""
        self.assertRegex(self.src, r'class="grp[^"]*pinhead',
                         "머리글이 이 목록의 머리글 문법을 쓰지 않는다")

    def test_the_label_is_not_a_type_name(self):
        """머리글이 타입 이름(request/knowledge…)처럼 보이면 또 하나의 덩어리로
        읽힌다 — 이 줄은 덩어리가 아니라 '오른쪽에 열려 있는 것'이다."""
        m = re.search(r"const PIN_HEAD_LABEL = \"([^\"]+)\"", self.src)
        self.assertIsNotNone(m, "머리글 낱말이 한 곳에 모여 있지 않다 (ux-writer 가 고칠 자리)")
        self.assertNotIn(m.group(1).lower(),
                         ("request", "article", "knowledge", "question", "session"))

    # --- ② 풀 수 있다 ---

    def test_there_is_a_way_to_let_go(self):
        """고른 문서를 푸는 길이 없었다."""
        self.assertIn("data-pinoff", self.src, "선택을 푸는 손잡이가 없다")
        self.assertRegex(self.src, r'closest\("\[data-pinoff\]"\)',
                         "손잡이를 눌러도 아무 일도 일어나지 않는다")

    def test_the_handle_sits_in_the_header(self):
        """푸는 손잡이는 푸는 대상 바로 위에 선다 — 오른쪽 문서 판에 두면
        '문서를 닫는다'가 아니라 '문서를 취소한다'로 읽히는 자리다(그 판에는
        이미 승인·반려가 있다)."""
        m = re.search(r'class="grp[^"]*pinhead[^"]*"[^>]*>(.*?)</div>', self.src, re.S)
        self.assertIsNotNone(m, "머리글을 찾지 못했다")
        self.assertIn("data-pinoff", m.group(1), "손잡이가 머리글 밖에 있다")

    def test_the_handle_is_ink_and_reachable_by_keyboard(self):
        """색면·테두리 없는 mono 글자 + hover 밑줄 — `+ N개 더 보기` 와 같은 어휘.
        그리고 진짜 button 이라 Tab 으로 닿고 Enter 로 눌린다."""
        self.assertRegex(self.src, r'<button type="button" class="pinoff"',
                         "손잡이가 진짜 button 이 아니다")
        body = dict((s, c) for s, c in rules_for(self.src, ".pinoff"))
        base = [c for s, c in body.items() if s.endswith(".pinoff")]
        self.assertTrue(base, ".pinoff 규칙이 없다")
        flat = base[0].replace(" ", "")
        self.assertIn("background:none", flat)
        self.assertIn("border:0", flat)
        self.assertTrue(any(":focus-visible" in s for s in body),
                        "키보드로 닿은 자리가 보이지 않는다")

    def test_letting_go_clears_the_selection_everywhere(self):
        """푼다는 것은 주소에서도 빠진다는 뜻이다 — 새로고침에 되살아나면 안 푼 것이다."""
        m = re.search(r"function docDeselect\(\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "선택을 푸는 함수가 없다")
        fn = m.group(1)
        self.assertIn("selectedDoc = null", fn)
        self.assertIn("pushRoute()", fn, "주소에 문서가 남아 새로고침하면 되살아난다")

    def test_letting_go_shows_the_empty_state(self):
        """오른쪽 판이 방금 푼 문서를 계속 그리고 있으면 아무것도 안 푼 것이다 —
        renderDocs 는 doclist 만 갈아 끼우므로 뷰어는 스스로 비워야 한다."""
        m = re.search(r"function docDeselect\(\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("문서를 선택하세요", m.group(1),
                      "푼 뒤에 오른쪽이 무엇을 보여 주는지 정해지지 않았다")

    # --- Esc 는 그 층이 아니다 ---

    def test_escape_does_not_drop_the_document(self):
        """Esc 는 떠 있는 것을 닫는 키다. 판의 상태까지 지우면, 호버카드를
        닫으려고 누른 Esc 가 읽던 문서를 되돌리기 없이 지운다."""
        m = re.search(r'if \(e\.key !== "Escape"\) return;(.+?)\}\);', self.src, re.S)
        self.assertIsNotNone(m, "전역 Escape 핸들러를 찾지 못했다")
        self.assertNotIn("selectedDoc", m.group(1),
                         "Esc 가 문서 선택까지 지운다 — 같은 키에 두 층이 얹혔다")
        self.assertNotIn("docDeselect", m.group(1))


if __name__ == "__main__":
    unittest.main()
