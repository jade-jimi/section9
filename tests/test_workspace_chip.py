"""화면이 **작업 자리**를 사람에게 말한다 (REQ-20260829-030-62x6).

무인 작업자는 워크트리(격리된 사본)에 앉는 것이 기본이지만, 아직 커밋되지 않은
코드가 있으면 그 사본이 낡은 자리가 되므로 본 저장소에 앉는다(REQ-20260829-028).
**말없이 다르게 동작하면 다음 사람이 또 헤맨다** — 워크트리에서 고친 화면은 지금
도는 서버에 영영 안 나타나므로, 무엇을 어디서 확인할지가 자리에 달려 있다.

이 시험이 붙잡는 계약 넷:

① **없는 것은 그리지 않는다.** 서버는 그 문서에 새 코드로 스폰이 한 번 일어난
   뒤부터만 `workspace` 를 싣는다. 키가 없을 때 빈 칸이나 "미상"을 그리면, 모르는
   것이 판에서 매일 자리를 먹는다 — 같은 잘못을 취소 열에서 한 번 고쳤다
   (REQ-20260829-031).
② **화면은 판정하지 않는다.** 어느 사유가 어느 자리로 가는지는 서버의
   `workspace_decision` 하나가 안다. 화면이 사유에서 자리를 유추하기 시작하면 같은
   판정이 두 벌이 되고, 그때부터 한 벌만 고쳐진다(이 저장소가 판정 버튼·멈춤
   술어에서 세 번 밟은 실패다).
③ **줄이 아니라 칩이다.** "줄은 사람의 손을 요구하는 사실에만 준다"
   (REQ-20260827-017). 자리는 읽고 나서 대개 할 일이 없는 사실이라 카드 메타 줄의
   칩이고, 할 일이 있는 경우(미커밋 코드)는 카드마다 되풀이하지 않고 헤더 칩
   하나가 말한다.
④ **깨우기 창은 `ok` 와 `message` 둘만 읽는다.** 서버에 `action` 값이 하나
   늘어도(028 이 더한 `waiting`) 화면은 그대로여야 한다. 그리고 `ok=false` 는
   오류가 아니라 설명이라 붉히지 않는다 — 대기는 고장이 아니라 차례다.

계약을 정규식으로 "그렇게 생겼다"만 보지 않고, 함수를 그대로 떼어 node 로
**실행**한다 (test_board_done_window 와 같은 방식). node 가 없으면 실행 검증만
건너뛰고 소스 계약은 그대로 본다.

실행: python3 tests/ workspace_chip
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
S9 = os.path.join(HERE, "..", "bin", "s9")


def find_node():
    n = shutil.which("node") or shutil.which("nodejs")
    if n:
        return n
    for pat in ("/home/*/.vscode-server/bin/*/node",
                "/root/.vscode-server/bin/*/node"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


NODE = find_node()


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def grab(src, pattern, what):
    m = re.search(pattern, src, re.S | re.M)
    assert m, f"{what} 를 못 찾았다 — 이름이 바뀌었으면 이 시험도 따라가야 한다"
    return m.group(0)


class WorkspaceChip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = read(INDEX)
        cls.place = grab(cls.src, r"const WS_PLACE = \{[^\n]*\};", "WS_PLACE")
        cls.mark = grab(cls.src, r"const WS_MARK = [^\n]*;", "WS_MARK")
        cls.fix = grab(cls.src, r"const WS_FIX_COMMIT = [^\n]*;\n"
                                r"const WS_FIX_SWEEP = [^\n]*;", "WS_FIX_*")
        cls.means = grab(cls.src, r"const WS_MEANS = \{.*?\};", "WS_MEANS")
        cls.why = grab(cls.src, r"const WS_WHY = \{.*?\n\};", "WS_WHY")
        cls.state = grab(cls.src, r"^function wsState\(r\)\{.*?^\}", "wsState")
        cls.title = grab(cls.src, r"^function wsTitle\(s\)\{.*?^\}", "wsTitle")
        cls.chip = grab(cls.src, r"^function wsChip\(r\)\{.*?^\}", "wsChip")
        cls.open = grab(cls.src, r"^function wsOpen\(id\)\{.*?^\}", "wsOpen")
        cls.note = grab(cls.src, r"^function wsBoardNote\(\)\{.*?^\}", "wsBoardNote")
        cls.card = grab(cls.src, r"^function cardHTML\(r\)\{.*?^\}", "cardHTML")
        cls.wake = grab(cls.src, r"^async function wakeDoc\(id\)\{.*?^\}", "wakeDoc")
        cls.wakedlg = grab(cls.src, r"^function wakeDlg\(id, d\)\{.*?^\}", "wakeDlg")

    # ---------- node 로 실제 실행 ----------

    def run_js(self, body, rows=None):
        if not NODE:
            self.skipTest("node 없음 — 실행 검증 생략 (소스 계약은 별도 검사)")
        script = "\n".join([
            # 화면의 도우미는 이 시험의 관심사가 아니다 — 글자 그대로 통과시킨다
            "const esc = s => String(s == null ? '' : s);",
            "const shortId = s => String(s).slice(0, 16);",
            "let dlgSeen = null;",
            "const s9dlg = o => { dlgSeen = o; return null; };",
            "let catalog = %s;" % json.dumps(rows or []),
            "const catFind = id => catalog.find(r => r.id === id) || null;",
            self.place, self.mark, self.fix, self.means, self.why,
            self.state, self.title, self.chip, self.open, self.note,
            body,
        ])
        p = subprocess.run([NODE, "-e", script], capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(p.returncode, 0, f"node 실행 실패:\n{p.stderr[-2000:]}")
        return json.loads(p.stdout.strip().splitlines()[-1])

    def row(self, **kw):
        r = {"id": "REQ-20260829-030-62x6", "type": "request",
             "status": "in-progress"}
        r.update(kw)
        return r

    # W1 — 계약의 핵심: 값이 없으면 아무것도 그리지 않는다
    def test_w1_no_marker_no_mark(self):
        """서버가 키를 안 실었을 때 빈 칸도, "미상"도 그리지 않는다.

        지금 이 저장소의 in-progress 아홉 건이 전부 그 상태다 — 새 코드로 스폰이
        아직 없어 `workspace` 가 없다. 여기서 자리표시자를 그리면 판이 매일 아홉
        번 "모른다"고 말한다."""
        r = self.run_js("console.log(JSON.stringify({"
                        " none: wsChip({id:'X',type:'request',status:'in-progress'}),"
                        " empty: wsChip({id:'X',type:'request',status:'in-progress',workspace:{}}),"
                        " bogus: wsChip({id:'X',type:'request',status:'in-progress',"
                        "   workspace:{kind:'somewhere',reason:'fresh'}})}));")
        self.assertEqual(r["none"], "", "값이 없는데 표시를 그렸다")
        self.assertEqual(r["empty"], "", "빈 객체에 표시를 그렸다")
        self.assertEqual(r["bogus"], "", "모르는 자리 이름에 표시를 그렸다")

    # W2 — 도는 요청의 사실이다: 끝난 카드가 "여기서 돈다"고 말하면 안 된다
    def test_w2_only_while_it_runs(self):
        ws = {"kind": "main", "reason": "dirty-spine", "wt": "", "at": ""}
        r = self.run_js("console.log(JSON.stringify({"
                        " prog: wsChip(%s), done: wsChip(%s), know: wsChip(%s)}));" % (
                            json.dumps(self.row(workspace=ws)),
                            json.dumps(self.row(status="done", workspace=ws)),
                            json.dumps(self.row(type="knowledge", workspace=ws))))
        self.assertIn("본 저장소", r["prog"])
        self.assertEqual(r["done"], "", "끝난 카드가 아직 어디서 돈다고 말한다")
        self.assertEqual(r["know"], "", "요청이 아닌 문서에까지 자리를 그렸다")

    # W3 — 자리는 **낱말**로 갈린다 (색이 유일한 단서가 아니다)
    def test_w3_the_two_places_are_words(self):
        r = self.run_js("console.log(JSON.stringify({"
                        " main: wsChip(%s), wt: wsChip(%s)}));" % (
                            json.dumps(self.row(workspace={
                                "kind": "main", "reason": "self-edit"})),
                            json.dumps(self.row(workspace={
                                "kind": "worktree", "reason": "fresh",
                                "wt": "w-829-030-62x6"}))))
        self.assertIn("본 저장소", r["main"])
        self.assertIn("워크트리", r["wt"])
        # 낱말이 다르므로 색이 없어도 읽힌다 (s9-design 7: 색만으로 구분 금지)
        self.assertNotIn("본 저장소", r["wt"])

    # W4 — 사유는 사람 말로, 풀리는 법은 풀 수 있을 때만
    def test_w4_reason_and_remedy(self):
        r = self.run_js("console.log(JSON.stringify({"
                        " dirty: wsTitle(wsState(%s)), pile: wsTitle(wsState(%s)),"
                        " self: wsTitle(wsState(%s)), wt: wsTitle(wsState(%s))}));" % (
                            json.dumps(self.row(workspace={
                                "kind": "main", "reason": "dirty-overlap"})),
                            json.dumps(self.row(workspace={
                                "kind": "main", "reason": "worktree-pile"})),
                            json.dumps(self.row(workspace={
                                "kind": "main", "reason": "self-edit"})),
                            json.dumps(self.row(workspace={
                                "kind": "worktree", "reason": "fresh",
                                "wt": "w-829-030-62x6"}))))
        self.assertIn("커밋하면", r["dirty"], "커밋하면 풀린다는 말이 없다")
        self.assertIn("거두면", r["pile"], "워크트리를 거두면 풀린다는 말이 없다")
        # 풀 것이 없는 자리에 할 일을 지어내지 않는다 — 매번 참인 문장은 안 읽힌다
        self.assertNotIn("커밋하면", r["self"])
        self.assertNotIn("커밋하면", r["wt"])
        # 워크트리는 어느 워크트리인지까지 말한다 (cd 해서 볼 자리다)
        self.assertIn("w-829-030-62x6", r["wt"])

    # W5 — 서버가 내는 사유 코드에 빠짐이 없다
    def test_w5_every_server_reason_has_words(self):
        """서버(`workspace_decision`)가 낼 수 있는 사유를 화면이 다 안다.

        모르는 코드가 오면 자리 낱말만 그리고 문장은 비운다(그게 W6 다) — 그래도
        **오늘 존재하는 코드**에 빈 자리를 남기면 카드가 이유를 못 말한다."""
        s9 = read(S9)
        codes = set(re.findall(r'(?:^|\s)[MW]\("([a-z-]+)"', s9, re.M))
        self.assertGreaterEqual(len(codes), 10,
                                "서버에서 사유 코드를 못 읽었다 — 판정 함수가 바뀌었나")
        for c in sorted(codes):
            self.assertIn(f'"{c}"', self.why, f"사유 {c!r} 를 화면이 모른다")

    # W6 — 모르는 코드가 와도 화면이 무너지지 않는다
    def test_w6_unknown_reason_still_names_the_place(self):
        r = self.run_js("console.log(JSON.stringify(wsState(%s)));" % json.dumps(
            self.row(workspace={"kind": "main", "reason": "무언가-새-사유"})))
        self.assertEqual(r["place"], "본 저장소")
        self.assertEqual(r["why"], "", "모르는 사유에 말을 지어냈다")
        self.assertEqual(r["fix"], "")

    # W7 — **화면은 판정하지 않는다**
    def test_w7_the_screen_never_decides_the_place(self):
        """자리는 서버가 준 `kind` 그대로다. 사유에서 자리를 유추하는 순간
        `workspace_decision` 과 두 벌이 되고, 그때부터 한 벌만 고쳐진다."""
        for fn, name in ((self.state, "wsState"), (self.chip, "wsChip"),
                         (self.title, "wsTitle"), (self.open, "wsOpen")):
            self.assertNotIn("dirty", fn, f"{name} 이 사유를 손으로 갈랐다")
            self.assertNotIn("worktree-pile", fn, f"{name} 이 사유를 손으로 갈랐다")
        self.assertIn("w.kind", self.state, "서버가 준 kind 를 안 읽는다")

    # W8 — 저장소 하나의 사실은 카드마다 되풀이하지 않는다
    def test_w8_the_repo_fact_is_told_once(self):
        rows = [self.row(id="REQ-A", workspace={"kind": "main", "reason": "dirty-spine"}),
                self.row(id="REQ-B", workspace={"kind": "main", "reason": "dirty-overlap"}),
                self.row(id="REQ-C", workspace={"kind": "main", "reason": "dirty-unknown"}),
                self.row(id="REQ-D", workspace={"kind": "main", "reason": "worktree-pile"}),
                # 아래 둘은 세지 않는다 — 사람이 할 일이 없다
                self.row(id="REQ-E", workspace={"kind": "main", "reason": "self-edit"}),
                self.row(id="REQ-F", workspace={"kind": "worktree", "reason": "fresh"})]
        r = self.run_js(
            "const it = wsBoardNote(); it.act();"
            "console.log(JSON.stringify({label: it.label, tone: it.tone,"
            " title: it.title, body: dlgSeen.descHtml, cap: dlgSeen.cap,"
            " stop: dlgSeen.stop}));", rows=rows)
        self.assertIn("4", r["label"], "손이 드는 건수만 세지 않았다")
        # 경고가 아니다 — 옆의 진짜 경고와 층위가 같아지면 둘 다 안 읽힌다
        self.assertNotIn("sv-bad", r["tone"])
        self.assertNotIn("sv-warn", r["tone"])
        self.assertIs(r["stop"], False, "고장 창의 붉은 눈썹을 달았다")
        # 푸는 법은 사유마다가 아니라 **한 번만** 적힌다: 미커밋 사유 셋에 답은 하나다
        self.assertEqual(r["body"].count("커밋하면"), 1,
                         "같은 답을 여러 번 적었다 — 여러 번 적힌 문장은 안 읽힌다")
        self.assertEqual(r["body"].count("거두면"), 1)

    def test_w8b_quiet_when_nothing_needs_hands(self):
        """할 일이 없으면 헤더는 아무 말도 하지 않는다 — 상시 자리표시자는 곧
        배경이 되어 진짜 사고 때도 안 읽힌다(이 칩이 세운 규칙)."""
        rows = [self.row(id="REQ-A", workspace={"kind": "worktree", "reason": "fresh"}),
                self.row(id="REQ-B", workspace={"kind": "main", "reason": "live-verify"})]
        r = self.run_js("console.log(JSON.stringify({n: wsBoardNote()}));", rows=rows)
        self.assertIsNone(r["n"], "풀 것이 없는데 헤더가 말을 걸었다")

    # ---------- 소스 계약 (node 유무와 무관) ----------

    # W9 — 카드와 문서 화면이 **같은 함수**를 부른다
    def test_w9_one_function_for_both_screens(self):
        """같은 사실이 두 화면에 각자 글자를 가지면 한쪽만 고쳐진다 —
        판정 단추가 그 이유로 세 번 반려됐다(REQ-20260828-007)."""
        self.assertIn("${wsChip(r)}", self.card, "카드가 자리를 안 말한다")
        self.assertIn("${wsChip(catFind(m.id))}", self.src,
                      "문서 화면이 자리를 안 말한다")
        # 낱말은 한 곳에만 있다
        self.assertEqual(self.src.count('"본 저장소"'), 1,
                         "자리 낱말이 두 곳에 적혀 있다")

    # W10 — 줄이 아니라 칩이다
    def test_w10_a_chip_not_a_row(self):
        """"줄은 사람의 손을 요구하는 사실에만 준다"(REQ-20260827-017).
        자리는 읽고 나서 할 일이 없는 사실이라 카드 메타 줄 안에 선다."""
        self.assertNotIn("rvpt", self.chip, "자리에 대기·멈춤과 같은 줄을 줬다")
        # 메타 줄(.m) 안에서 태그보다 앞, 즉 한 덩어리 안이다
        m = re.search(r'<div class="m">(.*?)</div>', self.card, re.S)
        self.assertTrue(m and "${wsChip(r)}" in m.group(1),
                        "자리 칩이 메타 줄 밖에 섰다 — 카드에 줄이 하나 늘었다")
        css = re.search(r"(?m)^\.wsat\{([^}]*)\}", self.src)
        self.assertTrue(css, ".wsat 규칙이 없다")
        for banned in ("background", "border"):
            self.assertNotIn(banned, css.group(1),
                             "칩에 색면·테두리를 줬다 — 이 화면의 배지는 글자다")

    # ---------- 2차 반려: "어떤 화면에서 확인하는지 설명을 봐도 모르겠다" ----------

    # W14 — 낱말 앞에 **표**가 선다
    def test_w14_the_chip_carries_a_mark(self):
        """1차는 낱말만 세웠다. 메타 줄은 이름·급·크기·태그가 이미 서는 자리라
        낱말 하나는 지나가는 태그로 읽혔고, 값이 붙은 카드가 실제로 보드에
        있었는데도 사람이 못 찾았다. 표는 헤더 칩과 **같은 글자**여야 한다 —
        표를 둘로 나누면 사람이 배울 것이 둘이 된다."""
        mark = re.search(r'"(.+?)"', self.mark).group(1)
        r = self.run_js(
            "console.log(JSON.stringify({ main: wsChip(%s), wt: wsChip(%s),"
            " note: wsBoardNote()}));" % (
                json.dumps(self.row(workspace={"kind": "main",
                                               "reason": "live-verify"})),
                json.dumps(self.row(workspace={"kind": "worktree",
                                               "reason": "fresh"}))),
            rows=[self.row(workspace={"kind": "main", "reason": "dirty-spine"})])
        self.assertIn(mark, r["main"], "카드의 자리에 표가 없다")
        self.assertIn(mark, r["wt"])
        self.assertEqual(r["note"]["mark"], mark,
                         "카드와 헤더의 표가 다르다 — 둘이 한 가지라는 것을 못 잇는다")
        # 표가 낱말을 밀어내지는 않는다 — 표만으로는 어느 자리인지 못 읽는다
        self.assertIn("본 저장소", r["main"])

    # W15 — 손 위의 글만으로는 못 찾은 사람에게 답이 안 된다: **누를 수 있다**
    def test_w15_the_chip_can_be_pressed(self):
        r = self.run_js("console.log(JSON.stringify(wsChip(%s)));" % json.dumps(
            self.row(id="REQ-20260829-030-62x6",
                     workspace={"kind": "main", "reason": "live-verify"})))
        self.assertIn('data-wsat="REQ-20260829-030-62x6"', r)
        # role/tabindex 가 있어야 이 화면의 Enter·Space 핸들러가 집는다
        self.assertIn('role="button"', r)
        self.assertIn('tabindex="0"', r)
        # 손 위의 글은 **그대로 둔다** — 빠른 쪽은 여전히 얹기만 하면 된다
        self.assertIn("title=", r)

    def test_w15b_the_press_beats_the_card(self):
        """카드 안의 손잡이는 카드가 아니다 (깨우기·세우기가 세운 규칙).
        칩이 카드보다 늦게 잡히면 누를 때마다 문서가 열려 창을 못 본다."""
        i_ws = self.src.index('closest("[data-wsat]")')
        i_doc = self.src.index('closest("[data-doc]")')
        self.assertLess(i_ws, i_doc, "카드가 칩보다 먼저 잡는다")
        seg = self.src[i_ws:i_doc]
        self.assertIn("stopPropagation", seg, "카드까지 이벤트가 올라간다")
        self.assertIn("wsOpen(", seg, "누르는 길이 창으로 안 간다")

    # W16 — 누르면 **그 카드 한 장**을 말한다
    def test_w16_the_press_opens_that_one_request(self):
        rows = [self.row(id="REQ-A", workspace={"kind": "main",
                                                "reason": "dirty-overlap"}),
                self.row(id="REQ-B", workspace={"kind": "worktree",
                                                "reason": "fresh",
                                                "wt": "w-829-030-62x6"})]
        r = self.run_js(
            "wsOpen('REQ-A'); const a = dlgSeen; wsOpen('REQ-B'); const b = dlgSeen;"
            "console.log(JSON.stringify({a, b}));", rows=rows)
        # 누른 것이 그 카드라 답도 그 카드다 — 옆 카드가 섞이면 무엇을 눌렀는지 흐려진다
        self.assertIn("REQ-A", r["a"]["title"])
        self.assertNotIn("REQ-B", r["a"]["title"] + r["a"]["descHtml"])
        # 사유와 푸는 법이 **창 안 문장**으로 있다 (귀띔에만 있으면 못 찾은 사람에게 답이 아니다)
        self.assertIn("커밋되지 않았다", r["a"]["descHtml"])
        self.assertIn("커밋하면", r["a"]["descHtml"])
        # 그래서 나에게 무슨 뜻인가 — 자리가 다르면 답도 달라야 한다
        self.assertIn("바로 나타납니다", r["a"]["descHtml"])
        self.assertIn("나타나지 않습니다", r["b"]["descHtml"])
        # 워크트리는 어느 워크트리인지까지 말한다 (사람이 cd 해서 볼 자리다)
        self.assertIn("w-829-030-62x6", r["b"]["title"])
        # 풀 것이 없는 자리에 할 일을 지어내지 않는다
        self.assertNotIn("커밋하면", r["b"]["descHtml"])
        # 대기·자리는 고장이 아니다 — 붉은 눈썹을 달지 않는다
        self.assertIs(r["a"]["stop"], False)

    def test_w17_nothing_to_show_opens_nothing(self):
        """값이 없으면 안 그린다는 계약은 **누른 뒤에도** 같다. 빈 창은 "모른다"를
        한 번 더 말하는 자리일 뿐이다."""
        r = self.run_js("wsOpen('REQ-A'); wsOpen('없는-문서');"
                        "console.log(JSON.stringify({dlg: dlgSeen}));",
                        rows=[self.row(id="REQ-A")])
        self.assertIsNone(r["dlg"], "그릴 것이 없는데 창을 열었다")

    # W11 — 깨우기 창은 `ok` 와 `message` 둘만 읽는다
    def test_w11_wake_reads_only_ok_and_message(self):
        """서버에 `action` 값이 하나 늘었다(`waiting`). 화면이 그 값을 알기
        시작하면 같은 말이 서버와 화면 두 벌이 된다."""
        both = self.wake + self.wakedlg
        self.assertNotIn("d.action", both, "화면이 action 을 읽기 시작했다")
        self.assertNotIn('"waiting"', both, "화면이 서버의 답 이름을 베껴 적었다")
        self.assertIn("d.message", self.wakedlg)
        self.assertIn("d.ok", self.wakedlg)

    def test_w12_a_refusal_is_not_a_failure(self):
        """`waiting`·`busy`·`capped`·`moving` 은 전부 정상적인 답이다 —
        붉은 실패 창으로 그리면 사람은 고장으로 읽는다. 대기는 차례다."""
        self.assertRegex(self.wakedlg, r"stop:\s*false")
        # 창을 짓는 자리도 하나다 — 진단(?dlg=wakewait)이 같은 함수를 부른다
        self.assertIn("wakeDlg(id, d)", self.wake)
        self.assertIn("wakeDlg(", grab(self.src, r"if \(m\[1\] === \"wakewait\".*?\n  \}",
                                       "?dlg=wakewait 진단"))

    # W13 — 진단은 **진짜 함수**를 부른다
    def test_w13_the_probe_draws_nothing_of_its_own(self):
        """그림을 따로 만들면 보고 고친 것이 화면이 아니게 된다. 진단이 하는
        일은 서버가 줬을 값을 행에 얹는 것뿐이다 (stallProbe 가 낸 선례)."""
        probe = grab(self.src, r"^function wsProbe\(rows\)\{.*?^\}", "wsProbe")
        self.assertIn("r.workspace = {", probe, "진단이 행에 값을 얹지 않는다")
        for banned in ("innerHTML", "wsChip", "<span"):
            self.assertNotIn(banned, probe, "진단이 화면을 따로 그렸다")
        self.assertIn("if (r.workspace) continue", probe,
                      "진단이 서버가 준 진짜 값을 덮어쓴다")
        self.assertIn("wsProbe(fresh)", self.src, "진단이 카탈로그 길에 안 걸려 있다")


if __name__ == "__main__":
    unittest.main()
