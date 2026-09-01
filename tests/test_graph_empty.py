"""빈 그래프가 이유를 말하는가 (REQ-20260826-039-62x6).

사용자는 "그래프 탭에 아무것도 보이지 않는다. 새로고침을 하면 보이긴 하던데…"
라고 썼다. 캡처를 보면 렌더가 실패한 게 아니다. 헤더 종류 필터가 `question`
하나로 좁혀 3건만 남겼는데, 그래프 범례에서는 그 `question` 이 꺼져 있었다.
교집합이 0이니 캔버스는 정직하게 아무것도 안 그렸다 — **다만 이유를 말하지
않았다.** 원인을 알려면 사용자가 위쪽 필터와 범례 두 곳을 스스로 대조해야 했다.

새로고침하면 보이는 것도 같은 얘기다: 헤더 필터는 새로고침에 풀리고 범례
설정은 브라우저에 남는다. 그래서 조합이 저절로 풀린다.

그러니 고칠 것은 그리기가 아니라 **빈 화면의 침묵**이다. 이 테스트가 지키는
계약은 넷이다.

  ① 노드가 0일 때만 안내가 뜬다 (그려진 그래프를 덮지 않는다).
  ② 원인별로 말이 다르다 — 문서 자체가 없음 / 필터가 0건으로 좁힘 /
     남은 문서의 종류를 범례에서 꺼 둠. 셋을 한 문장으로 뭉뚱그리면
     사용자는 여전히 어디를 눌러야 할지 모른다.
  ③ 되돌리는 버튼이 같이 있다 — 진짜 <button> 이라 키보드로도 닿는다.
  ④ 문구는 사용자 언어다. 내부 이름(gtypes·catalog·node·GRAPH_TYPES)이
     화면에 새면 설명이 아니라 암호가 된다.

픽셀이 아니라 이 계약만 검사한다. 실제 렌더는 사람의 캡처 확인 몫이다.

실행: python3 tests/ graph_empty
"""
import os
import re
import unittest

import websrc  # 공용 원문 도우미 (REQ-20260830-029)
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()

# 화면에 절대 새면 안 되는 내부 이름들
JARGON = ("gtypes", "GRAPH_TYPES", "catalog", "renderGraph", "localStorage",
          "s9gtypes", "TYPE_ORDER", "노드", "필터링", "렌더")


class GraphEmpty(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()

    # ---------- ① 뜨는 조건 ----------

    def test_empty_notice_only_when_nothing_is_drawn(self):
        """그릴 노드가 하나라도 있으면 안내는 뜨지 않는다."""
        m = re.search(r"const gEmpty = [^;]+;", self.src)
        self.assertIsNotNone(m, "빈 상태 판정을 renderGraph 에서 찾지 못했다")
        self.assertRegex(m.group(0), r"nodes\.length\s*\?\s*null\s*:",
                         "노드가 있으면 null 이어야 한다")

    def test_notice_is_rendered_into_the_canvas_panel(self):
        """안내는 캔버스가 있는 자리에 뜬다 — 옆 레일이 아니라."""
        m = re.search(r'<canvas id="gcanvas">[\s\S]{0,400}?</div>', self.src)
        self.assertIsNotNone(m)
        self.assertIn("graphEmptyHTML(", m.group(0),
                      "빈 화면 안내가 캔버스 자리에 붙어 있어야 한다")

    # ---------- ② 원인별로 다른 말 ----------

    def test_three_causes_get_three_answers(self):
        """세 갈래를 각기 다른 문장으로 답한다."""
        blk = self._state_fn()
        self.assertRegex(blk, r"if \(!catalog\.length\)",
                         "문서 자체가 없는 경우를 먼저 가른다")
        self.assertRegex(blk, r"if \(!rows\.length\)",
                         "필터가 0건으로 좁힌 경우를 가른다")
        self.assertRegex(blk, r"gtypes\.has\(", "범례에서 꺼 둔 종류를 찾는다")
        msgs = re.findall(r'msg:\s*[`"]([^`"]+)', blk)
        self.assertGreaterEqual(len(msgs), 3, "원인별 문장이 셋 이상이어야 한다")
        self.assertEqual(len(msgs), len(set(msgs)), "문장이 서로 달라야 한다")

    def test_hidden_types_are_named_not_counted(self):
        """무엇이 꺼졌는지 이름으로 말한다 — '3건 숨김'만으로는 못 찾는다."""
        blk = self._state_fn()
        self.assertIn("KO", blk, "종류 이름을 한국어로 바꿔 말한다")
        for ko in ("요청", "지식", "질문", "세션"):
            self.assertIn(ko, blk, "%s 이름이 없다" % ko)

    def test_refresh_confusion_is_answered(self):
        """'새로고침하면 보이던데'에 화면이 답한다."""
        blk = self._state_fn()
        self.assertIn("새로고침", blk,
                      "새로고침하면 왜 보이는지 한 줄로 답해야 한다")

    # ---------- ③ 되돌리는 버튼 ----------

    def test_fix_is_a_real_button(self):
        """진짜 <button> 이다 — 키보드로 닿아야 한다."""
        m = re.search(r"<button class=\"gefix\"[^>]*data-gfix=", self.src)
        self.assertIsNotNone(m, "되돌리기 버튼을 찾지 못했다")

    def test_handler_covers_both_fixes(self):
        """필터 지우기와 종류 다시 켜기 둘 다 실제로 동작한다."""
        m = re.search(r'const gf = evEl\(e\.target\)\?\.closest\("\[data-gfix\]"\);'
                      r'[\s\S]*?\n  \}', self.src)
        self.assertIsNotNone(m, "data-gfix 핸들러가 없다")
        h = m.group(0)
        self.assertIn('"filters"', h)
        self.assertIn("#f-type", h, "종류 필터도 지워야 한다")
        self.assertIn("#f-mine", h, "'내 것만'도 필터다 — 안 풀면 버튼이 죽는다")
        self.assertIn("gtypes.add", h, "꺼 둔 종류를 다시 켠다")
        self.assertIn("s9gtypes", h, "다시 켠 상태를 저장한다")
        self.assertIn("render()", h)

    def test_button_carries_which_types_to_restore(self):
        """어떤 종류를 켤지 마크업이 들고 있다 — 핸들러가 다시 계산하지 않는다."""
        self.assertRegex(self.src, r"data-gtypes=")

    # ---------- ④ 문구와 시각 언어 ----------

    def test_copy_has_no_internal_names(self):
        """사용자 문장에 내부 이름이 새지 않는다."""
        blk = self._state_fn()
        for raw in re.findall(r'(?:msg|note|label):\s*[`"]([^`"]+)', blk):
            # 화면에 나가는 것은 값이 채워진 뒤의 글자다 — 자리표시자와 태그는 뺀다
            line = re.sub(r"\$\{[^}]*\}", "", raw)
            line = re.sub(r"<[^>]*>", "", line)
            for j in JARGON:
                self.assertNotIn(j, line, "내부 용어 %r 이 문구에 있다: %s" % (j, line))

    def test_no_color_fill_and_no_side_bar(self):
        """색면 하이라이트·좌측 세로 띠 금지 — 색은 글자로."""
        css = self._css()
        # 잉크 반전(누른 컨트롤)은 이 제품의 인터랙션 언어라 허용 — 금지 대상은
        # 장식용 색면이다. 그래서 --text/--bg 두 잉크만 통과시킨다.
        for bg in re.findall(r"background\s*:\s*([^;}]+)", css):
            self.assertIn(bg.strip(), ("none", "transparent", "var(--text)", "var(--bg)"),
                          "빈 상태에 색면을 깔지 않는다: %s" % bg)
        self.assertNotIn("border-left", css, "좌측 세로 띠 금지")
        # 꺼진 종류는 그 종류 색 글자로 말한다 — 위 범례 칩과 눈으로 이어지게.
        # TCOLOR 는 --t-* 토큰 맵이라 tone 이 바뀌어도 따라온다.
        self.assertIn("TCOLOR[t]", self._state_fn())

    def test_styles_are_token_only_and_theme_agnostic(self):
        """6개 tone 전부에서 성립하려면 색은 토큰으로만 쓴다."""
        css = self._css()
        websrc.no_hex(self, css)
        self.assertNotRegex(css, r"\[data-(?:skin|theme)=",
                            "특정 스킨/톤 전용 스타일이 아니다")
        self.assertIn("pointer-events", css,
                      "안내는 캔버스 드래그를 가로막지 않는다 — 버튼만 받는다")

    def test_notice_is_announced(self):
        """동적으로 나타나는 안내는 상태 변화로 알린다 (접근성)."""
        m = re.search(r'<div class="gempty"[^>]*>', self.src)
        self.assertIsNotNone(m)
        self.assertIn('role="status"', m.group(0))


    # ---------- ⑤ 되돌리는 손이 어디 있는지 화면이 짚는다 ----------
    #
    # 2026-08-27 반려: "범례를 선택했는데도 화면이 바뀌지 않는다."
    # 실브라우저로 재현해 보니 클릭은 멀쩡히 닿고(hit-test 통과) 핸들러도 돌고
    # 저장까지 된다. 문제는 **범례에서 취소선이 그어진 항목이 셋인데 안내는
    # 어느 것인지 짚어 주지 않는다**는 것이었다. 사용자는 한글 "질문"을 영문
    # 대문자 QUESTION 으로 스스로 옮겨야 했고, 그중 아닌 것(KNOWLEDGE·SESSION)
    # 을 누르면 그릴 것이 여전히 0건이라 안내가 같은 문장을 다시 그렸다 —
    # 글자도 그림도 그대로. 사용자에게는 죽은 컨트롤로 보인다.
    #
    # 기존 12개 계약은 마크업과 핸들러의 **존재**만 봤기 때문에 이걸 통과시켰다
    # (REQ-20260826-025 와 같은 계열의 구멍). 그래서 여기서는 "눌렀을 때 화면이
    # 사용자에게 무엇을 돌려주는가"를 계약으로 박는다.

    def test_msg_does_not_send_the_user_upward(self):
        """주 문장이 '위쪽'을 가리키면 사용자는 바로 아래 버튼을 건너뛴다.

        반려의 실제 경로가 이것이었다 — 안내가 "위쪽 범례에서…"라고 시선을
        위로 보냈고, 사용자는 버튼 대신 범례로 가서 엉뚱한 항목을 눌렀다."""
        blk = self._state_fn()
        for raw in re.findall(r'msg:\s*`([^`]+)`', blk):
            line = re.sub(r"<[^>]*>", "", re.sub(r"\$\{[^}]*\}", "", raw))
            for w in ("위쪽", "아래", "위의", "여기를"):
                self.assertNotIn(w, line,
                    "주 문장은 위치를 가리키지 않는다(행동은 버튼이 맡는다): %s" % line)

    def test_notice_names_the_legend_label_verbatim(self):
        """범례에 실제로 찍힌 글자(QUESTION)를 그대로 준다.

        한국어 이름(질문)만 주면 사용자가 영문 대문자 라벨로 옮겨 찾아야 한다 —
        취소선이 그어진 항목이 여럿일 때 그 번역이 곧 오클릭이 된다."""
        blk = self._state_fn()
        self.assertIn("toUpperCase()", blk,
                      "범례 라벨(대문자 타입명)을 문구에 그대로 넣어야 한다")

    def test_legend_marks_the_type_to_click(self):
        """안내가 떠 있는 동안 눌러야 할 범례 항목을 화면이 지목한다."""
        # 항목이 무슨 태그인지는 이 계약의 관심사가 아니다 — 지목 표시가 붙느냐만
        # 본다. (REQ-20260827-007 에서 span → button 으로 바뀌었다: 키보드로
        # 닿게 하려면 진짜 버튼이어야 한다.)
        m = re.search(r'<(?:span|button)[^>]*class="gtype\$\{[\s\S]{0,300}?data-gtype=',
                      self.src)
        self.assertIsNotNone(m, "범례 항목 마크업을 찾지 못했다")
        self.assertIn("want", m.group(0),
                      "눌러야 할 항목에 지목 표시가 붙지 않는다")

    def test_mark_and_button_read_the_same_source(self):
        """지목 표시와 버튼이 **같은 출처**에서 켤 종류를 읽는다.

        마크업과 핸들러가 서로 다른 이름을 보다가 조용히 갈라지는 것이
        REQ-20260826-025 의 결함이었다. 여기서는 st.fix.types 하나만 본다."""
        m = re.search(r"const gWant = [^;]+;", self.src)
        self.assertIsNotNone(m, "지목 대상 집합을 renderGraph 에서 찾지 못했다")
        self.assertIn("fix", m.group(0),
                      "버튼과 같은 st.fix.types 를 써야 갈라지지 않는다")
        self.assertIn("types", m.group(0))

    def test_want_mark_keeps_the_off_signal_and_paints_no_fill(self):
        """지목은 '꺼져 있다'는 사실을 지우지 않고, 색면이 아니라 잉크 점선이다."""
        m = re.search(r"\.gtype\.want\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, ".gtype.want 스타일이 없다")
        css = m.group(1)
        self.assertIn("dashed", css, "지목은 점선 아웃라인으로 — 색면 금지")
        self.assertNotIn("background", css, "색면 하이라이트 금지")
        self.assertNotIn("text-decoration:none", css.replace(" ", ""),
                         "취소선을 지우면 '꺼져 있다'는 사실이 사라진다")
        websrc.no_hex(self, css)
    def test_toggle_handler_records_what_was_turned_on(self):
        """켠 종류를 기록한다 — 끈 것은 기록하지 않는다(의도적 축소다)."""
        m = re.search(r'const gt2 = evEl\(e\.target\)\?\.closest\("\[data-gtype\]"\);'
                      r'[\s\S]*?\n  \}', self.src)
        self.assertIsNotNone(m, "범례 토글 핸들러가 없다")
        h = m.group(0)
        self.assertRegex(h, r"gLastOn\s*=",
                         "방금 켠 종류를 기록해야 헛클릭을 인정할 수 있다")
        self.assertIn("gtypes.has(t)", h, "켠 경우와 끈 경우를 갈라야 한다")

    def test_ineffective_toggle_is_acknowledged(self):
        """켰는데도 화면이 그대로면 화면이 그 사실을 말한다.

        같은 문장을 말없이 다시 그리는 것이 반려의 직접 원인이었다."""
        blk = self._state_fn()
        self.assertIn("gLastOn", blk, "방금 켠 종류를 안내가 참조하지 않는다")
        self.assertRegex(blk, r"\back\s*:", "헛클릭을 인정하는 자리가 없다")
        acks = [t for t in re.findall(r"`([^`]*)`", blk) if "켰지만" in t]
        self.assertTrue(acks, "헛클릭을 인정하는 문장이 없다")
        self.assertTrue(any("그대로" in a for a in acks),
                        "무엇이 안 바뀌었는지 사용자 말로 말해야 한다")
        self.assertIn('class="geack"', self.src, "인정 줄을 그리는 자리가 없다")

    def test_ack_does_not_outlive_the_click(self):
        """되돌리기가 성공했거나 조건이 바뀌면 인정 줄은 남지 않는다."""
        m = re.search(r'const gf = evEl\(e\.target\)\?\.closest\("\[data-gfix\]"\);'
                      r'[\s\S]*?\n  \}', self.src)
        self.assertIsNotNone(m)
        self.assertRegex(m.group(0), r"gLastOn\s*=\s*null",
                         "버튼으로 되돌린 뒤에도 인정 줄이 남으면 거짓말이 된다")
        m2 = re.search(r'\["#q","#q-body"[\s\S]{0,400}?\}\)\);', self.src)
        self.assertIsNotNone(m2, "필터 변경 리스너를 찾지 못했다")
        self.assertRegex(m2.group(0), r"gLastOn\s*=\s*null",
                         "조건이 바뀌면 직전 클릭에 대한 인정은 무효다")

    # ---------- ⑥ 범인은 범례가 아니라 헤더일 수 있다 (REQ-20260827-054) ----------
    #
    # 사용자: "이미지를 확인해봐 지금 뭔가 제대로 동작하지 않는것같다."
    # 캡처를 재현해 보니 그래프는 멀쩡히 돌고 있었다. 헤더 종류 조건이
    # `question` 하나로 좁혀 27건만 남겼고, 사용자는 범례에서 REQUEST 를 켰다.
    # 요청은 헤더 조건에서 이미 걸러진 뒤라 화면은 그대로였다.
    #
    # 그때 화면이 한 말은 "지금 조건에 요청은 없다"였다 — **조건**이라고만 했다.
    # 범인의 이름을 부르지 않으면 되돌릴 자리를 못 찾고, 못 찾으면 고장으로
    # 읽힌다. 그리고 그 자리에 있던 유일한 버튼("질문 다시 켜기")은 사용자가
    # 방금 말한 것("요청을 보여 달라")과 다른 것을 한다.
    #
    # 그래서 계약은 셋이다: ① 범인을 이름과 값으로 부른다 ② 되돌리는 손이
    # 그 범인 하나만 푼다 ③ 화면에서도 그 자리를 짚는다.

    def test_header_condition_is_named_with_its_value(self):
        """범인이 헤더 조건이면 이름과 지금 값을 함께 말한다."""
        blk = self._state_fn()
        self.assertIn("condHiding(", blk, "범인을 찾는 자리가 없다")
        self.assertIn("condName(", blk, "조건을 이름으로 부르지 않는다")
        name = re.search(r"const condName = ([\s\S]*?);\n", self.src)
        self.assertIsNotNone(name, "condName() 을 찾지 못했다")
        self.assertIn("c.val()", name.group(1),
                      "이름만으로는 못 찾는다 — 지금 걸린 값을 함께 말해야 한다")

    def test_every_header_condition_can_be_named_and_undone(self):
        """헤더의 조건 여섯 축이 모두 이름·되돌리는 손을 가진다."""
        m = re.search(r"const HCOND = \[[\s\S]*?\n\];", self.src)
        self.assertIsNotNone(m, "헤더 조건 목록을 찾지 못했다")
        h = m.group(0)
        for sel in ("#q", "#f-user", "#f-mine", "#f-project", "#f-tag", "#f-type"):
            self.assertIn(sel, h, "%s 조건이 목록에 없다" % sel)
        for ko in ("검색어", "사용자", "내 것만", "프로젝트", "태그", "종류"):
            self.assertIn(ko, h, "%s 를 사용자 말로 부르지 않는다" % ko)
        self.assertEqual(h.count("clear:"), 6, "조건마다 되돌리는 손이 있어야 한다")
        # 한국어는 조사가 다르다 — '내 것만'은 걸리는 게 아니라 켜지고, 지우는 게
        # 아니라 끈다. 한 문장 틀에 밀어 넣으면 화면에 비문이 나간다.
        self.assertIn("켜져 있다", h)
        self.assertIn("끄면", h)

    def test_only_the_guilty_condition_is_cleared(self):
        """되돌리기는 범인 하나만 푼다 — 나머지 조건은 사용자가 걸어 둔 것이다."""
        m = re.search(r'const gf = evEl\(e\.target\)\?\.closest\("\[data-gfix\]"\);'
                      r'[\s\S]*?\n  \}', self.src)
        self.assertIsNotNone(m)
        h = m.group(0)
        self.assertIn("gcond", h, "조건 하나를 푸는 갈래가 없다")
        br = h[h.index("gcond"):]
        self.assertIn("c.clear()", br, "그 조건 자신의 손을 써야 한다")
        # 이 갈래에서 다른 컨트롤을 직접 만지면 '지우기'가 아니라 '초기화'가 된다
        self.assertNotIn('$("#f-user").value = ""', br)
        self.assertIn("data-gcond=", self.src, "버튼이 어느 조건인지 들고 있어야 한다")

    def test_button_and_mark_read_the_same_condition(self):
        """짚는 자리와 버튼이 같은 출처(fix.cond)를 읽는다."""
        m = re.search(r"markHeaderCause\(gEmpty[^;]*;", self.src)
        self.assertIsNotNone(m, "헤더 지목을 renderGraph 에서 찾지 못했다")
        self.assertIn("fix.cond", m.group(0),
                      "버튼과 같은 출처를 읽어야 말과 손이 갈라지지 않는다")

    def test_mark_does_not_outlive_the_notice(self):
        """안내가 사라지면 지목도 사라진다 — 남으면 거짓말이 된다."""
        m = re.search(r"function markHeaderCause\(sel\)\{[\s\S]*?\n\}", self.src)
        self.assertIsNotNone(m, "markHeaderCause() 를 찾지 못했다")
        self.assertIn("classList.remove", m.group(0), "이전 지목을 지우지 않는다")
        r = re.search(r"function render\(\)\{[\s\S]{0,400}", self.src)
        self.assertIn("markHeaderCause(null)", r.group(0),
                      "다른 탭으로 가도 지목이 남는다")

    def test_header_mark_is_ink_dashes_not_a_fill(self):
        """헤더 지목도 잉크 점선이다 — 색면·세로 띠 금지, 색 하드코딩 금지."""
        m = re.search(r"\.fgroup \.want\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, ".fgroup .want 스타일이 없다")
        css = m.group(1)
        self.assertIn("dashed", css)
        self.assertNotIn("background", css, "색면 하이라이트 금지")
        self.assertNotIn("border-left", css, "좌측 세로 띠 금지")
        websrc.no_hex(self, css)
    def test_no_guess_when_several_conditions_overlap(self):
        """범인이 하나로 좁혀지지 않으면 지목하지 않는다."""
        m = re.search(r"function condHiding\(type\)\{[\s\S]*?\n\}", self.src)
        self.assertIsNotNone(m, "condHiding() 을 찾지 못했다")
        self.assertRegex(m.group(0), r"return null;",
                         "못 좁히면 물러나야 한다 — 틀린 범인은 침묵보다 나쁘다")
        blk = self._state_fn()
        self.assertRegex(blk, r"if \(h\)\{",
                         "범인을 못 찾았을 때 기존 갈래로 물러나야 한다")

    def test_absent_type_is_not_blamed_on_the_header(self):
        """기록 자체에 없는 종류를 헤더 탓으로 돌리지 않는다."""
        blk = self._state_fn()
        self.assertRegex(blk, r"catalog\.some\(r => r\.type === gLastOn\)",
                         "기록에 그 종류가 있는지 먼저 확인해야 한다")

    def test_counting_can_drop_one_condition_at_a_time(self):
        """조건을 하나씩 빼고 다시 셀 수 있어야 범인을 특정한다."""
        m = re.search(r"function filtered\(skipQ, skipType, skip\)\{[\s\S]*?\n\}",
                      self.src)
        self.assertIsNotNone(m, "filtered() 가 조건 하나를 뺄 수 없다")
        f = m.group(0)
        for k in ("q", "type", "user", "project", "tag", "mine"):
            self.assertIn('off("%s")' % k, f, "%s 축을 뺄 수 없다" % k)

    # ---------- helpers ----------

    def _state_fn(self):
        m = re.search(r"function graphEmptyState\(rows\)\{[\s\S]*?\n\}", self.src)
        self.assertIsNotNone(m, "graphEmptyState() 를 찾지 못했다")
        return m.group(0)

    def _css(self):
        return websrc.css_section(self, self.src, r"/\* -+ 그래프 빈 화면")


if __name__ == "__main__":
    unittest.main(verbosity=2)
