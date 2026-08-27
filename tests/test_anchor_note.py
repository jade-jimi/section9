"""구간에 메모 달기 (REQ-20260827-072-62x6).

사용자: "문서에 특정 라인에 메모를 추가할 수 있는 기능이 있으면 좋겠고, 특정
단어, 문장, 구간을 드래그 하면 미니 프롬프트 팝업창이 떠서 애드혹 하게 프롬프팅
하고, 그 결과나 응답이 문단에 추가 되었으면 좋겠다."

서버는 이미 `/api/chat` 이 `doc` 와 함께 `anchor`(끌어 고른 글 그대로)를 받으면
문서 노트 첫 줄에 `> ⌖ 고른 글` 인용으로 남긴다(커밋 2a83a17). 다시 읽는 함수는
`note_anchor(entry_text)`.

계약은 여섯이다.

  ① 문서 본문에서 글을 끌어 고르면 그 자리에 미니 팝업이 뜨고, **고른 글이
     팝업 안에 보인다**.
  ② 쓴 말이 `doc` + `anchor` 로 전송된다.
  ③ 앵커 달린 노트를 **그 구간 옆에서** 읽을 수 있게 짚는다(양방향).
  ④ **고르기만 하고 아무것도 안 쓰면 팝업은 조용히 사라진다.** 이 기능의 가장
     큰 위험이다 — 문서를 읽으려고 끄는 사람이 훨씬 많고, 매번 쓰기 상자가
     튀어나오면 문서를 못 읽는다. 그래서 뜨는 것은 버튼 하나뿐이고, 쓰는 자리는
     눌러야 열린다.
  ⑤ 쓰는 자리는 071 의 판정 대화상자와 **같은 어휘**다. 팝업이 두 벌이면 한
     벌만 고쳐진다.
  ⑥ 문서가 바뀌어 그 글을 못 찾으면 **못 찾았다고 말한다.** 엉뚱한 곳을
     짚으면서 짚는 척하는 것이 제일 나쁘다.

실행: python3 tests/ anchor_note
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")
S9 = os.path.join(HERE, "..", "bin", "s9")


class AnchorNote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    # ---------- ① 고른 글이 팝업에 보인다 ----------

    def test_the_popup_shows_what_was_picked(self):
        """무엇에 다는 메모인지가 곧 라벨이다."""
        fn = self._fn("anchorPopShow")
        self.assertIn("anchorSelText", fn, "고른 글을 읽지 않는다")
        self.assertIn("ANCHOR_MARK", fn, "표식이 없다")
        self.assertRegex(fn, r"s\.text\.slice\(0, 34\)", "긴 글을 그대로 흘린다")
        self.assertIn("에 메모", fn, "무엇을 하는 버튼인지 말하지 않는다")
        # 문서 본문에서 고른 것만 — 메타표에서 고른 글은 문서의 글이 아니다
        sel = self._fn("anchorSelText")
        self.assertIn('root.querySelector(".md")', sel, "본문 밖의 선택도 받는다")
        self.assertIn("ANCHOR_MIN", sel, "한두 글자에도 팝업이 뜬다")
        self.assertIn("ANCHOR_MAX", sel, "문서 전체를 앵커로 삼을 수 있다")

    # ---------- ② doc + anchor ----------

    def test_it_sends_doc_and_anchor(self):
        """서버가 받는 두 값 그대로 — 고른 글은 손대지 않고 그대로 보낸다."""
        fn = self._fn("anchorSend")
        self.assertIn('"/api/chat"', fn, "다른 곳으로 보낸다")
        self.assertIn("doc: docId, anchor", fn, "doc·anchor 를 함께 보내지 않는다")
        # 붙어 있는 세션이 없으면 보낼 곳이 없다 — 말없이 삼키지 않는다
        self.assertIn("if (!T || !T.sid)", fn, "세션이 없어도 보내는 척한다")

    # ---------- ③ 그 구간 옆에서 읽는다 ----------

    def test_anchored_notes_point_both_ways(self):
        """구간 → 메모, 메모 → 구간. 한쪽만 있으면 되돌아올 수 없다."""
        fn = self._fn("anchorMark")
        self.assertIn("blockquote", fn, "앵커 인용을 찾지 않는다")
        self.assertIn("anjump", fn, "구간에서 메모로 갈 수 없다")
        self.assertIn("anback", fn, "메모에서 구간으로 갈 수 없다")
        self.assertIn("anchorFind", fn, "본문에서 그 글을 찾지 않는다")
        # 인용은 렌더돼야 찾을 수 있다 — md2html 에 인용 처리가 있어야 한다
        self.assertIn("<blockquote>", self.src, "마크다운이 인용을 그리지 않는다")
        self.assertRegex(self.src, r"const QUOTE_RE = /\^\\s\*&gt;",
                         "이미 esc() 를 지난 줄에서 `>` 로 찾는다 (한 줄도 안 걸린다)")

    def test_it_matches_exactly_not_approximately(self):
        """비슷한 것을 짚으면 거짓말이다 — 공백 차이만 눈감는다."""
        fn = self._fn("anchorFind")
        self.assertIn('replace(/\\s+/g, " ")', fn, "공백 차이로 못 찾는다")
        self.assertIn("surroundContents", fn, "찾은 자리를 감싸지 않는다")
        # 앵커 인용 자신을 짚지 않는다 (인용문 안에 같은 글이 있다)
        self.assertIn('closest("blockquote.anchorq")', fn,
                      "메모가 제 인용문을 가리킨다")

    # ---------- ④ 조용히 사라진다 ----------

    def test_it_disappears_silently_when_nothing_is_written(self):
        """읽으려고 끄는 사람이 훨씬 많다 — 방해가 되면 문서를 못 읽는다."""
        bind = self._fn("anchorBind")
        for how in ("Escape", "scroll", "mousedown"):
            self.assertIn(how, bind, "%s 로 안 사라진다" % how)
        self.assertIn("anchorPopClose", bind)
        # 뜨는 것은 버튼 하나 — 쓰기 상자를 먼저 들이밀지 않는다
        show = self._fn("anchorPopShow")
        self.assertIn('createElement("button")', show, "고르자마자 쓰기 상자가 뜬다")
        self.assertNotIn("textarea", show, "고르자마자 쓰기 상자가 뜬다")
        self.assertNotIn("s9dlg", show, "고르자마자 대화상자가 뜬다")
        # 아무것도 안 쓰고 닫으면 아무 일도 없다
        ask = self._fn("anchorAsk")
        self.assertIn("if (text === null) return;", ask, "취소해도 무언가 보낸다")

    # ---------- ⑤ 같은 어휘 ----------

    def test_the_writing_surface_is_the_judgement_dialog(self):
        """팝업이 두 벌이면 한 벌만 고쳐진다."""
        ask = self._fn("anchorAsk")
        self.assertIn('s9dlg({kind: "prompt"', ask, "제 대화상자를 새로 만든다")
        self.assertIn("required: true", ask, "빈 메모도 보낸다")
        self.assertIn("고른 구간에 메모를 답니다", ask, "무엇을 하는 창인지 말하지 않는다")
        # 색면 금지 · 스킨 전용 스타일 금지
        css = self._css()
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,6}\b", "색 하드코딩 금지")
        self.assertNotRegex(css, r"\[data-(?:skin|theme)=", "스킨 전용 스타일 금지")
        for v in re.findall(r"background\s*:\s*([^;}\n]+)", css):
            self.assertIn(v.strip(), ("none", "transparent", "var(--panel)", "var(--text)"),
                          "색면을 깔지 않는다: %s" % v)

    # ---------- ⑥ 못 찾으면 못 찾았다고 ----------

    def test_it_says_when_it_cannot_find_the_span(self):
        """엉뚱한 곳을 짚으면서 짚는 척하는 것이 제일 나쁘다."""
        fn = self._fn("anchorMark")
        self.assertIn("anlost", fn, "못 찾았을 때의 표시가 없다")
        self.assertIn("문서가 바뀌어 이 구간을 찾지 못했습니다", fn,
                      "왜 못 짚는지 말하지 않는다")
        self.assertRegex(fn, r"if \(!hit\)\{[\s\S]{0,300}?return;",
                         "못 찾았는데도 짚으려 든다")

    # ---------- 서버와 같은 표식을 쓴다 ----------

    def test_the_mark_matches_the_server(self):
        """앵커 표식은 서버가 쓰는 그 글자여야 한다 — 다르면 영영 못 읽는다."""
        with open(S9, encoding="utf-8") as f:
            s9 = f.read()
        self.assertIn('ANCHOR_MARK = "\\u2316"', s9, "서버 표식이 바뀌었다")
        self.assertIn('const ANCHOR_MARK = "⌖"', self.src,
                      "화면이 서버와 다른 표식을 쓴다")

    def test_it_can_be_opened_without_hands(self):
        """헤드리스로 직접 보고 고칠 길 — 끌어 고른 상태는 손으로 만들어야 한다."""
        self.assertIn("[?&]anchor\\b", self.src, "진단 파라미터가 없다")
        self.assertIn("anchorPopShow(host", self._fn("anchorDiag"),
                      "진단이 팝업을 세우지 않는다")

    # ---------- helpers ----------

    def _fn(self, name):
        m = re.search(r"(?:async )?function %s\([^)]*\)\{[\s\S]*?\n\}" % name, self.src)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m.group(0)

    def _css(self):
        m = re.search(r"/\* -+ 구간에 메모 달기[\s\S]*?\*/([\s\S]*?)\n\n", self.src)
        self.assertIsNotNone(m, "구간 메모 CSS 블록을 찾지 못했다")
        return m.group(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
