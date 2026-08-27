"""끝난 요청은 하루가 지나면 **열에서 내린다** (REQ-20260827-057-62x6).

사용자 요청: "보드화면에서 완료가 된 항목은 완료된지 하루가 지나면 목록에서
사라지게 해줘. 너무 많이 쌓이게 된다."

1차는 "+N 더 보기"로 **접어 두는** 쪽으로 만들었다가 반려됐다:

  "이런식으로 해달라는게 아니고 목록이 너무 길어서 의미가 없이 스크롤이
   힘들어지니까 아예 스크롤이 안되게 그냥 접은 내용에도 없애달라고.
   그리고 접기는 원래 접는 기능이 괜찮았다."

접는 것은 줄인 것이 아니라 숨긴 것이다 — 펼치면 322건이 그대로 쏟아지고
스크롤은 여전히 힘들다. 그래서 이 요청의 답은 둘이다.

  ① 하루가 지난 끝난 요청은 **목록에 없다.** 접은 안쪽에도 없다.
  ② **원래 접기(끝난 열 3건 + "N개 더 보기")는 그대로다.** 사용자가
     "원래 접는 기능이 괜찮았다"고 못 박았다.

두 잣대는 겹치는 것이 아니라 순서다: 먼저 하루로 **내리고**, 남은 것에
원래 개수 접기를 적용한다.

내린 것을 **설명하지도 않는다**. 2차에 "하루가 지난 완료 252건은 목록에서
내렸다 — Docs 에 그대로 있다"를 한 줄 달았다가 다시 지적받았다:

  "이런건 문구로 남기지마라"

하루가 지난 것이 안 보이는 건 이 화면이 늘 도는 규칙이지 사고가 아니다 —
규칙을 매번 변명하는 줄은 자리만 먹고 곧 안 읽힌다. (사용자가 건 조건 때문에
안 보이는 경우는 다르다. 그건 원인을 짚어 줘야 풀 수 있어서 이름으로 말한다 —
REQ-20260827-054. 이쪽은 풀 것이 없다.) 남긴 것은 열이 비었을 때의 이름표
"하루 안에 완료된 요청 없음" 하나뿐이다 — 322건이 있는데 "완료된 요청 없음"
이라고만 하면 그건 거짓이 되기 때문이다.

잣대가 되는 시계는 `status_since` 다 — 끝난 때이지 마지막으로 만진 때가
아니다. `updated` 로 세웠다가 이미 한 번 반려를 받았다(REQ-20260827-016).

이 테스트는 정규식으로 "그렇게 생겼다"를 보는 대신 `colHTML` 을 그대로 떼어
node 로 **실행**한다 (test_paste_fold 와 같은 방식). node 가 없으면 실행 검증은
건너뛰되 소스 계약(아래 Contract)은 그대로 검사한다.

실행: python3 tests/ board_done_window
"""
import glob
import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")

DAY = 24 * 60 * 60 * 1000


def find_node():
    n = shutil.which("node") or shutil.which("nodejs")
    if n:
        return n
    # WSL/컨테이너에 node 가 없어도 VS Code 서버가 하나 들고 있는 경우가 많다
    for pat in ("/home/*/.vscode-server/bin/*/node",
                "/root/.vscode-server/bin/*/node"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


NODE = find_node()


def read_src():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def grab(src, pattern, what):
    m = re.search(pattern, src, re.S | re.M)
    assert m, f"{what} 를 못 찾았다 — 이름이 바뀌었으면 이 테스트도 따라가야 한다"
    return m.group(0)


class BoardDoneWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = read_src()
        cls.win = grab(cls.src, r"const TERMINAL_WINDOW_MS = [^\n]*;", "TERMINAL_WINDOW_MS")
        cls.at = grab(cls.src, r"const termAt = [^\n]*;", "termAt")
        cls.word = grab(cls.src, r"const TERM_WORD = \{[^\n]*\};", "TERM_WORD")
        cls.lim = grab(cls.src, r"const COL_LIMIT = [^\n]*;", "COL_LIMIT")
        cls.col = grab(cls.src, r"^function colHTML\(key, label, color, grp\)\{.*?^\}",
                       "colHTML")

    # ---------- node 로 실제 실행 ----------

    def render_rel(self, key, specs, expanded=False):
        """상대 시각(`ago` = 몇 ms 전)을 node 안에서 실제 ISO 로 바꿔 렌더하고,
        어떤 카드가 보이는지 돌려준다. 고정 시각을 박아 두면 하루만 지나도
        테스트가 스스로 늙는다."""
        js_rows = json.dumps([dict(s) for s in specs])
        if not NODE:
            self.skipTest("node 없음 — 실행 검증 생략 (소스 계약은 별도 검사)")
        script = "\n".join([
            'const TERMINAL = new Set(["done","cancelled"]);',
            self.lim, self.win, self.at, self.word,
            "const cardHTML = r => `<c>${r.id}</c>`;",
            'const EMPTY_COL = {"in-progress": \'<div class="colempty">진행 중인 요청 없음</div>\','
            ' done: \'<div class="colempty">완료된 요청 없음</div>\'};',
            "const expanded = new Set(%s);" % ('["col:%s"]' % key if expanded else "[]"),
            self.col,
            "const rows = %s.map(r => {" % js_rows,
            "  const o = {id: r.id, type: 'request'};",
            "  if (r.ago !== undefined && r.ago !== null)",
            "    o[r.field || 'status_since'] = new Date(Date.now() - r.ago).toISOString();",
            "  return o; });",
            "const html = colHTML(%s, %s, 'var(--x)', rows);" % (
                json.dumps(key), json.dumps(key)),
            "console.log(JSON.stringify({html,"
            " cards: (html.match(/<c>([^<]*)<\\/c>/g)||[]).map(s=>s.slice(3,-4)),"
            " badge: (html.match(/class=\"n\"[^>]*>([^<]*)</)||[])[1],"
            " more: (html.match(/class=\"more\"[^>]*>([^<]*)</)||[])[1] || null,"
            " cut: (html.match(/class=\"colcut\">([^<]*)</)||[])[1] || null,"
            " empty: (html.match(/class=\"colempty\">([^<]*)</)||[])[1] || null}));",
        ])
        p = subprocess.run([NODE, "-e", script], capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0, f"node 실행 실패:\n{p.stderr[-2000:]}")
        return json.loads(p.stdout.strip().splitlines()[-1])

    # W1 — 이 요청의 전부: 하루가 지난 완료는 목록에서 사라진다
    def test_w1_older_than_a_day_drops_out(self):
        r = self.render_rel("done", [
            {"id": "FRESH-1", "ago": 60 * 1000},
            {"id": "FRESH-2", "ago": 5 * 60 * 60 * 1000},
            {"id": "OLD-1", "ago": DAY + 60 * 1000},
            {"id": "OLD-2", "ago": 40 * DAY},
        ])
        self.assertEqual(r["cards"], ["FRESH-1", "FRESH-2"],
                         "하루가 지난 완료가 목록에 남아 있다")

    # W2 — 반려의 핵심: 내린 것을 되펼치는 버튼을 만들지 않는다
    def test_w2_dropped_items_have_no_expander(self):
        """"접은 내용에도 없애달라" — 펼치면 다시 나오는 것은 내린 것이 아니다."""
        r = self.render_rel("done", [
            {"id": "FRESH", "ago": 1000},
            {"id": "OLD-1", "ago": 2 * DAY},
            {"id": "OLD-2", "ago": 3 * DAY},
        ])
        self.assertIsNone(r["more"],
                          "하루 지난 것을 되펼치는 버튼이 있다 — 목록이 다시 길어진다")
        self.assertNotIn("하루 지난", str(r["more"] or ""))

    def test_w2b_the_rule_does_not_apologise_for_itself(self):
        """내린 것을 설명하는 문구를 두지 않는다.

        2026-08-27 사용자: "이런건 문구로 남기지마라". 하루가 지난 것이 안 보이는
        건 이 화면이 **늘 도는 규칙**이지 사고가 아니다 — 규칙을 매번 변명하는
        줄은 자리만 먹고 곧 안 읽힌다.

        사용자가 건 조건 때문에 안 보이는 경우와 헷갈리지 말 것: 그쪽은 원인을
        짚어 줘야 풀 수 있어서 이름으로 말한다(REQ-20260827-054). 이쪽은 풀
        것이 없다."""
        r = self.render_rel("done", [
            {"id": "FRESH", "ago": 1000},
            {"id": "OLD-1", "ago": 2 * DAY},
            {"id": "OLD-2", "ago": 3 * DAY},
        ])
        self.assertIsNone(r["cut"], "규칙을 변명하는 줄이 남아 있다")
        for w in ("내렸다", "Docs 에 그대로", "하루가 지난"):
            self.assertNotIn(w, r["html"], "설명 문구 %r 이 남아 있다" % w)

    # W3 — 펼쳐도 하루 안의 것뿐이다
    def test_w3_expanding_never_brings_back_the_dropped(self):
        specs = [{"id": "F%d" % i, "ago": 1000 + i} for i in range(5)] + [
            {"id": "OLD-1", "ago": 2 * DAY}, {"id": "OLD-2", "ago": 3 * DAY}]
        r = self.render_rel("done", specs, expanded=True)
        self.assertEqual(r["cards"], ["F0", "F1", "F2", "F3", "F4"],
                         "펼치니 하루 지난 것이 다시 나온다")

    # W4 — 원래 접기는 그대로다 (사용자가 명시적으로 지켜 달라고 했다)
    def test_w4_the_original_collapse_is_untouched(self):
        specs = [{"id": "F%d" % i, "ago": 1000 + i} for i in range(6)]
        r = self.render_rel("done", specs)
        self.assertEqual(len(r["cards"]), 3, "끝난 열의 기본 3건 접기가 사라졌다")
        self.assertEqual(r["more"], "3개 더 보기", "원래 접기 문구가 바뀌었다")
        r2 = self.render_rel("done", specs, expanded=True)
        self.assertEqual(len(r2["cards"]), 6)
        self.assertEqual(r2["more"], "접기", "펼친 뒤 되접을 길이 없다")

    # W5 — 조용한 하루에 "완료된 요청 없음"은 거짓말이다
    def test_w5_quiet_day_says_which_day_it_means(self):
        r = self.render_rel("done", [{"id": "OLD-1", "ago": 2 * DAY},
                                     {"id": "OLD-2", "ago": 9 * DAY}])
        self.assertEqual(r["cards"], [])
        # 빈 상태의 이름표는 남긴다 — 322건이 있는데 "완료된 요청 없음"이라고만
        # 하면 거짓이 된다. 이건 변명이 아니라 **지금 이 열이 무엇인지**의 이름이고,
        # 열이 비었을 때만 나온다.
        self.assertEqual(r["empty"], "하루 안에 완료된 요청 없음")
        self.assertIsNone(r["cut"], "빈 열에까지 설명 문구를 붙였다")

    # W6 — 진짜로 한 건도 없으면 원래 빈 상태 문구 그대로
    def test_w6_truly_empty_keeps_its_own_words(self):
        r = self.render_rel("done", [])
        self.assertEqual(r["empty"], "완료된 요청 없음")
        self.assertIsNone(r["cut"])
        self.assertIsNone(r["more"])

    # W7 — cancelled 도 같은 자, 다만 제 말로
    def test_w7_cancelled_shares_the_rule(self):
        r = self.render_rel("cancelled", [{"id": "FRESH", "ago": 1000},
                                          {"id": "OLD", "ago": 3 * DAY}])
        self.assertEqual(r["cards"], ["FRESH"])
        self.assertIsNone(r["cut"])
        # 열이 비면 그때만 제 말("취소")로 이름을 붙인다
        r2 = self.render_rel("cancelled", [{"id": "OLD", "ago": 3 * DAY}])
        self.assertEqual(r2["empty"], "하루 안에 취소된 요청 없음")

    # W8 — 살아 있는 컬럼은 건드리지 않는다 (개수 잣대 그대로)
    def test_w8_live_columns_unchanged(self):
        specs = [{"id": "R%d" % i, "ago": (i + 1) * 10 * DAY} for i in range(9)]
        r = self.render_rel("in-progress", specs)
        self.assertEqual(len(r["cards"]), 7,
                         "살아 있는 컬럼까지 시간으로 잘랐다 — 진행 중인 일에는 "
                         "'며칠 됐나'가 사라질 이유가 못 된다")
        self.assertEqual(r["more"], "2개 더 보기")
        self.assertEqual(r["badge"], "9", "살아 있는 컬럼의 숫자는 전체 건수다")
        self.assertIsNone(r["cut"])

    # W9 — 경계는 정확히 24시간
    def test_w9_boundary_is_exactly_one_day(self):
        r = self.render_rel("done", [
            {"id": "IN", "ago": DAY - 60 * 1000},
            {"id": "OUT", "ago": DAY + 60 * 1000},
        ])
        self.assertEqual(r["cards"], ["IN"])

    # W10 — 컬럼 숫자는 **그 열에 있는 것**을 센다
    def test_w10_badge_counts_what_is_in_the_column(self):
        r = self.render_rel("done", [{"id": "F1", "ago": 1000},
                                     {"id": "F2", "ago": 2000},
                                     {"id": "O1", "ago": 5 * DAY},
                                     {"id": "O2", "ago": 6 * DAY}])
        self.assertEqual(r["badge"], "2",
                         "322건이 그대로 적혀 있으면 '쌓인다'는 느낌은 그대로다")
        # 펼쳐도 같은 수다 — 목록과 숫자가 어긋나지 않는다
        r2 = self.render_rel("done", [{"id": "F1", "ago": 1000},
                                      {"id": "O1", "ago": 5 * DAY}], expanded=True)
        self.assertEqual(r2["badge"], "1")

    # W11 — 시각을 못 읽는 문서는 최근 자리를 차지하지 않는다
    def test_w11_undated_docs_fall_to_the_archive(self):
        r = self.render_rel("done", [{"id": "FRESH", "ago": 1000},
                                     {"id": "NODATE", "ago": None}])
        self.assertEqual(r["cards"], ["FRESH"],
                         "근거 없이 '방금 끝난 것' 자리에 앉았다")

    # W12 — status_since 가 없으면 created 로 물러난다 (문서 세대차 대비)
    def test_w12_falls_back_to_created(self):
        r = self.render_rel("done", [{"id": "OLDGEN", "ago": 1000, "field": "created"}])
        self.assertEqual(r["cards"], ["OLDGEN"])

    # ---------- 소스 계약 (node 유무와 무관) ----------

    def test_c1_window_is_one_day_and_named(self):
        """C1. 하루라는 값이 코드 안에 흩어지지 않는다."""
        self.assertRegex(self.win, r"24 \* 60 \* 60 \* 1000")
        self.assertIn("TERMINAL_WINDOW_MS", self.col,
                      "colHTML 이 그 상수를 안 쓴다")

    def test_c2_uses_the_shared_terminal_set(self):
        """C2. '끝났다'의 정의를 새로 적지 않는다 — done 만 적으면 cancelled 가
        빠지고, 그 순간 같은 질문에 두 가지 답이 생긴다 (test_board_done_order B2)."""
        self.assertIn("TERMINAL.has(key)", self.col)
        self.assertNotIn('key === "done"', self.col,
                         "끝난 상태를 손으로 다시 적었다")

    def test_c3_cuts_by_the_clock_the_card_shows(self):
        """C3. 자르는 자와 카드가 보여주는 시계가 같아야 한다 — 정렬에서 이미
        한 번 밟은 실패다(REQ-20260827-016). 그래서 status_since 가 1순위다."""
        self.assertRegex(self.at, r"r\.status_since \|\| r\.updated \|\| r\.created")

    def test_c4_the_original_terminal_limit_survives(self):
        """C4. 원래 접기를 없애지 않는다 — 사용자가 지켜 달라고 한 그 기능이다."""
        self.assertRegex(self.src, r"COL_LIMIT_TERMINAL = 3\b",
                         "끝난 열의 원래 3건 접기가 사라졌다")
        self.assertIn("COL_LIMIT_TERMINAL", self.col)


if __name__ == "__main__":
    unittest.main()
