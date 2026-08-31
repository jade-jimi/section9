"""멈춘 것을 사람이 깨우는 손잡이 — 화면 몫 (REQ-20260828-041-62x6).

사용자(18:04): "in-progress 중인 카드나 문서에 상태체크 기능을 만들고 **굳이
프롬프트로 물어보지 않고 진행할 수 있게** 하는건 어때?"

REQ-20260828-036 은 그 물음의 **보여주기 절반**만 냈다 — 점의 근거를 고치고,
멈춤 줄을 세우고, 열 머리에 수를 붙였다. 화면은 "멈췄다"고 말할 수 있게 됐지만
사람이 거기서 할 수 있는 일은 없었다. 그래서 사용자는 하루에 다섯 번 리드에게
"이거 진짜 도는 거냐"를 물어야 했다. 이 파일은 나머지 절반의 계약이다.

계약은 여섯이다.

  ① **손잡이는 멈춤 줄에만.** 멈춘 카드가 아니면 뜨지 않는다. 판정은 화면이
     다시 하지 않는다 — 서버가 행에 실어 준 `stalled_mins` 를 읽을 뿐이다
     (REQ-20260828-036 이 세운 규칙: 두 벌이면 한 벌만 고쳐진다).
  ② **보드와 문서가 한 함수로 짓는다.** 같은 행동이 두 화면에 각자 글자를
     가지면 한쪽만 고쳐진다 — REQ-20260828-007 이 그 이유로 세 번 반려됐다.
  ③ **화면이 이유를 짓지 않는다.** 서버가 준 `message` 를 그대로 띄운다.
     `action` 으로 문구를 갈라 쓰는 순간 같은 말이 서버와 화면 두 벌이 된다.
  ④ **`ok=false` 는 오류가 아니라 설명이다.** `capped`(한도 소진)·`busy`(이미
     붙어 있음)·`moving`(아직 멈춘 게 아님)은 정상적인 답이다 — 붉은 실패의
     옷을 입히면 사람은 고장으로 읽고 다시 누르지 않는다.
  ⑤ **연타는 막고 실패는 다시 누를 수 있다.** 도는 중에는 눌리지 않지만, 못
     깨운 것을 다시 못 누르게 잠그는 것은 벌주는 화면이다.
  ⑥ **새 층을 만들지 않는다.** 색면 하이라이트·세로 띠·새 경고 배지 없이,
     카드가 이미 쓰는 행동 줄(.acts)과 행위 버튼(.deed)을 그대로 입는다.

실행: python3 tests/ wake_handle
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()

# 서버가 돌려주는 action 값 전부 (bin/s9 wake_request 의 계약). 화면은 이 낱말
# 중 **어느 것도** 알아서는 안 된다 — 알기 시작하면 문구가 두 벌이 된다.
ACTIONS = ("spawned", "busy", "moving", "capped", "off", "disabled",
           "elsewhere", "no-cli", "not-request", "not-in-progress")


def _grab(src, name):
    m = re.search(r"function %s\([^)]*\)\{[\s\S]*?\n\}" % name, src)
    assert m, name
    return m.group(0)


class WakeHandle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        cls.stall = _grab(cls.src, "stallHTML")
        # 손잡이가 사실 줄을 떠나 id 줄의 벨트로 갔다 (REQ-20260830-040 규칙 4).
        # 계약은 그대로다 — 짓는 자리가 하나이고, 안 멈춘 행에는 빈 문자열이
        # 오며, 카드와 문서가 같은 함수를 부른다. 보는 덩어리만 넓힌다.
        cls.handle = "\n".join([cls.stall, _grab(cls.src, "wakeBtnHTML"),
                                _grab(cls.src, "driftBtnHTML"),
                                _grab(cls.src, "deedBeltHTML")])
        # 답을 창으로 옮기는 자리가 wakeDlg 로 갈라졌고(REQ-20260829-030), 그
        # 앞에 **창이 설지를 가르는 자리**(wakeAnswer)가 한 겹 더 섰다
        # (REQ-20260830-049). 진단이 사람이 누를 때와 **같은 함수**를 부르게
        # 하려는 것이라, 이 시험이 보는 "깨우기의 길"은 셋을 합한 것이다.
        cls.wake = "\n".join([_grab(cls.src, "wakeDoc"),
                              _grab(cls.src, "wakeAnswer"),
                              _grab(cls.src, "wakeDlg")])
        cls.card = _grab(cls.src, "cardHTML")
        cls.doc = _grab(cls.src, "openDoc") if "function openDoc(" in cls.src \
            else cls.src

    # ---------- ① 손잡이는 멈춤 줄에만 ----------

    def test_the_handle_lives_in_the_id_belt(self):
        """깨우기는 **id 줄의 벨트** 안에서만 그려진다 (REQ-20260830-040 규칙 4).

        멈춤 줄에 붙어 있던 동안 손잡이의 자리는 카드마다 달랐고, 좁은 칸에서는
        그 27px 이 문장에서 빼앗은 폭이라 정작 멈춤 줄이 잘렸다. 자리는 옮겼지만
        **짓는 자리는 여전히 하나**다 — 그것이 이 시험이 지키는 것이다."""
        self.assertIn("data-wake=", self.handle, "손잡이를 짓는 자리가 없다")
        # 그리는 자리는 둘뿐이다 — 글리프 갈래(wakeBtnHTML)와 낱말 갈래
        # (driftBtnHTML). paintWake 의 `[data-wake="…"]` 는 이미 그려진 것을
        # **찾는** 자리라 세지 않는다.
        self.assertEqual(len(re.findall(r'data-wake="\$\{esc\(', self.src)), 2,
                         "손잡이를 그리는 자리가 여럿이다 — 한 벌만 고쳐진다")
        # 낱말은 상수 한 곳에서 온다 (REQ-20260829-024 라운드4) — 글자를 짓는
        # 자리와 다시 칠하는 자리 두 곳에 두었더니 개명 한 번에 갈렸다.
        self.assertIn("WAKE_LABEL", self.handle)

    def test_a_card_that_is_not_stalled_has_no_handle(self):
        """멈춘 카드가 아니면 빈 문자열이 온다.

        조건이 **부르는 쪽**에 있던 것을 함수 안으로 걷어 들였다
        (REQ-20260828-041 2차). 부르는 쪽마다 조건을 두면 그 조건이 갈라진다 —
        실제로 카드에만 `!bl.length` 가 붙어 문서 화면과 다른 답을 냈다.
        계약은 그대로다: 안 멈춘 카드에는 손잡이가 없다.
        """
        m = re.search(r"const stall\s*=([\s\S]{0,200}?);\n", self.card)
        self.assertIsNotNone(m, "카드가 멈춤 줄을 다는 자리가 없다")
        self.assertIn("stallHTML", m.group(1))
        self.assertIn("stallState(r)", self.stall, "줄 짓는 함수가 판정을 안 지난다")
        self.assertIn("stallState(r)", _grab(self.src, "wakeBtnHTML"),
                      "손잡이가 판정을 안 지난다")
        for name in ("slowRowHTML", "stoppedRowHTML", "wakeBtnHTML", "deedBeltHTML"):
            self.assertIn('return "";', _grab(self.src, name),
                          "%s 가 안 멈춘 행에 빈 문자열을 안 돌려준다" % name)

    def test_the_screen_never_measures_the_minutes_itself(self):
        """분은 서버가 잰다 — 화면이 다시 재면 CLI 와 다른 말을 하게 된다."""
        state = _grab(self.src, "stallState")
        self.assertIn("r.stalled_mins", state, "판정이 서버가 준 분을 안 읽는다")
        self.assertIn("st.mins", self.stall, "줄이 그 분을 안 옮긴다")
        for banned in ("Date.now() -", "getTime()", "fromisoformat"):
            self.assertNotIn(banned, self.stall,
                             "멈춤 줄이 나이를 스스로 재고 있다: %s" % banned)

    # ---------- ② 보드와 문서가 한 함수 ----------

    def test_board_and_document_say_the_same_word(self):
        """두 화면이 stallHTML 을 부른다 — 갈라질 자리가 없다."""
        calls = re.findall(r"stallHTML\(", self.src)
        self.assertGreaterEqual(len(calls), 3,
                                "짓는 자리(1) + 부르는 자리(보드·문서)가 없다")
        self.assertIn("stallHTML(r)", self.card, "보드 카드가 안 부른다")
        self.assertIn("stallHTML(stallDoc)", self.src, "문서 화면이 안 부른다")
        # 조각이 둘이 된 뒤로도 **둘 다** 같은 함수에서 온다 (REQ-20260830-040) —
        # 벨트를 문서에서 빼면 문서 화면만 손잡이를 잃는다.
        self.assertIn("deedBeltHTML(r)", self.card, "보드 카드가 벨트를 안 부른다")
        # 문서는 낱말 얼굴(wordy)로 부른다 (REQ-20260830-046) — 함수는 같다.
        self.assertIn("deedBeltHTML(stallDoc, true)", self.src,
                      "문서 화면이 벨트를 안 부른다")
        # 문서 화면은 **자기 조건을 갖지 않는다** (REQ-20260828-041 2차) —
        # 카탈로그 행을 넘길 뿐이고, 멈춤인지는 stallState 한 곳이 답한다.
        self.assertNotIn("srow", self.src.split("const stallRow")[1][:200],
                         "문서 화면이 다시 판정한다")
        # 행동은 머리 띠(docActs, 붙박이)로, 사실 줄은 그 아래 흐름으로
        # (REQ-20260830-046) — 멈춤 줄이 실제로 놓이는 계약은 그대로다.
        self.assertIn("${docActs}</div>${stallRow}", self.src,
                      "문서 화면에 멈춤 줄이 실제로 놓이지 않는다")

    # ---------- ③ 화면이 이유를 짓지 않는다 ----------

    def test_the_screen_shows_the_server_sentence_verbatim(self):
        self.assertIn("d.message", self.wake, "서버 문장을 안 쓴다")
        self.assertIn('title: d.message', self.wake,
                      "서버 문장이 창의 본문에 서지 않는다")

    def test_the_screen_does_not_branch_on_action(self):
        """`action` 으로 문구를 갈라 쓰면 서버와 화면 두 벌이 된다."""
        self.assertNotIn("d.action", self.wake, "화면이 action 을 읽는다")
        for a in ACTIONS:
            self.assertNotIn('"%s"' % a, self.wake,
                             "화면이 서버의 사유 낱말을 알고 있다: %s" % a)

    # ---------- ④ 거절은 오류가 아니다 ----------

    def test_a_refusal_is_not_painted_as_a_failure(self):
        """`ok=false` 도 설명이다 — 창머리 잉크를 붉게 올리지 않는다."""
        self.assertIn("stop: false", self.wake, "거절이 실패의 옷을 입는다")
        self.assertNotIn('cap: "실패"', self.wake)
        # 눈썹 잉크는 kind 가 아니라 stop 이 정한다
        cap = re.search(r'<span class="dlgcap\$\{([^}]*)\}', self.src)
        self.assertIsNotNone(cap, "창머리 잉크를 정하는 자리를 못 찾았다")
        self.assertIn("o.stop", cap.group(1),
                      "알림이면 무엇이든 붉어진다 — 설명도 고장으로 읽힌다")

    # ---------- ⑤ 연타는 막고 실패는 다시 ----------

    def test_no_double_press_but_a_failure_can_be_pressed_again(self):
        self.assertIn("if (wokePending(id)) return;", self.wake,
                      "같은 카드를 연타할 수 있다")
        self.assertIn("wokeAt.set(id, Date.now())", self.wake)
        # 실패·거절이면 표식을 지운다 = 다시 누를 수 있다
        self.assertEqual(len(re.findall(r"wokeAt\.delete\(id\)", self.wake)), 2,
                         "못 깨운 뒤에 다시 누를 수 없다")
        self.assertIn("if (!d.ok){ wokeAt.delete(id); paintWake(id); }",
                      self.wake, "거절 뒤 손잡이가 잠긴 채로 남는다")
        # 도는 중 표시는 서버 왕복을 기다리지 않는다
        self.assertIn("paintWake(id);\n  let d", self.wake,
                      "누른 순간 화면이 답하지 않는다")
        # 영영 잠기지 않는다 — 스폰이 조용히 죽어도 풀린다
        self.assertIn("WOKE_HOLD", self.src, "표식이 만료되지 않는다")

    def test_the_running_state_says_it_is_running(self):
        # 낱말이 「깨우기」에서 「이어가기」로 바뀌었다 (REQ-20260829-024 반려:
        # "깨우기, 세우기 라는 용어가 너무 어색한데"). 계약은 그대로다 —
        # 누른 뒤의 얼굴이 자기가 도는 중임을 말해야 한다.
        self.assertIn("WAKE_GOING", self.handle)
        self.assertIn("이어가는 중…", self.src)
        # 잠금은 `disabled` 가 아니라 `aria-disabled` 다 (REQ-20260831-009) —
        # `disabled` 는 눌린 손잡이에서 포커스를 걷어 키보드 손을 떨어뜨린다.
        self.assertIn("DEED_BUSY", self.handle,
                      "다시 그려도 도는 중인 손잡이가 되살아난다")
        self.assertIn('const DEED_BUSY = \' aria-disabled="true"\'', self.src,
                      "잠금 표시가 한 곳에서 오지 않는다")
        self.assertNotRegex(self.handle, r'\?\s*" disabled"',
                            "눌린 손잡이를 아직 disabled 로 잠근다")

    # ---------- ⑥ 새 층 없음 ----------

    def test_it_reuses_the_button_the_card_already_has(self):
        """.acts/.deed 를 그대로 입는다 — 그래야 스킨이 따라온다."""
        # 이제 글리프는 id 줄의 벨트에, 낱말 갈래만 자기 줄(.deedrow.wordy)에
        # 선다 (REQ-20260830-040) — 입은 옷은 그대로다.
        self.assertIn('class="deedrow wordy"', self.stall)
        self.assertIn('class="acts deedbelt"', self.handle)
        self.assertIn('class="acts wakerow"', self.handle)
        # `deed wake` 뒤에 상태 갈래(`ico`·`busy`)가 붙는다 (REQ-20260830-032:
        # 손잡이 얼굴이 글리프로 바뀌었다). 계약은 낱말 그대로가 아니라 **입은
        # 옷**이다 — 카드가 이미 쓰는 .deed 를 그대로 입었는가.
        self.assertRegex(self.handle, r'class="deed wake[ `$]')
        # 새 배지·색면·띠를 만들지 않는다
        m = re.search(r"\.acts\.wakerow\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, ".acts.wakerow 규칙이 없다")
        for banned in ("background", "animation", "border-left"):
            self.assertNotIn(banned, m.group(1),
                             "깨우기 줄이 %s 로 새 층을 만든다" % banned)
        self.assertNotIn("wakebanner", self.src)

    def test_calm_skin_does_not_lose_the_row(self):
        """calm 은 카드를 order 로 다시 세운다 — 자리를 안 주면 제목 위로 튄다.

        손잡이가 사실 줄과 한 줄로 묶이면서(REQ-20260830-032) 카드의 직계
        자식이 `.acts` 에서 그 껍데기(`.deedrow`)로 바뀌었다. 무는 것은 옛
        이름이 아니라 **그 자식이 order:3 을 받는가**다."""
        self.assertRegex(
            self.src,
            r'\[data-skin="calm"\] \.card>\.deedrow\{order:3\}',
            "calm 스킨에서 손잡이 줄이 카드 맨 위로 올라간다")

    # ---------- 배선 ----------

    def test_one_road_to_the_server(self):
        self.assertEqual(len(re.findall(r'"/api/wake"', self.src)), 1,
                         "깨우기를 부르는 자리가 여럿이다")
        self.assertIn('method: "POST"', self.wake)
        self.assertIn("withAs({id})", self.wake, "대리 사용자가 안 실린다")

    def test_enter_presses_the_handle_not_the_card(self):
        """카드 안의 **진짜 버튼**은 Enter 를 제 것으로 받는다.

        실측으로 잡은 결함이다 (REQ-20260828-041). 보드 카드는 role="button" 인
        판이고 그 안에 진짜 <button> 이 산다 — 승인·반려·이어 말하기, 그리고
        깨우기. role="button" 컨트롤을 Enter 로 누르는 전역 핸들러가
        `closest('[role="button"]')` 로 **판**을 집어 올려, 손잡이의 네이티브
        활성화를 preventDefault 로 막고 카드를 눌렀다. 마우스로는 깨우기가,
        키보드로는 문서 열기가 일어났다 — 같은 자리에서 다른 일이 일어나는
        종류의 고장이라 눈에 잘 안 띈다.
        """
        m = re.search(r'addEventListener\("keydown", e => \{[\s\S]{0,700}?'
                      r'closest\(\'\[role="button"\]\'\)', self.src)
        self.assertIsNotNone(m, "role=button 컨트롤의 Enter 핸들러를 못 찾았다")
        self.assertIn('t.closest("button,a[href],summary")', m.group(0),
                      "카드 안의 진짜 버튼이 Enter 를 빼앗긴다 — "
                      "키보드로는 손잡이 대신 문서가 열린다")

    def test_the_handle_is_not_the_card(self):
        """카드 안의 손잡이는 카드가 아니다 — 눌러도 문서가 열리지 않는다."""
        m = re.search(r'closest\("\[data-wake\]"\);\n\s*if \(wk\)\{([^\n]*)',
                      self.src)
        self.assertIsNotNone(m, "깨우기 클릭을 잡는 자리가 없다")
        self.assertIn("stopPropagation", m.group(1),
                      "깨우기를 누르면 문서까지 열린다")
        self.assertIn("wakeDoc(wk.dataset.wake)", m.group(1))


def _css(src):
    """주석을 걷어낸 CSS 만 — 주석은 고쳐 낸 옛 값을 근거로 인용한다."""
    return re.sub(r"/\*[\s\S]*?\*/", " ", src)


def _rules(src):
    """(셀렉터, 선언) 짝 — 손잡이를 건드리는 규칙만 훑는다."""
    out = []
    for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", src):
        out.append((" ".join(m.group(1).split()), m.group(2)))
    return out


class ThePaintIsNotTheTarget(unittest.TestCase):
    """손이 닿는 상자와 **칠해지는 원**은 다른 것이다 (REQ-20260830-043 2차 반려).

    사용자: "레이아웃이 여전히 안맞다" — 캡처는 손이 카드에 얹힌 화면이었고,
    거기서 검은 원이 식별자의 마지막 글자를 파고들었다.

    뿌리는 hover 가 **과녁 전체**(27px)를 칠한 것이다. 글리프 손잡이는 27px
    과녁 안에 11px 그림을 담고, 벨트는 그 남는 흰 자리만큼을 음수 여백으로
    되돌려 잉크 사이를 줄의 눈금에 맞춘다 — 그러니 상자를 통째로 칠하면 되돌린
    만큼이 그대로 글자를 덮는다. 쉬는 얼굴만 재고 끝내서 두 번 반려됐다.

    그래서 계약은 셋이다.
      ① 과녁은 안 줄인다 (min-width/min-height 27px).
      ② 칠은 안쪽 원에만 든다 (padding + background-clip:content-box).
      ③ 그 클립을 되돌리는 `background` 단축을 손잡이에 쓰지 않는다.
    """

    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.css = _css(f.read())
        cls.rules = _rules(cls.css)
        cls.belt = [(s, d) for s, d in cls.rules
                    if "deedbelt" in s or "deed.ico" in s]

    def test_the_target_is_not_shaved(self):
        """과녁 27px 은 1px 도 안 줄인다 — 아이콘이 된 대가가 작은 과녁이면 안 된다."""
        hit = [d for s, d in self.rules if s.endswith(".acts button.deed.ico")]
        self.assertTrue(hit, "글리프 손잡이의 과녁 규칙이 없다")
        self.assertIn("min-width:27px", hit[0])
        self.assertIn("min-height:27px", hit[0])

    def test_the_paint_is_clipped_into_the_target(self):
        """칠은 과녁이 아니라 그 안의 원에 든다."""
        gate = [d for s, d in self.belt if "background-clip" in d]
        self.assertEqual(len(gate), 1,
                         "칠하는 자리를 정하는 관문이 하나가 아니다 — "
                         "스킨마다 사본이 생기면 한쪽만 고쳐진다")
        self.assertIn("background-clip:content-box", gate[0])
        self.assertRegex(gate[0], r"padding:\d+px",
                         "안여백이 없으면 클립해도 원이 과녁 그대로다")
        self.assertIn("border-radius:999px", gate[0],
                      "라운드를 못박지 않으면 cobalt·slate 의 각진 값이 "
                      "클립된 칠을 모난 알약으로 만든다")

    def test_no_shorthand_undoes_the_clip(self):
        """`background:` 단축은 background-clip 을 border-box 로 되돌린다.

        손잡이를 건드리는 규칙이 단축을 쓰는 순간, 특이도가 관문보다 높으면
        칠이 다시 과녁 전체로 퍼진다 — 반려된 그 얼굴로 되돌아간다."""
        for sel, dec in self.belt:
            self.assertNotRegex(
                dec, r"(^|;)\s*background\s*:",
                "손잡이 규칙이 background 단축을 쓴다 (%s) — "
                "낱개 속성(background-color/-image)으로 쓰라" % sel)

    def test_the_pull_is_written_once(self):
        """왼쪽 당김은 잉크 사이를 실측해 정한 값이라 **한 곳**에만 산다.

        calm 이 `margin` 단축으로 세로 여백을 지우면서 그 값을 한 벌 더 갖고
        있었다 — 다음에 자를 대는 사람이 한쪽만 고친다."""
        pulls = [(s, d) for s, d in self.rules
                 if "deedbelt" in s and re.search(r"margin(-left)?\s*:[^;]*-\d", d)]
        self.assertEqual(len(pulls), 1,
                         "벨트의 왼쪽 당김이 %d 곳에 적혀 있다: %s"
                         % (len(pulls), [s for s, _ in pulls]))

    def test_the_focus_ring_rounds_the_circle_not_the_target(self):
        """키보드 링도 칠이다 — 과녁 밖에 그리면 hover 와 똑같이 글자를 덮는다."""
        ring = [d for s, d in self.belt if "focus-visible" in s]
        self.assertTrue(ring, "글리프 손잡이의 포커스 링 규칙이 없다")
        self.assertIn("outline-offset:-6px", ring[0])

    def test_an_inverted_card_inverts_the_chip_too(self):
        """터미널 스킨은 손이 얹힌 카드를 통째로 반전한다 — 그 위의 잉크 칩은
        배경과 같은 색이 되어 **손잡이가 통째로 사라졌다**(실제 포인터를 얹어
        찍고 발견). 잉크 배경에 잉크 칩은 없는 것과 같다."""
        inv = [d for s, d in self.belt
               if '[data-skin="terminal"]' in s and ".card:hover" in s]
        self.assertTrue(inv, "반전된 카드 위에서 칩을 뒤집는 규칙이 없다")
        self.assertTrue(any("background-color:var(--bg)" in d for d in inv),
                        "반전 카드에서 칩이 배경색에 묻힌다")


class TheWindowStandsOnlyForExceptions(unittest.TestCase):
    """성공을 알리는 창은 자격이 없다 (REQ-20260830-049, designer 판정 A안).

    이어가기는 비파괴·자동·되돌림 가능(⏸)이다. 누른 손 아래에서 ▶ 가 ⏸ 로
    서는 것이 이미 답인데, 그 위에 판을 하나 더 세우면 원인과 결과가 공간적으로
    끊기고 **창이 자기가 가리키는 그 카드를 가린다**(designer 실측 캡처). 게다가
    이 화면에서 창은 「물음 아니면 거절」의 신호로 학습돼 있어(중단하기 확인 ·
    닿지 못했습니다 · 이어가지 않음), 아무 문제도 없는데 문제의 옷을 입고
    나타난다. 카드 사실 줄의 규율(REQ-20260830-040 「예외만 말한다」)을 창에
    그대로 옮긴다.

    계약은 넷이다.
      ① 성공에 덧붙일 **예외 사실(`note`)이 없으면 창은 서지 않는다.**
      ② 실패·대기(`ok=false`)의 창은 그대로 선다 — 읽을 이유가 실제로 있다.
      ③ 갈래(워크스페이스)는 화면이 다시 판정하지 않는다 — 서버가 할 말을
         가졌는가 하나만 읽는다(bin/s9 `_wake_note` 가 유일한 판정처).
      ④ 급이 다른 두 말은 슬롯도 둘이다 — `message` 는 제목(.dlgt),
         `note` 는 부가(.dlgs). 화면이 한 문자열을 마침표로 쪼개지 않는다.
    """

    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        cls.answer = _grab(cls.src, "wakeAnswer")
        cls.dlg = _grab(cls.src, "wakeDlg")

    # ---------- ① 성공은 조용하다 ----------

    def test_a_plain_success_raises_no_window(self):
        """할 말이 없는 성공은 창을 세우지 않고 그냥 돌아간다."""
        self.assertRegex(
            self.answer, r"if\s*\(d\.ok\s*&&\s*!d\.note\)\s*return",
            "예외 사실 없는 성공이 아직 창을 세운다 — 카드의 ▶→⏸ 가 이미 답이다")

    def test_the_click_goes_through_the_verdict_not_around_it(self):
        """누른 길도 진단의 길도 **판정을 지나서** 창에 닿는다. 어느 한쪽이
        wakeDlg 를 직접 부르면 규칙이 한 자리에 있지 않게 된다."""
        doc = _grab(self.src, "wakeDoc")
        self.assertIn("wakeAnswer(id, d)", doc,
                      "누른 길이 판정을 건너뛰고 창을 짓는다")
        self.assertNotIn("wakeDlg(id, d)", doc)
        # 진단(diag.js `?dlg=wakespawn…`)도 같은 자리를 지난다
        self.assertNotIn("wakeDlg(\"REQ-", self.src,
                         "진단이 판정을 건너뛰고 창을 직접 짓는다 — 캡처가 "
                         "사람이 보는 화면을 비추지 못한다")

    # ---------- ② 실패·대기의 창은 남는다 ----------

    def test_a_refusal_still_stands(self):
        """`ok=false` 는 note 가 없어도 창이 선다 — 읽을 이유가 있다."""
        self.assertIn("d.ok &&", self.answer,
                      "성공 여부를 보지 않고 창을 없앤다 — 거절까지 조용해진다")
        self.assertIn("return wakeDlg(id, d);", self.answer,
                      "판정을 지난 답이 창으로 서지 않는다")

    # ---------- ③ 갈래는 화면이 짓지 않는다 ----------

    def test_the_screen_never_re_reads_the_workspace(self):
        """화면이 워크스페이스를 다시 캐면 그리기와 답이 두 벌이 된다."""
        for w in ("workspace", "worktree", "kind ===", "WS_MEANS"):
            self.assertNotIn(w, self.answer,
                             "창을 세울지를 화면이 갈래로 판정한다: %s" % w)

    # ---------- ④ 두 말은 슬롯도 둘 ----------

    def test_two_slots_for_two_ranks_of_speech(self):
        self.assertIn("title: d.message", self.dlg, "제목 칸이 없다")
        self.assertIn("desc: d.note", self.dlg,
                      "부가 사실이 설 슬롯이 없다 — 한 슬롯에 겹치면 강조가 둘")

    def test_the_screen_does_not_split_the_sentence_itself(self):
        """서버 문장을 화면이 마침표로 쪼개면 문장 안 쉼표에서 깨진다."""
        for bad in (".split(", "indexOf(\".\")", "lastIndexOf(\".\")"):
            self.assertNotIn(bad, self.dlg + self.answer,
                             "화면이 서버 문장을 손으로 쪼갠다: %s" % bad)


class ThePressedHandKeepsItsPlace(unittest.TestCase):
    """누른 손은 그 자리에 남는다 (REQ-20260831-009).

    049 로 성공 경로의 창이 사라지자 키보드 손이 갈 곳을 잃었다. CDP 실측:
    ▶ 에 포커스를 주고 누르면 `activeAfter=BODY` — 눌린 단추를 `disabled` 로
    만드는 순간 브라우저가 포커스를 걷고, 이어지는 재그리기가 그 단추 개체
    자체를 지운다. 창이 있던 동안에는 창이 landmark 노릇을 했지만 이제 없다.

    잠금을 지는 것은 원래 `wokePending`/`stopPending` 이지 `disabled` 가
    아니다 — 누르는 자리 둘이 그 관문을 먼저 지난다. 그러니 계약은 셋이다.
      ① 잠금은 **보이되 닿는** `aria-disabled` 로 말한다 (포커스가 남는다).
      ② 연타 관문은 그대로다 — 잠금 표시를 바꾼다고 두 번 나가면 안 된다.
      ③ 재그리기를 건너 손이 같은 카드의 손잡이로 돌아온다. 다만 **내 자리였을
         때만**, 그리고 **창이 서 있지 않을 때만** — 창이 서면 손은 창의 것이다.
    """

    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        cls.face = _grab(cls.src, "faceDeed")
        cls.keep = _grab(cls.src, "keepDeedFocus")
        cls.doc = _grab(cls.src, "wakeDoc")

    # ---------- ① 잠금은 포커스를 걷지 않는다 ----------

    def test_the_lock_no_longer_takes_the_focus_away(self):
        self.assertNotIn("b.disabled", self.face,
                         "눌린 손잡이를 아직 disabled 로 잠근다 — 브라우저가 "
                         "포커스를 걷어 키보드 손이 body 로 떨어진다")
        self.assertIn('setAttribute("aria-disabled", "true")', self.face)
        self.assertIn('removeAttribute("aria-disabled")', self.face,
                      "잠금이 풀려도 표시가 남는다")

    def test_the_lock_is_written_once(self):
        """그린 얼굴과 칠하는 얼굴이 같은 말을 해야 한다 — 상수 하나."""
        self.assertIn('const DEED_BUSY = \' aria-disabled="true"\'', self.src)
        self.assertNotRegex(self.src, r'\$\{going \? " disabled" : ""\}',
                            "아직 disabled 로 그리는 손잡이가 남아 있다")

    def test_the_paint_follows_the_new_lock(self):
        """CSS 가 옛 표시를 보고 있으면 눌린 얼굴이 통째로 사라진다."""
        css = _css(self.src)
        for who in ("wake", "stop"):
            self.assertIn('button.%s[aria-disabled="true"]' % who, css,
                          "%s 의 눌린 얼굴이 새 잠금 표시를 안 본다" % who)
            self.assertNotIn("button.%s[disabled]" % who, css,
                             "%s 규칙이 아직 옛 표시를 본다" % who)

    # ---------- ② 연타 관문은 그대로 ----------

    def test_the_double_press_gate_is_untouched(self):
        """잠금 표시를 바꾼다고 두 번 나가면 안 된다 — 관문은 눌리는 자리에."""
        self.assertIn("if (wokePending(id)) return;", self.doc)
        self.assertIn("if (stopPending(id)) return;", _grab(self.src, "stopDoc"))

    # ---------- ③ 재그리기를 건너 자리가 남는다 ----------

    def test_the_focus_crosses_the_redraw(self):
        self.assertIn("await keepDeedFocus(id, () => refreshCatalog(true))",
                      self.doc, "재그리기가 손잡이를 갈아 끼우는데 손이 "
                                "따라가지 않는다")

    def test_it_only_returns_a_hand_that_was_there(self):
        self.assertIn("if (!mine || held.isConnected) return;", self.keep,
                      "남의 자리를 빼앗거나, 멀쩡한 자리를 다시 잡는다")

    def test_an_open_window_owns_the_hand(self):
        """창이 서 있으면 뒤의 카드로 포커스를 끌어오지 않는다."""
        self.assertIn(".dlgbox", self.keep,
                      "창이 서 있는지 보지 않고 포커스를 가져간다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
