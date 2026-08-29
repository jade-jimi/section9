"""점과 손잡이는 한 벌이다 — 화면 몫 라운드2 (REQ-20260828-041-62x6, 2차 반려).

사용자가 같은 기능을 두 번 반려했다: "안된다 이 기능도."

라운드1이 서버에서 두 시계를 합쳤다(`stall_mins` 가 live_kind 를 읽는다). 화면에는
그때 **두 개의 갈래**가 남아 있었다.

  ① `!bl.length` — 카드만 가진 관문. 선행 대기 줄이 선 요청은 카드에서 멈춤 줄과
     손잡이를 통째로 잃었는데, 문서 화면은 그 관문을 몰라 같은 요청에 손잡이를
     줬다. **같은 요청이 두 자리에서 다른 말을 한다** — 판정 단추가 세 번
     반려됐던 그 결함(REQ-20260828-007)과 같은 모양이다.
  ② 점은 `live_kind` 를, 손잡이는 `stalled_mins` 를 각자 읽었다. 서버가 둘을
     한 벌로 만들어도 화면이 두 필드를 따로 읽는 한, 한쪽만 서는 조합이 남는다
     — 그것이 사용자가 본 "멈췄다고 적혔는데 누를 게 없는 카드"다.

그래서 계약은 하나로 줄인다: **멈춤 술어는 `stallState(r)` 하나뿐이고, 점·줄·
손잡이·열 머리 수·정렬이 전부 그 하나를 먹는다.** 술어가 하나면 어긋날 자리가
없다 — 이 저장소가 판정 버튼에서 세 번, 멈춤 표시에서 두 번 배운 것이다.

실행: python3 tests/ stall_pair
"""
import glob
import json
import os
import re
import shutil
import subprocess
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()


def _find_node():
    n = shutil.which("node") or shutil.which("nodejs")
    if n:
        return n
    for pat in ("/home/*/.vscode-server/bin/*/node", "/root/.vscode-server/bin/*/node"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


NODE = _find_node()


def _code(js):
    """주석을 걷어낸 코드만 — 주석은 옛 필드 이름을 근거로 인용한다."""
    js = re.sub(r"/\*[\s\S]*?\*/", " ", js)
    return re.sub(r"(?m)^\s*//.*$", " ", js)


def _grab(src, name):
    m = re.search(r"\nfunction %s\([^)]*\)\{[\s\S]*?\n\}" % name, src)
    assert m, name
    return m.group(0)


class StallOnePredicate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        cls.state = _code(_grab(cls.src, "stallState"))
        cls.stall = _grab(cls.src, "stallHTML")
        cls.card = _code(_grab(cls.src, "cardHTML"))
        cls.col = _code(_grab(cls.src, "colHTML"))
        cls.board = _grab(cls.src, "renderBoard")
        cls.demo = _grab(cls.src, "stallProbe")
        cls.democ = _code(cls.demo)
        # 문서 화면의 멈춤 줄이 사는 자리 (loadDoc 안)
        cls.doc = _code(cls.src[cls.src.index("async function loadDoc("):])

    # ---------- F1. 술어는 하나 ----------
    def test_f1_single_predicate_exists(self):
        self.assertIn("function stallState(", self.src,
                      "멈춤 술어를 짓는 자리가 없다")
        # 술어는 서버가 준 두 신호를 **함께** 읽는다
        self.assertIn("stalled_mins", self.state, "술어가 분을 안 읽는다")
        self.assertIn("live_kind", self.state, "술어가 점의 근거를 안 읽는다")

    def test_f1_card_does_not_judge_again(self):
        """카드는 판정하지 않고 술어를 부른다 — 필드를 직접 재판정하면 두 벌이 된다."""
        self.assertIn("stallState(r)", self.card, "카드가 술어를 안 부른다")
        self.assertNotIn("stalled_mins", self.card,
                         "카드가 아직 stalled_mins 를 직접 판정한다 (술어가 두 벌)")

    def test_f1_document_does_not_judge_again(self):
        seg = self.doc[:self.doc.index("stallHTML") + 400] \
            if "stallHTML" in self.doc else self.doc
        self.assertIn("stallHTML(", seg, "문서 화면이 멈춤 줄을 안 짓는다")
        self.assertNotIn("stalled_mins", seg,
                         "문서 화면이 아직 stalled_mins 를 직접 판정한다")

    # ---------- F2. 카드와 문서가 같은 답 ----------
    def test_f2_no_blocker_gate_on_card(self):
        """선행 대기 줄이 있어도 손잡이를 뺏지 않는다.

        원래 규칙은 '같은 사실을 두 줄로 말하지 않는다'였고 옳다. 그러나 그 관문이
        지운 것은 문장 하나가 아니라 **행동 하나**였다 — 그리고 문서 화면은 그
        관문을 몰라서, 같은 요청이 카드에선 못 깨우고 문서에선 깨워졌다.
        선행 대기(관계)와 멈춤(시계)은 다른 사실이기도 하다: 선행이 안 끝난 채로
        아무도 안 붙어 있는 요청이야말로 사람이 깨워야 하는 것이다.
        """
        m = re.search(r"const stall\s*=([\s\S]{0,300}?);\n", self.card)
        self.assertTrue(m, "멈춤 줄을 짓는 자리가 없다")
        self.assertNotIn("bl.length", m.group(1),
                         "선행 대기가 아직 멈춤 손잡이를 지운다 (카드·문서 비대칭)")

    def test_f2_both_call_the_same_builder(self):
        self.assertIn("stallHTML(", self.card)
        self.assertIn("stallHTML(", self.doc)

    # ---------- F3. 그려 놓고 못 누르는 카드가 없다 ----------
    def test_f3_stopped_dot_always_has_a_handle(self):
        """정지 마크가 서는 조건 = 손잡이가 서는 조건.

        문(멈췄나?)은 서버가 지금 다시 잰 `stalled_mins` 하나가 연다. 색인에 굳은
        작업자 기록(`live_kind`)은 문 안에서 **얼굴만** 고른다 — 어제의 정지가
        오늘 카드를 칠하고 손잡이는 없던 자리가 그것이다.
        """
        self.assertIn("stalled_mins", self.state, "문을 여는 것이 서버의 분이 아니다")
        self.assertIn("spawn_failed", self.state, "얼굴을 고르는 자리가 없다")
        self.assertIn("face", self.state, "얼굴을 돌려주지 않는다")
        # 손잡이를 짓는 자리는 하나뿐, 그리고 안 멈춘 행은 빈 문자열
        self.assertEqual(1, self.stall.count("data-wake="),
                         "손잡이를 짓는 자리가 하나가 아니다")
        self.assertIn('return "";', self.stall,
                      "안 멈춘 행을 부르는 쪽이 걸러야 한다 — 조건이 두 벌이 된다")

    # ---------- F4. 거꾸로도 한 벌 ----------
    def test_f4_handle_implies_stopped_dot(self):
        """분이 실린 행의 점은 멈춤 모양이다 — 손잡이만 있고 점은 조용한 카드 금지."""
        i = self.card.index("livedot")
        self.assertIn("stallState(r)", self.card[:i],
                      "점을 고르기 전에 멈춤 술어를 읽지 않는다")
        # 옛 갈래: 멈춤인데 속 빈 회색 원(off)으로 그리던 자리 — off 는 이제
        # "모름"(스트림 조용함)에만 남는다. 멈춤을 그리는 off 는 없어야 한다.
        for mm in re.finditer(r'livedot off" title="([^"]*)"', self.card):
            self.assertNotIn("진전이 없다", mm.group(1),
                             "멈춤이 아직 .livedot.off(모름의 마크)로 그려진다")
        seg = self.card[i - 600 if i > 600 else 0:]
        on = seg.index("livedot on")
        stopped = seg.index("dot-stopped")
        self.assertLess(stopped, on,
                        "초록 점멸이 멈춤보다 먼저 걸린다 — 멈춘 것이 초록으로 뛴다")

    # ---------- F5. 화면은 분을 짓지 않는다 ----------
    def test_f5_screen_never_computes_minutes(self):
        for name, body in (("stallState", self.state), ("stallHTML", self.stall)):
            self.assertNotIn("Date.now()", body,
                             f"{name} 가 스스로 시계를 본다 — 분은 서버 것이다")
            self.assertNotIn("60000", body, f"{name} 가 분을 계산한다")

    # ---------- F6. 진단 파라미터 ----------
    def test_f6_stall_param_faces(self):
        self.assertIn("?stall=", self.src, "진단 파라미터가 문서화되지 않았다")
        for face in ("stallkind", "stalldep", "stallhold"):
            self.assertIn(face, self.democ, f"{face} 얼굴이 없다")
        head = self.src[self.src.index("/* ?stall=<분>"):]
        self.assertIn("spawn_failed", head[:600],
                      "죽음 얼굴을 부르는 법이 적혀 있지 않다")

    def test_f6_param_is_inert_without_query(self):
        m = re.search(r"if \(!m[^\n]*\) return rows;", self.democ)
        self.assertTrue(m, "파라미터가 없을 때 행을 그대로 돌려주지 않는다")

    def test_f6_param_goes_through_the_real_screen(self):
        """그림을 따로 그리지 않는다 — 진짜 카탈로그 행에 얹어 진짜 함수를 지난다."""
        self.assertIn("stallProbe(fresh)", self.src, "stallProbe 를 부르는 자리가 없다")
        for banned in ("data-wake", "rvpt", "livedot"):
            self.assertNotIn(banned, self.democ,
                             "진단용이 화면을 따로 그린다 — 보고 고친 것이 "
                             "화면이 아니게 된다")

    def test_f6_the_handle_can_be_pressed_headlessly(self):
        """?stallpress=<id> 가 **진짜 wakeDoc 을 부른다** — 창을 지어 세우지 않는다.

        거절 창(사용자가 "붉게 뜨면 반려"라고 판정해야 하는 그 창)은 손이 있어야
        열린다. 두 번 올라간 이 기능의 그 창을 아무도 눈으로 본 적이 없었다.
        """
        m = re.search(r"function stallPressProbe\(\)\{[\s\S]*?\n\}", self.src)
        self.assertTrue(m, "손잡이를 눌러 보는 자리가 없다")
        self.assertIn("wakeDoc(", m.group(0),
                      "진짜 누르는 함수를 안 부른다 — 그림을 세우면 고친 것이 "
                      "화면이 아니게 된다")
        self.assertNotIn("s9dlg", m.group(0), "진단이 창을 따로 짓는다")

    # ---------- F8. 열 머리와 정렬도 같은 술어 ----------
    def test_f8_column_count_uses_predicate(self):
        self.assertIn("stallState(", self.col,
                      "열 머리의 '멈춤 N' 이 다른 술어를 쓴다")
        self.assertNotIn("stalled_mins", self.col)

    def test_f8_sort_uses_predicate(self):
        seg = self.board[self.board.index("in-progress"):]
        self.assertIn("stallState(", seg,
                      "in-progress 정렬이 다른 술어를 쓴다")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- 실제로 돌린다

STUBS = """
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const shortId = s => String(s).slice(0, 17);
const SCOLOR = {}, SYS_TAGS = new Set(), PICKED_MARK = "*";
const expanded = new Set();
const tagHue = () => 0, prioHTML = () => "", fmtElapsed = () => "0s";
const fmtWhen = iso => "오늘 16:45";
const rvClamped = (cap, tx) => `<div class="rvpt">${cap}</div>`;
// 작업 자리 칩(REQ-20260829-030)은 이 시험의 관심사가 아니다 — prioHTML 과 같이
// 비워 둔다. 자리 표시의 계약은 tests/test_workspace_chip.py 가 따로 붙잡는다.
const wsChip = () => "";
const rvLabel = s => s;
const DEP_DEAD = new Set(["done", "cancelled"]);
let CAT = [];
const catFind = id => CAT.find(r => r.id === id) || null;
function liveBlockers(r){
  if (!r || DEP_DEAD.has(r.status)) return [];
  return (r.blocked_by || []).map(catFind).filter(b => b && !DEP_DEAD.has(b.status));
}
"""


@unittest.skipUnless(NODE, "node 없음 — 실행 검증 생략")
class StallRendersTheSame(unittest.TestCase):
    """정적 검사는 '조건이 한 곳인가'를 보고, 여기서는 **그려서** 확인한다."""

    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    def render(self, rows):
        g = lambda n: _grab(self.src, n)
        script = "\n".join([
            STUBS,
            g("fmtStall"), g("fmtLast"),
            "const wokeAt = new Map(); const WOKE_HOLD = 180000;",
            g("wokePending"), g("stallState"), g("stallHTML"), g("cardHTML"),
            "CAT = %s;" % json.dumps(rows),
            # 문서 화면이 짓는 자리와 **같은 표현식**
            "const out = CAT.map(r => ({id: r.id, card: cardHTML(r),"
            "  doc: stallHTML(catFind(r.id))}));",
            "console.log(JSON.stringify(out));",
        ])
        p = subprocess.run([NODE, "-e", script], capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0, "node 실행 실패:\n" + p.stderr[-2000:])
        return {o["id"]: o for o in json.loads(p.stdout.strip().splitlines()[-1])}

    ROWS = [
        # 멈춘 것 — 손잡이가 서야 한다
        {"id": "REQ-A", "type": "request", "status": "in-progress",
         "title": "멈춘 것", "user": "u", "stalled_mins": 45,
         "updated": "2026-08-29T16:45:00+09:00"},
        # 멈췄고 **선행 대기도 있는** 것 — 2차 반려가 뒤집은 자리
        {"id": "REQ-B", "type": "request", "status": "in-progress",
         "title": "멈췄고 선행도 있다", "user": "u", "stalled_mins": 30,
         "blocked_by": ["REQ-D"], "updated": "2026-08-29T16:45:00+09:00"},
        # 죽음이 기록된 것 — 채운 사각
        {"id": "REQ-C", "type": "request", "status": "in-progress",
         "title": "죽었다", "user": "u", "stalled_mins": 12,
         "live_kind": "spawn_failed", "live_reason": "프로세스 종료",
         "updated": "2026-08-29T16:45:00+09:00"},
        # 안 멈춘 것 — 손잡이도 점도 없어야 한다
        {"id": "REQ-D", "type": "request", "status": "open",
         "title": "선행", "user": "u"},
        # 도는 중 — 초록
        {"id": "REQ-E", "type": "request", "status": "in-progress",
         "title": "돈다", "user": "u", "live": True, "live_age": 3},
    ]

    def test_card_and_document_render_the_same_stall_block(self):
        out = self.render(self.ROWS)
        for r in self.ROWS:
            o = out[r["id"]]
            if o["doc"]:
                self.assertIn(o["doc"], o["card"],
                              "%s: 카드와 문서의 멈춤 덩어리가 다르다" % r["id"])
            else:
                self.assertNotIn("data-wake=", o["card"],
                                 "%s: 문서엔 없는 손잡이가 카드엔 있다" % r["id"])

    def test_a_blocked_row_keeps_its_handle(self):
        out = self.render(self.ROWS)
        b = out["REQ-B"]["card"]
        self.assertIn("선행 대기", b, "선행 대기 줄이 사라졌다")
        self.assertIn("data-wake=", b, "선행 대기가 손잡이를 먹었다")
        self.assertIn("30분째 진전 없음", b)

    def test_the_dot_and_the_handle_stand_or_fall_together(self):
        out = self.render(self.ROWS)
        for rid, o in out.items():
            card = o["card"]
            handle = "data-wake=" in card
            stopped = "dot-stopped" in card
            self.assertEqual(handle, stopped,
                             "%s: 점과 손잡이가 어긋난다 (손잡이=%s 정지마크=%s)"
                             % (rid, handle, stopped))
        self.assertIn("dot-stopped mild", out["REQ-A"]["card"])
        self.assertIn('livedot dot-stopped" title="처리 주체가 멈췄다',
                      out["REQ-C"]["card"])
        self.assertIn("livedot on", out["REQ-E"]["card"])

    def test_a_quiet_row_says_nothing(self):
        out = self.render(self.ROWS)
        for rid in ("REQ-D", "REQ-E"):
            self.assertNotIn("멈춤", out[rid]["card"], "%s 가 멈췄다고 말한다" % rid)
            self.assertEqual("", out[rid]["doc"])
