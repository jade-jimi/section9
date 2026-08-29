"""반려에 그림을 붙인다 (REQ-20260829-015).

사용자: "반려할 때 이미지를 붙여넣을 수 있는 기능을 만들어달라고 했었지만,
어느샌가 유실된 것 같다. 그래서 이어 말하기 기능으로 이미지와 함께 반려하는데…"

클립보드 그림을 받는 자리는 터미널 입력줄 한 곳뿐이었다. 판정 창은 글자만
받으니, 화면에서 반려하려면 글로만 쓰거나 터미널로 건너가 우회해야 했다 —
그 우회를 쓰다가 사용자는 또 다른 결함(REQ-20260829-012)을 만났다. **그 우회가
없어지는 것이 이 건의 값이다.**

## 결정

① **글을 받는 창은 전부 그림도 받는다.** 반려만 받게 하면 사람은 어느 창이
   그림을 받는지 외워야 한다 — 승인에도 "이렇게 나왔다"는 그림을 남길 이유가
   있고, 판정 창은 어차피 한 컴포넌트다. 규칙은 하나다.
② **받는 길은 터미널이 쓰는 그 길이다.** 업로드 엔드포인트를 두 벌로 만들면
   한 벌만 고쳐진다.
③ **그림은 사유와 함께 그 문서에 남는다.** 전이만 하고 끝내면 그림은 서버
   임시 자리에서 늙어 죽는다.
④ **그림이 먼저, 전이가 나중이다.** 반려는 무인 재작업 작업자를 깨우는데,
   그가 문서를 읽을 때 그림이 이미 있어야 한다.
⑤ **그림을 못 붙이면 전이하지 않는다.** 증거 없는 반려를 만들지 않는다 —
   그게 이 요청이 고치려는 실패의 다른 얼굴이다.

## 서버 몫 (여기서는 안 한다)

지금은 화면이 두 번 두드린다: `/api/note` 로 사유+그림을 남기고, `/api/status`
로 전이한다. 한 번으로 줄이려면 `/api/status` 가 `atts` 를 받아 do_transition
안에서 함께 붙여야 한다. 그리고 `/api/note` 는 라벨을 `ask` 로 박아 두어,
반려 근거가 '질문'으로 적힌다 — 라벨을 인자로 받게 하는 것이 서버 몫이다.

실행: python3 tests/ judge_attach
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


class JudgeAttach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    def _fn(self, name):
        m = re.search(r"(?:async )?function %s\([^)]*\)\{[\s\S]*?\n\}" % name, self.src)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m.group(0)

    # --- ① 그림을 받는다 ---

    def test_the_dialog_takes_pasted_images(self):
        """붙여넣기(Ctrl+V)로 받는다 — 사용자가 실제로 하던 동작이다."""
        fn = self._fn("s9dlg")
        self.assertRegex(fn, r'addEventListener\("paste"',
                         "판정 창이 붙여넣기를 받지 않는다")
        self.assertIn("clipboardData", fn)

    def test_the_dialog_takes_dropped_images(self):
        """끌어놓기도 받는다 — 파일로 갖고 있는 그림은 붙여넣기가 번거롭다."""
        fn = self._fn("s9dlg")
        self.assertRegex(fn, r'addEventListener\("drop"', "끌어놓기를 받지 않는다")
        self.assertRegex(fn, r'addEventListener\("dragover"',
                         "끌어놓을 자리라는 표시가 없다")

    def test_every_writing_dialog_takes_them(self):
        """반려만 받게 하면 어느 창이 그림을 받는지 외워야 한다 — 승인·상태
        옮기기도 같은 창이고 같은 규칙이다."""
        fn = self._fn("judgeAct")
        self.assertEqual(fn.count("attach: true"), 3,
                         "글을 받는 판정 창 셋(승인·반려·상태 옮기기)이 "
                         "모두 그림을 받지는 않는다")

    # --- ② 두 벌로 만들지 않는다 ---

    def test_the_upload_road_is_the_one_the_terminal_uses(self):
        """업로드 엔드포인트가 둘이면 한 벌만 고쳐진다."""
        self.assertEqual(self.src.count('"/api/chat/upload"'), 2,
                         "업로드 길이 하나(터미널)도 둘(그 밖)도 아니다 — "
                         "터미널과 판정 창이 같은 한 길을 써야 한다")

    # --- ③ 올리는 중에는 못 누른다 ---

    def test_you_cannot_judge_while_a_picture_is_still_going_up(self):
        """반쯤 올라간 그림으로 반려가 나가면 증거가 빈 채로 남는다."""
        fn = self._fn("s9dlg")
        self.assertRegex(fn, r"some\(a => a\.up\)",
                         "올리는 중인 첨부가 있어도 확인이 눌린다")

    def test_a_chip_can_be_taken_back(self):
        """잘못 붙인 그림을 뺄 수 없으면 창을 닫았다 다시 열어야 한다."""
        self.assertIn("data-dlgattrm", self.src, "붙인 그림을 뺄 수 없다")

    # --- ④⑤⑥ 문서에 남는다 · 순서 · 실패 ---

    def test_the_picture_lands_on_the_document(self):
        """전이만 하고 끝내면 그림은 서버 임시 자리에서 늙어 죽는다."""
        fn = self._fn("postStatus")
        self.assertIn('"/api/note"', fn, "붙인 그림이 문서에 남지 않는다")
        self.assertRegex(fn, r"\[Image: ",
                         "문서가 그림으로 그릴 표식을 남기지 않는다")

    def test_the_picture_goes_first(self):
        """반려는 무인 재작업 작업자를 깨운다 — 그가 문서를 읽을 때 그림이
        이미 있어야 한다."""
        fn = self._fn("postStatus")
        self.assertLess(fn.index('"/api/note"'), fn.index('"/api/status"'),
                        "전이가 먼저 나가 작업자가 그림 없는 문서를 읽는다")

    def test_a_failed_attachment_stops_the_transition(self):
        """증거 없는 반려를 만들지 않는다 — 그게 이 요청이 고치려는 실패의
        다른 얼굴이다."""
        fn = self._fn("postStatus")
        m = re.search(r'"/api/note"[\s\S]{0,900}?\n', fn)
        self.assertIsNotNone(m)
        seg = fn[fn.index('"/api/note"'):fn.index('"/api/status"')]
        self.assertIn("return", seg,
                      "그림을 못 붙였는데도 전이가 그대로 나간다")

    # --- 재료: 계기판 언어 ---

    def test_the_chip_is_ink_not_a_filled_block(self):
        """색면 금지. 그리고 터미널 팔레트(--cc-*)를 빌려 쓰지 않는다 —
        이 창은 tone 을 따라가는데 --cc-* 는 늘 어두운 자체 색이라 밝은
        테마에서 글자가 묻힌다."""
        rules = rules_for(self.src, ".dlgatt")
        self.assertTrue(rules, "판정 창 첨부 줄의 규칙이 없다")
        for sel, css in rules:
            flat = css.replace(" ", "")
            self.assertNotIn("--cc-", flat, "터미널 팔레트를 빌려 썼다: " + sel)
            self.assertNotRegex(flat, r"background:(?!none)",
                                "칩을 색면으로 그렸다: " + sel)

    def test_it_can_be_seen_without_hands(self):
        """붙인 그림이 선 창은 손이 있어야 생긴다 — `?dlg=` 가 낸 선례대로
        헤드리스에서도 세워 볼 수 있어야 한다."""
        self.assertIn("rejectatt", self.src,
                      "그림이 붙은 판정 창을 세워 볼 길이 없다")


if __name__ == "__main__":
    unittest.main()
