"""프로젝트 전용 탭의 계약 — G0′ (REQ-20260831-026-62x6).

두 번의 반려가 같은 자리를 가리켰다. ① "docs 탭 좌측에 프로젝트가 안 보인다"
② "프로젝트는 docs 보다 상위 개념인데 docs 와 같은 수준으로 docs 탭에 존재한다는
게 어불성설이다". PO·designer 가 재수렴해 확정한 것이 **전용 탭**이고, 이 파일이
지키는 것은 그 판정의 세 가지다:

  ① **문은 하나다** — 탭 하나가 문이고, 문서 종류 목록(TYPE_ORDER·「종류」 셀렉트·
     Docs 좌측 진입점)에서 project 가 사라진다. 문이 둘이면 사용자는 어느 쪽이
     맞는지 묻게 되고, 그 물음이 두 번째 반려의 내용이었다.
  ② **얼굴은 늘지 않는다** — 탭 우측은 새 관리 판이 아니라 **지금의 PRJ 문서
     판**이다(prjPanelHTML). 관리 판을 따로 지으면 같은 프로젝트가 두 얼굴을
     갖고, 그 다음부터는 한쪽만 고쳐진다(이 저장소가 이미 치른 값).
  ③ **렌즈와 집은 다른 것이다** — 헤더 「프로젝트」 필터(렌즈)는 이 목록을 좁히지
     않고, 목록에서 행을 고르는 일이 전역 필터를 바꾸지도 않는다. 지금 그 범위인
     행에 「◂ 보는 중」 표식만 선다.

계약은 둘로 나뉜다: 읽어서 아는 것(정적)과 띄워 봐야 아는 것(실브라우저 + 실서버).
탭 줄이 한 줄인지는 후자다 — designer 가 CDP 로 여덟 번째 탭을 끼워 넣고 실측한
"처방 없음" 판정을, 이제 진짜 여덟 개로 다시 잰다.

실행: python3 tests/ project_tab
"""
import json
import os
import re
import subprocess
import time
import unittest
import urllib.error
import urllib.request

from cdpreal import WS, chrome_path, reclaim
from portpool import free_port, wait_server

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web")
S9 = os.path.join(ROOT, "bin", "s9")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def strip_comments(src):
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"(?m)^\s*//.*$", "", src)


class TheTabStandsInItsPlace(unittest.TestCase):
    """탭은 여덟이고, 여덟째는 Terminal 다음·Settings 앞이다."""

    @classmethod
    def setUpClass(cls):
        cls.html = read(WEB, "index.html")
        cls.app = strip_comments(read(WEB, "app", "app.js"))

    def test_the_label_and_the_seat(self):
        """오른쪽 끝 Settings 는 근육 기억의 앵커라 움직이지 않는다 — 관리 층
        둘(Projects·Settings)이 오른쪽에 붙어 문서 뷰 다섯과 무리를 이룬다."""
        seats = re.findall(r'data-tab="([a-z]+)"', self.html)
        self.assertEqual(
            seats,
            ["board", "docs", "graph", "audit", "stream", "terminal",
             "projects", "settings"],
            "탭 자리가 확정 순서가 아니다 (Terminal 다음 · Settings 앞)")
        self.assertRegex(self.html, r'data-tab="projects"[^>]*>Projects<',
                         "탭 라벨이 `Projects` 가 아니다")

    def test_the_router_knows_the_same_eight(self):
        """껍데기와 라우터가 다른 목록을 들면 주소로 들어온 사람만 다른 화면을
        본다 — `#projects` 가 Board 로 튕긴다."""
        m = re.search(r'const TABS = \[([^\]]+)\]', self.app)
        self.assertTrue(m, "TABS 배열을 못 읽었다")
        tabs = re.findall(r'"([a-z]+)"', m.group(1))
        self.assertEqual(
            tabs,
            ["board", "docs", "graph", "audit", "stream", "terminal",
             "projects", "settings"],
            "라우터의 탭 목록이 껍데기와 다르다")

    def test_the_address_carries_the_chosen_project(self):
        """고른 프로젝트가 주소에 실려야 새로고침·뒤로가기가 같은 화면을 낸다."""
        self.assertRegex(self.app,
                         r'tab === "projects" && selectedDoc',
                         "주소가 고른 프로젝트를 안 싣는다(pushRoute)")
        self.assertRegex(self.app,
                         r't === "projects" && parts\[1\]',
                         "주소에서 고른 프로젝트를 안 읽는다(applyRoute)")

    def test_the_pane_is_drawn_by_the_project_renderer(self):
        self.assertRegex(self.app, r'tab === "projects"\)\{\s*renderProjects\(\)',
                         "render() 가 이 탭을 그리지 않는다")


class TheDoorIsOnlyOne(unittest.TestCase):
    """문서 종류 목록에서 project 가 사라진다 — 근원 제거."""

    @classmethod
    def setUpClass(cls):
        cls.html = read(WEB, "index.html")
        cls.const = read(WEB, "app", "const.js")
        cls.docs = strip_comments(read(WEB, "app", "docs.js"))

    def test_the_type_list_has_no_project(self):
        m = re.search(r"const TYPE_ORDER = \[([^\]]+)\]", self.const)
        self.assertTrue(m)
        self.assertNotIn("project", re.findall(r'"([a-z]+)"', m.group(1)),
                         "문서 종류 목록(타입바)에 project 가 남아 있다")

    def test_the_kind_select_has_no_project(self):
        sel = re.search(r'<select id="f-type">[\s\S]*?</select>', self.html)
        self.assertTrue(sel, "「종류」 셀렉트를 못 읽었다")
        opts = re.findall(r"<option[^>]*>([^<]*)</option>", sel.group(0))
        self.assertNotIn("project", opts,
                         "「종류」 셀렉트에 project 옵션이 남아 있다: %r" % opts)

    def test_docs_no_longer_keeps_a_project_door(self):
        """Docs 좌측의 PROJECT 진입점·목록·만들기 손잡이가 사라진다 —
        문이 둘이면 어느 쪽이 맞는지 묻게 된다(2차 반려의 내용)."""
        self.assertNotIn('curType === "project"', self.docs,
                         "Docs 에 project 분기가 남아 있다")
        for fn in ("prjListHTML(", "prjRowHTML("):
            self.assertNotIn(fn, self.docs,
                             "Docs 가 아직 프로젝트 목록을 그린다: %s" % fn)

    def test_the_document_list_shows_only_declared_kinds(self):
        """선언한 종류만 무리를 갖는다 — 모르는 종류를 목록 끝에 동적으로
        붙이던 자리가 1차 반려의 원인이었다(SESSION 142건 뒤 맨 바닥)."""
        m = re.search(r"const groups = \{([^}]*)\}", self.docs)
        self.assertTrue(m, "groups 초기 객체를 못 읽었다")
        self.assertNotIn("project", m.group(1))
        self.assertNotRegex(
            self.docs, r"groups\[r\.type\] \|\| \(groups\[r\.type\]\s*=",
            "모르는 종류가 목록 끝에 동적으로 붙는다 — 그 자리가 1차 반려다")

    def test_the_project_document_is_still_a_document(self):
        """정본 지위는 불변이다 — 문서 판(prjPanelHTML)은 그대로 문서 뷰가 그린다."""
        self.assertIn("prjPanelHTML(", self.docs,
                      "PRJ 문서 뷰에서 프로젝트 판이 사라졌다")


class TheFaceIsNotDoubled(unittest.TestCase):
    """탭 우측은 새 관리 판이 아니라 **지금의 문서 판**이다."""

    @classmethod
    def setUpClass(cls):
        cls.js = strip_comments(read(WEB, "app", "project.js"))
        body = re.search(r"function renderProjects\(\)\{[\s\S]*?\n\}", cls.js)
        assert body, "renderProjects 가 없다"
        cls.body = body.group(0)

    def test_the_left_is_the_list_we_already_built(self):
        self.assertIn("prjListHTML(", self.body,
                      "좌측이 이미 지은 목록을 안 쓴다")

    def test_the_right_is_the_document_pane(self):
        """관리 판을 새로 지으면 얼굴이 셋이 된다 — 우측은 loadDoc 이 그린다."""
        self.assertIn("loadDoc(", self.body,
                      "우측이 문서 판을 부르지 않는다 — 별도 관리 판을 지었다")
        self.assertNotIn("prjPanelHTML(", self.body,
                         "탭이 문서 판을 제 손으로 다시 그린다 — 관문이 둘이 된다")
        self.assertIn('id="viewer"', self.body,
                      "문서 판이 설 자리(#viewer)가 없다")

    def test_the_pane_says_whose_it_is(self):
        """판마다 주인을 밝힌다 — Docs 와 이 탭이 같은 셸 모양을 쓰므로, 주인을
        안 밝히면 탭을 옮겨도 남의 목록만 갈아 끼우고 판은 그대로 남는다."""
        self.assertIn('data-pane="projects"', self.body)
        docs = strip_comments(read(WEB, "app", "docs.js"))
        self.assertIn('data-pane="docs"', docs)
        self.assertNotIn('$("#view .docs .doclist")', docs,
                         "Docs 가 남의 판을 제 것으로 착각할 수 있다")

    def test_choosing_a_row_does_not_move_the_global_filter(self):
        """렌즈와 집은 다른 것이다 — 목록에서 고르는 일이 전역 범위를 바꾸면
        Board 로 돌아갔을 때 보던 것이 사라진다(PO 판정 ④의 금지)."""
        self.assertNotRegex(self.body, r'#f-project"\)\.value\s*=',
                            "행 선택이 전역 필터를 바꾼다")

    def test_the_header_filter_does_not_narrow_this_list(self):
        """그릇을 고르는 자리에서 그릇 필터가 걸리면 한 줄만 남는다."""
        self.assertNotIn("filtered(", self.body,
                         "탭 목록이 전역 필터를 그대로 먹는다")
        self.assertIn("viewing", self.body,
                      "지금 보는 범위를 표식으로 말하지 않는다")

    def test_the_background_refresh_does_not_wipe_a_hand(self):
        """15초 폴이 적고 있는 판을 갈아 끼우지 않는다 — Docs 가 배운 그 가드."""
        self.assertIn("prjEditing(", self.body,
                      "배경 갱신에 편집 가드가 없다")
        self.assertIn("docFresh", self.body,
                      "사람이 방금 고른 때와 배경 갱신을 안 가른다")


class TheMarkerIsInTheTable(unittest.TestCase):
    """「◂ 보는 중」도 화면 글자다 — PRJ_TEXT 한 곳에서 나온다."""

    def test_the_marker_lives_in_the_word_table(self):
        js = read(WEB, "app", "project.js")
        m = re.search(r"const PRJ_TEXT = \{([\s\S]*?)\n\};", js)
        self.assertTrue(m)
        self.assertIn("보는 중", m.group(1),
                      "표식 문안이 문구 표 밖에 있다")


# ─── 띄워 봐야 아는 것 — 실서버 + 실브라우저 ──────────────────────────────

TABLINE = r"""
(() => {
  const tabs = [...document.querySelectorAll("header .tabs [data-tab]")];
  const tops = tabs.map(b => Math.round(b.getBoundingClientRect().top));
  const hdr = document.querySelector("header");
  return {n: tabs.length, rows: [...new Set(tops)].length,
          right: Math.round(tabs[tabs.length - 1].getBoundingClientRect().right),
          headerH: Math.round(hdr.getBoundingClientRect().height)};
})()
"""

OPEN_TAB = r"""
(() => {
  document.querySelector('header [data-tab="projects"]').click();
  return new Promise(r => setTimeout(() => {
    const pane = document.querySelector('#view .docs[data-pane="projects"]');
    const rows = [...document.querySelectorAll("#view .doclist .pjrow")];
    r({pane: !!pane,
       list: !!(pane && pane.querySelector(".doclist .pjlist")),
       viewer: !!(pane && pane.querySelector("#viewer")),
       create: !!document.querySelector("#view [data-prjnew]"),
       rows: rows.length,
       ids: rows.map(x => x.dataset.doc),
       empty: (document.querySelector("#viewer .empty") || {}).textContent || ""});
  }, 700));
})()
"""

OPEN_ROW = r"""
(() => {
  const row = document.querySelector("#view .doclist .pjrow");
  row.click();
  return new Promise(r => setTimeout(() => {
    const v = document.querySelector("#viewer");
    r({tab: (document.querySelector("header [data-tab].active") || {}).dataset
             ? document.querySelector("header [data-tab].active").dataset.tab : "",
       panel: !!v.querySelector(".pjpanel"),
       members: !!v.querySelector(".pmem"),
       history: /History/.test(v.textContent),
       hash: location.hash});
  }, 1400));
})()
"""

VIEWING = r"""
(() => {
  const el = document.querySelector("#f-project");
  const before = [...document.querySelectorAll("#view .doclist .pjrow")].length;
  el.value = %s;
  el.dispatchEvent(new Event("input", {bubbles: true}));
  return new Promise(r => setTimeout(() => {
    const rows = [...document.querySelectorAll("#view .doclist .pjrow")];
    const marked = rows.filter(x => x.querySelector(".pjnow"));
    r({before, after: rows.length,
       marked: marked.length,
       markedId: marked.length ? marked[0].dataset.doc : "",
       text: marked.length ? marked[0].querySelector(".pjnow").textContent : ""});
  }, 500));
})()
"""


class TheTabLineHoldsAndOpens(unittest.TestCase):
    """여덟 번째 탭이 줄을 밀지 않고, 눌러서 목록·문서 판이 선다."""

    out = None
    srv = None
    proc = None
    ws = None

    @classmethod
    def setUpClass(cls):
        chrome = chrome_path()
        if chrome is None:
            raise unittest.SkipTest("실브라우저 미검증 — Chrome/Edge 를 찾지 못했다")
        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env={**os.environ, "S9_ROOT": ROOT, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.marker = "s9prjtab-%d" % os.getpid()
        cls.win = chrome.startswith("/mnt/")
        cls.prof_wsl = (("/mnt/c/Temp/" + cls.marker) if cls.win
                        else "/tmp/" + cls.marker)
        prof_arg = ("C:\\Temp\\" + cls.marker) if cls.win else cls.prof_wsl
        if cls.win:
            os.makedirs("/mnt/c/Temp", exist_ok=True)
        try:
            wait_server(cls.port)
            cls.proc = subprocess.Popen(
                [chrome, "--headless=new", "--disable-gpu",
                 "--user-data-dir=" + prof_arg, "--no-first-run",
                 "--no-default-browser-check", "--disable-extensions",
                 "--disable-background-networking", "--remote-debugging-port=0",
                 "--window-size=1440,900",
                 "http://127.0.0.1:%d/" % cls.port],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            dev = os.path.join(cls.prof_wsl, "DevToolsActivePort")
            cdp = None
            for _ in range(160):
                if os.path.exists(dev):
                    try:
                        with open(dev, encoding="utf-8") as f:
                            cdp = int(f.read().splitlines()[0])
                        break
                    except (ValueError, IndexError, OSError):
                        pass
                time.sleep(0.25)
            if cdp is None:
                raise ConnectionError("DevToolsActivePort 미출현")
            pages = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:%d/json/list" % cdp, timeout=10).read())
            page = next(p for p in pages if p.get("type") == "page")
            cls.ws = WS(page["webSocketDebuggerUrl"])
            for _ in range(200):
                if cls.ws.eval("!!(window.__S9_APP_READY && "
                               "document.querySelector('#view .col,#view .docs'))"):
                    break
                time.sleep(0.25)
            else:
                raise ConnectionError("대시보드가 판을 세우지 못했다")
            cls.out = {}
            for w in (1440, 1280, 900):
                cls.ws.call("Emulation.setDeviceMetricsOverride", width=w,
                            height=900, deviceScaleFactor=1, mobile=False)
                time.sleep(0.2)
                cls.out["w%d" % w] = cls.ws.eval(TABLINE)
            cls.ws.call("Emulation.setDeviceMetricsOverride", width=1440,
                        height=900, deviceScaleFactor=1, mobile=False)
            cls.out["open"] = cls.await_(OPEN_TAB)
            cls.out["viewing"] = cls.await_(VIEWING % json.dumps("section9"))
            cls.out["row"] = cls.await_(OPEN_ROW)
            for k, v in cls.out.items():
                if v is None:
                    raise ConnectionError("%s 를 재지 못했다" % k)
        except (ConnectionError, StopIteration, OSError, RuntimeError,
                urllib.error.URLError) as e:
            cls.tearDownClass()
            raise unittest.SkipTest("실브라우저 미검증 — %r" % e)

    @classmethod
    def await_(cls, expr):
        r = cls.ws.call("Runtime.evaluate", expression=expr,
                        returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    @classmethod
    def tearDownClass(cls):
        if cls.ws is not None:
            try:
                cls.ws.close()
            except OSError:
                pass
            cls.ws = None
        if cls.proc is not None:
            try:
                cls.proc.terminate()
            except OSError:
                pass
            cls.proc = None
        reclaim(cls.marker, cls.win)
        if cls.srv is not None:
            cls.srv.terminate()
            try:
                cls.srv.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.srv.kill()
            cls.srv = None
        import shutil
        shutil.rmtree(cls.prof_wsl, ignore_errors=True)

    def test_eight_tabs_stay_on_one_line(self):
        """designer 실측(여덟 번째 탭을 DOM 에 끼워 재기)의 재현 — 이제 진짜
        여덟 개다. 700px 까지 한 줄이라던 그 판정을 900·1440 에서 못박는다."""
        for w in (1440, 1280, 900):
            d = self.out["w%d" % w]
            self.assertEqual(d["n"], 8, "%dpx: 탭이 여덟이 아니다" % w)
            self.assertEqual(d["rows"], 1,
                             "%dpx: 탭 줄이 %d 줄로 접혔다" % (w, d["rows"]))
            self.assertLess(d["right"], w,
                            "%dpx: 마지막 탭이 화면 밖으로 나갔다" % w)

    def test_the_tab_opens_the_two_pane_shell(self):
        d = self.out["open"]
        self.assertTrue(d["pane"], "탭을 눌러도 판이 안 선다")
        self.assertTrue(d["list"], "좌측에 프로젝트 목록이 없다")
        self.assertTrue(d["viewer"], "우측에 문서 판 자리가 없다")
        self.assertTrue(d["create"], "머리에 만들기 손잡이가 없다")
        self.assertGreaterEqual(d["rows"], 1, "프로젝트 줄이 하나도 없다")
        self.assertTrue(all(i.startswith("PRJ-") for i in d["ids"]),
                        "프로젝트가 아닌 줄이 섰다: %r" % d["ids"])
        self.assertIn("프로젝트", d["empty"],
                      "아무것도 안 고른 우측이 무엇을 고르라는지 말하지 않는다")

    def test_the_lens_marks_but_does_not_narrow(self):
        d = self.out["viewing"]
        self.assertEqual(d["before"], d["after"],
                         "헤더 프로젝트 필터가 이 목록을 좁혔다")
        self.assertEqual(d["marked"], 1, "지금 보는 범위 행에 표식이 없다")
        self.assertIn("보는 중", d["text"])

    def test_choosing_a_row_opens_the_document_pane(self):
        d = self.out["row"]
        self.assertEqual(d["tab"], "projects",
                         "행을 눌렀더니 다른 탭으로 튕겼다")
        self.assertTrue(d["panel"], "우측에 프로젝트 문서 판이 안 섰다")
        self.assertTrue(d["members"], "문서 판에 멤버 표가 없다")
        self.assertTrue(d["history"], "문서 판에 이력이 없다 — 문서가 아니다")
        self.assertTrue(d["hash"].startswith("#projects/PRJ-"),
                        "주소가 고른 프로젝트를 안 싣는다: %r" % d["hash"])
