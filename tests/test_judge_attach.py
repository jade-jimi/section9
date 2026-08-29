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

## 반려 재작업 (2026-08-29) — 붙는 것은 그림만이 아니다

사용자: "반려에 첨부할 수 있는 이미지가, 그림 이미지일수도, 문서 파일일수도,
영상파일일수도 있다." 실패한 CSV·로그·화면을 녹화한 영상이 반려의 근거로 온다.
1차는 붙여넣기·끌어놓기에서 **그림이 아닌 것을 조용히 버렸고**, 붙인 것을
무조건 `[Image:]` 로 적었다 — 영상에 그 표기가 붙으면 문서에 깨진 칸이 남는다.
붙지 않은 것보다 나쁘다.

⑥ **무엇이든 받는다.** 화면은 종류로 거르지 않는다.
⑦ **무엇으로 적을지는 서버가 정한다**(`asset_mark`). 화면이 확장자 표를 또
   들면 서버의 표와 어긋나고, 어긋난 그 확장자만 문서에서 깨진 칸이 된다.
   화면에 하나 남은 그림 판정(터미널 채팅 글)은 `IMAGE_EXT` 한 곳뿐이고,
   그 목록은 서버 `TYPE_GROUPS["image"]` 와 **같아야 한다** — 시험이 맞대어 본다.
⑧ **왕복은 한 번이다.** `/api/status` 가 `atts` 와 `label` 을 받는다. 순서
   (④)와 실패 시 중단(⑤)은 이제 서버가 한 몸으로 보장한다 — 화면이 손으로
   엮으면 앞이 되고 뒤가 안 될 때 어중간한 자리가 생긴다.
⑨ **판정 근거는 `response` 다.** `ask` 로 박아 두면 반려 근거가 문서에
   **질문**으로 적혀, 나중에 읽는 사람이 답할 질문과 판정 근거를 못 가른다.
⑩ **한도는 사람 말로.** 30MB 를 넘으면 실제 크기와 한도를 함께 말한다.
   영상은 쉽게 넘고, 다 올린 **뒤에** 400 을 받으면 기다린 시간이 헛것이 된다.

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

    def _code(self, name):
        """주석을 걷어낸 알맹이. 이 시험들은 "무엇을 하는가"를 묻지 "무엇을
        적어 두었는가"를 묻지 않는다 — 옛 방식을 **왜 버렸는지** 적어 둔 주석이
        그 옛 방식의 흔적으로 잡히면, 사람은 기록을 지워 시험을 통과시킨다."""
        fn = self._fn(name)
        fn = re.sub(r"/\*[\s\S]*?\*/", "", fn)
        return re.sub(r"(?m)^\s*//.*$", "", fn)

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
        """전이만 하고 끝내면 붙인 것은 서버 임시 자리에서 늙어 죽는다."""
        fn = self._code("postStatus")
        self.assertRegex(fn, r"atts: atts \|\| \[\]",
                         "붙인 것이 전이와 함께 가지 않는다")

    def test_it_knocks_once(self):
        """④⑤ 는 **서버가 한 몸으로** 보장한다 (2026-08-29 반려 재작업).

        1차에서는 화면이 두 번 두드렸다(`/api/note` → `/api/status`). 그래서
        "붙이는 것이 먼저"와 "못 붙이면 옮기지 않는다"를 화면이 손으로 엮어야
        했고, 앞이 되고 뒤가 안 되면 근거만 남고 상태는 안 옮겨진 어중간한
        자리가 생겼다. 이제 `/api/status` 가 `atts` 를 받는다 — 화면은 한 번
        보내고 결과만 읽는다. 계약 자체(④⑤)는 아래 서버 쪽에서 그대로 지킨다.
        """
        fn = self._code("postStatus")
        self.assertNotIn("/api/note", fn, "아직 두 번 두드린다")
        self.assertEqual(fn.count("await fetch("), 1,
                         "왕복이 하나가 아니다")

    def test_the_screen_no_longer_writes_the_mark(self):
        """⑦ 표기는 파일의 성질이지 화면의 취향이 아니다 — 화면이 짓던 것을
        서버(asset_mark)가 가져갔다. 그대로 두면 영상에 `[Image:]` 가 붙어
        문서에 깨진 칸이 남는다."""
        fn = self._code("postStatus")
        self.assertNotIn("[Image:", fn, "화면이 아직 표기를 짓는다")
        self.assertNotIn("[File:", fn)

    def test_the_reason_is_not_filed_as_a_question(self):
        """⑨ `ask` 로 박히면 반려 근거가 문서에 질문으로 적힌다."""
        fn = self._code("postStatus")
        self.assertRegex(fn, r'label: "response"',
                         "판정 근거의 라벨을 정하지 않는다")

    def test_the_order_and_the_stop_live_in_the_server(self):
        """④⑤ 가 옮겨 간 자리를 붙잡는다 — 화면에서 뺐으면 서버에 있어야 한다.
        한쪽만 보면 계약이 조용히 사라진 것을 아무도 모른다."""
        s9 = os.path.join(HERE, "..", "bin", "s9")
        with open(s9, encoding="utf-8") as f:
            src = f.read()
        i = src.find('if parsed.path == "/api/status":')
        self.assertGreater(i, 0)
        blk = src[i:i + 2200]
        self.assertIn("asset_mark", blk, "서버가 표기를 짓지 않는다")
        self.assertLess(blk.index("chat_append_doc"), blk.index("do_transition"),
                        "전이가 먼저다 — 작업자가 근거 없는 문서를 읽는다")

    # --- ⑥ 무엇이든 받는다 ---

    def test_it_does_not_sift_for_pictures(self):
        """실패한 CSV·로그·녹화 영상이 반려의 근거로 온다. 조용히 버리면
        사람은 붙였다고 믿고 근거 없는 반려를 보낸다."""
        fn = self._code("s9dlg")
        take = fn[fn.index("const take = async file"):]
        """ 목록에 담기 전에 빠져나가는 길은 **하나**여야 하고, 그것은 크기다.
           종류로 거르는 길이 하나라도 더 있으면 CSV·영상이 조용히 사라진다.
           (그림 정규식 자체는 남아 있다 — 이름 없는 붙여넣기에 이름을 지어
            주는 자리다. 거르는 데 쓰지 않는 것이 계약이다.) """
        head = take[:take.index("atts.push")]
        self.assertEqual(head.count("return;"), 1,
                         "종류로 거르는 자리가 남아 있다")
        self.assertIn("ATTACH_MAX", head[:head.index("return;")],
                      "빠져나가는 유일한 길이 크기가 아니다")
        m = re.search(r'ta\.addEventListener\("paste"[\s\S]{0,400}?\}\);', fn)
        self.assertIsNotNone(m)
        self.assertNotIn("image/", m.group(0),
                         "붙여넣기가 그림만 받는다")
        self.assertIn('i.kind === "file"', m.group(0))

    def test_the_chip_says_what_it_is(self):
        """칩이 그림을 전제하면 문서·영상을 붙일 수 있다는 것을 아무도 모른다."""
        fn = self._fn("s9dlg")
        seg = fn[fn.index("const attRender"):]
        self.assertIn("isImageName", seg[:900], "칩이 종류를 가르지 않는다")
        self.assertNotIn("이 그림 빼기", self.src, "말이 아직 그림만 가리킨다")

    def test_the_words_do_not_say_pictures_only(self):
        """⑥ 힌트·올리는 중·실패 문구가 '그림'이면 나머지는 없는 셈이다."""
        i = self.src.index("const DLG_ATTACH_HINT")
        hint = self.src[i:i + 260]
        for w in ("문서", "영상"):
            self.assertIn(w, hint, "붙일 수 있는 것을 다 말하지 않는다")
        self.assertNotIn("그림을 올리는 중이에요", self.src)
        self.assertNotIn("그림을 올리지 못했어요", self.src)

    # --- ⑦ 그림 판정은 한 곳, 서버와 같은 목록 ---

    def test_the_only_image_test_matches_the_server(self):
        """화면에 남은 그림 판정은 터미널 채팅 글 하나뿐이고(서버가 손댈 자리가
        없다), 그 목록이 서버와 어긋나면 그 확장자만 문서에서 깨진 칸이 된다."""
        m = re.search(r'const IMAGE_EXTS = "(.+?)";', self.src)
        self.assertIsNotNone(m, "그림 확장자 목록이 한 곳에 있지 않다")
        # 화면 안에 그런 확장자 목록이 둘이면 이미 갈라진 것이다 (실제로 갈려 있었다)
        self.assertEqual(len(re.findall(r"png\|jpe\?g\|gif", self.src)), 1,
                         "확장자 목록이 화면에 두 벌이다")
        s9 = os.path.join(HERE, "..", "bin", "s9")
        with open(s9, encoding="utf-8") as f:
            src = f.read()
        g = re.search(r'"image": \{([^}]*)\}', src)
        self.assertIsNotNone(g, "서버의 그림 확장자 목록을 찾지 못했다")
        exts = re.findall(r'"\.(\w+)"', g.group(1))
        self.assertTrue(exts)
        pat = re.compile(r"\.(?:%s)$" % m.group(1), re.I)
        for e in exts:
            self.assertTrue(pat.search("x." + e),
                            "서버는 그림이라는데 화면은 아니다: ." + e)

    # --- ⑩ 한도는 사람 말로 ---

    def test_too_big_says_how_big_and_how_much_is_allowed(self):
        """"업로드 실패"는 무엇을 고쳐야 할지 알려 주지 않는다. 영상은 쉽게
        넘으므로 이 말이 자주 쓰인다."""
        self.assertRegex(self.src, r"const ATTACH_MAX = 30 \* 1024 \* 1024",
                         "서버 한도와 같은 값이 화면에 없다")
        i = self.src.index("const attTooBig")
        say = self.src[i:i + 300]
        self.assertIn("fmtSize(f.size)", say, "실제 크기를 말하지 않는다")
        self.assertIn("fmtSize(ATTACH_MAX)", say, "한도를 말하지 않는다")
        # 두 화면이 각자 30MB 를 적어 두면 서버가 바뀔 때 한 곳만 고쳐진다
        self.assertEqual(self.src.count("30 * 1024 * 1024"), 1,
                         "한도가 화면에 두 벌이다")
        fn = self._fn("termUpload")
        self.assertIn("ATTACH_MAX", fn, "터미널이 제 한도를 따로 든다")
        # 올린 뒤가 아니라 올리기 전에 막는다
        fn2 = self._code("s9dlg")
        take = fn2[fn2.index("const take = async file"):]
        self.assertLess(take.index("ATTACH_MAX"), take.index("readAsDataURL"),
                        "다 올린 뒤에 한도를 말한다 — 기다린 시간이 헛것이 된다")

    def test_the_reason_survives_the_next_redraw(self):
        """못 붙인 이유는 **상태로 들고 있어야** 한다.

        1차에서는 실패한 자리에서 곧장 hint 에 써 넣었는데 바로 뒤따르는
        `sync()` 가 덮어썼다 — 즉 "올리지 못했어요"는 한 번도 보인 적이 없다.
        영상은 한도를 자주 넘으므로 이 말이 자주 쓰이는데, 뜨자마자 사라지면
        사람은 아무 일도 안 일어난 것으로 읽는다.
        """
        fn = self._code("s9dlg")
        self.assertIn("attWarn", fn, "못 붙인 이유를 들고 있지 않다")
        take = fn[fn.index("const take = async file"):]
        self.assertNotIn("hint.innerHTML", take,
                         "실패한 자리에서 힌트를 직접 써 넣는다 — 곧 덮인다")
        sy = fn[fn.index("const sync = ()"):]
        self.assertIn("attWarn", sy[:900], "다시 그릴 때 이유가 사라진다")

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
        # 그림·문서·영상 셋이 한 화면에 선다 (⑥ — 하나만 세우면 갈린 것을 못 본다)
        i = self.src.index("seedAtts:")
        seed = self.src[i:i + 400]
        for ext in (".png", ".csv", ".mp4"):
            self.assertIn(ext, seed, "진단 창에 %s 가 없다" % ext)


if __name__ == "__main__":
    unittest.main()
