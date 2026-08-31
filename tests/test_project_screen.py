"""프로젝트 화면의 계약 — 골격(mock) 몫 (REQ-20260831-028-62x6).

설계(REQ-20260831-026 designer 판정)가 정한 것은 **새 탭 0 · 새 화면 0** 이다.
프로젝트는 문서에 살고, 화면은 세 자리에 얹힌다 — Docs 좌측 목록 · PRJ 문서 뷰
패널 · Board 위 한 줄 띠. 이 파일이 지키는 것은 그 셋의 계약이다.

계약은 둘로 나뉜다.

  ① **읽어서 아는 것** (`web/app/project.js` · `web/css/project.css`) — 문구가
     한 곳에 모였는가, 저장 관문이 하나인가, 색을 리터럴로 적지 않았는가,
     `.proj-info` 를 복제하지 않았는가, 배율이 갈릴 기하를 새로 만들지 않았는가.
     스킨 열 벌이 저마다 색을 말해 둔 자리를 새로 그리면 그 순간 관문이 열
     곳이 된다(벨트 글리프 때의 그 함정).
  ② **띄워 봐야 아는 것** (`web/verify-project.html` + 실브라우저) — 상태마다
     무엇이 그려지는가. 권한이 없을 때 컨트롤이 **회색으로 있는 게 아니라
     없는가**, 멤버 0 인데 넣을 사람도 0 일 때 다른 문구가 서는가, 만료가
     붉은색이 아니라 물러난 색인가, 띠가 정말 한 줄(32px)인가.
     Chrome 이 없으면 그 갈래만 건너뛴다 — 읽어서 아는 것은 그래도 돈다.

실행: python3 tests/ project_screen
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
from portpool import free_port, wait_server   # 포트 규율은 풀 한 곳에서

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), "web")
JS = os.path.join(WEB, "app", "project.js")
CSS = os.path.join(WEB, "css", "project.css")
FIX = "verify-project.html"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def strip_comments(src):
    """/* … */ 와 // … 를 걷어낸다 — 계약은 코드가 하는 말만 본다."""
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"(?m)^\s*//.*$", "", src)


class TheWordsLiveInOnePlace(unittest.TestCase):
    """문구는 `PRJ_TEXT` 한 곳이다 — W2 의 판정이 표 하나만 갈아 끼우면 되게."""

    def test_no_korean_string_outside_the_table(self):
        src = strip_comments(read(JS))
        m = re.search(r"const PRJ_TEXT = \{[\s\S]*?\n\};", src)
        self.assertTrue(m, "PRJ_TEXT 표가 없다")
        rest = src[:m.start()] + src[m.end():]
        stray = re.findall(r"""["'`][^"'`\n]*[가-힣][^"'`\n]*["'`]""", rest)
        self.assertEqual(
            stray, [],
            "화면 글자가 PRJ_TEXT 밖에 있다 — 문구 판정이 한 곳을 못 고친다: %r"
            % stray[:4])

    def test_no_key_is_written_twice(self):
        """같은 이름을 두 번 적으면 **뒤엣것이 앞엣것을 조용히 지운다.**

        실제로 그랬다: 「마지막 활동 없음」을 만들려고 `none: "없음"` 을 더했다가
        목록의 빈 상태 문구(`none: "아직 프로젝트가 없습니다"`)가 통째로 「없음」이
        됐고, 시험은 다 초록이었다(빈 자리가 서 있는지만 봤으므로). 캡처를 눈으로
        보고서야 잡혔다 — 그 눈을 여기 남긴다."""
        src = read(JS)
        m = re.search(r"const PRJ_TEXT = \{([\s\S]*?)\n\};", src)
        keys = re.findall(r"(?m)^\s{2}(\w+):", m.group(1))
        dup = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(dup, [], "PRJ_TEXT 에 같은 이름이 둘 있다: %r" % dup)

    def test_the_fixture_calls_the_real_builders(self):
        """검증 자는 **화면이 쓰는 그 함수**를 부른다 — 베낀 마크업이 아니다.

        베끼면 그 순간부터 둘이 갈라지고, 갈라진 뒤의 캡처는 화면을 증명하지
        않는다. 창도 마찬가지라 `s9dlg` 를 그대로 불러 띄운다(흉내 낸 껍데기는
        실제 캐스케이드와 다를 수 있다 — 처음엔 그렇게 지었다가 걷어냈다)."""
        fix = read(os.path.join(WEB, FIX))
        for fn in ("prjListHTML", "prjPanelHTML", "prjStripHTML",
                   "prjCreateDlg", "prjWire"):
            self.assertIn(fn + "(", fix, "검증 자가 %s 를 부르지 않는다" % fn)
        for copied in ("dlghead", "dlgfoot", "dlgcap"):
            self.assertNotIn(copied, fix,
                             "창 껍데기를 베꼈다(%s) — 진짜 창을 띄워라" % copied)


class TheSaveHasOneGate(unittest.TestCase):
    """설정 인라인이든 멤버 표든 한 문을 지난다 — 두 벌이면 한 벌만 고쳐진다."""

    def test_only_one_fetch(self):
        src = strip_comments(read(JS))
        self.assertEqual(
            len(re.findall(r"\bfetch\(", src)), 1,
            "요청을 보내는 자리가 둘 이상이다 — 저장 규칙이 갈라진다")

    def test_every_write_goes_through_prjpost(self):
        src = strip_comments(read(JS))
        for path in ("/api/project/set", "/api/project/member",
                     "/api/project/member/rm", "/api/project/add"):
            for line in [ln for ln in src.splitlines() if path in ln]:
                self.assertTrue(
                    re.search(r"\b(post|prjPost)\(", line),
                    "%s 가 관문(prjPost) 밖에서 불린다: %s" % (path, line.strip()))

    def test_only_the_status_change_asks_first(self):
        """보관은 그 프로젝트의 문서가 통째로 접히는 사건이라 확인 창을 거친다 —
        나머지 인라인 편집은 묻지 않고 그 자리에서 저장한다(설계 판정)."""
        src = strip_comments(read(JS))

        def between(a, b):
            i = src.index(a)
            j = src.index(b, i)
            return src[i:j]

        # status 컨트롤의 배선 — 멤버 표 배선이 시작되기 전까지
        st = between("stSel.addEventListener", 'querySelectorAll("[data-pjmem]")')
        self.assertLess(st.index("s9dlg({"), st.index('post("/api/project/set"'),
                        "묻기 전에 저장한다")
        # 인라인 값 편집에는 창이 없다 — 되돌리기가 곧 다시 고치기다
        edit = between('querySelectorAll("[data-pjset]")', "const stSel")
        self.assertNotIn("s9dlg(", edit, "값 하나 고치는데 창을 띄운다")
        self.assertIn('post("/api/project/set"', edit, "값 편집이 저장을 안 한다")

    def test_the_screen_does_not_invent_refusals(self):
        """거부 사유는 서버가 준 문장 그대로 — 화면이 지어내면 CLI 와 갈라진다."""
        src = strip_comments(read(JS))
        self.assertIn("d.error", src, "서버 사유를 그리지 않는다")
        for word in ("권한이 없습니다", "실패했습니다", "오류"):
            self.assertNotIn(word, src, "화면이 거부 사유를 지어낸다: %s" % word)


class TheDialogIsBorrowed(unittest.TestCase):
    """창은 `s9dlg` 것이다 — 새 창 부품을 만들지 않는다."""

    def test_it_calls_s9dlg(self):
        self.assertIn("s9dlg({", strip_comments(read(JS)))

    def test_it_does_not_build_its_own_shell(self):
        src = strip_comments(read(JS))
        for cls in ("dlghead", "dlgfoot", "dlgbox", "dlgcap"):
            self.assertNotIn(
                '"' + cls, src,
                "창 껍데기(%s)를 스스로 짓는다 — 창이 두 벌이 된다" % cls)

    def test_the_form_has_four_fields_only(self):
        """넷만이다(표시명·slug·개요·고객). 담당자 4필드는 만들 때 쓰지 않는다."""
        src = read(JS)
        body = re.search(r"function prjFormHTML\(v\)\{[\s\S]*?\n\}", src)
        self.assertTrue(body)
        got = re.findall(r'f\("(\w+)"', body.group(0))
        self.assertEqual(got, ["name", "slug", "summary", "customer"])
        self.assertNotIn("contact_", body.group(0),
                         "만들 때 담당자를 묻는다 — 그 창의 결정은 하나여야 한다")


class TheRulesSayNoColour(unittest.TestCase):
    """규칙 파일은 배치와 밀도만 말한다 — 색은 토큰에서만 온다."""

    def test_no_colour_literal(self):
        body = re.sub(r"/\*[\s\S]*?\*/", "", read(CSS))
        bad = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", body)
        self.assertEqual(bad, [], "색을 직접 적었다: %r" % bad)

    def test_no_round_no_shadow_no_side_bar(self):
        body = re.sub(r"/\*[\s\S]*?\*/", "", read(CSS))
        self.assertNotIn("box-shadow", body, "그림자 금지")
        for m in re.findall(r"border-radius:([^;}]+)", body):
            self.assertEqual(m.strip(), "0", "라운드 금지")
        self.assertFalse(re.search(r"border-left:\s*[1-9]", body),
                         "카드 좌측 세로 띠 금지")

    def test_the_member_table_has_one_gate(self):
        """멤버 표 규칙은 `.pmem` 한 곳 — `.proj-info` 를 복제하지 않는다."""
        body = re.sub(r"/\*[\s\S]*?\*/", "", read(CSS))
        self.assertNotIn(".proj-info", body,
                         "기존 패널 셀렉터를 복제했다 — 관문이 둘이 된다")
        for name in os.listdir(os.path.join(WEB, "css")):
            if name == "project.css":
                continue
            other = re.sub(r"/\*[\s\S]*?\*/", "",
                           read(os.path.join(WEB, "css", name)))
            self.assertNotIn(".pmem", other,
                             "%s 가 멤버 표 규칙을 나눠 갖는다" % name)

    def test_expiry_is_not_a_fault(self):
        """만료는 고장이 아니다 — 붉은 잉크는 실패 줄에만."""
        body = re.sub(r"/\*[\s\S]*?\*/", "", read(CSS))
        self.assertIn(".pmem .m-off{color:var(--muted)}", body)
        for rule in re.findall(r"([^{}]+)\{[^{}]*--c-blocked[^{}]*\}", body):
            self.assertIn("pjerr", rule,
                          "붉은 잉크가 실패 줄 밖에서 쓰인다: %s" % rule.strip())

    def test_no_geometry_that_splits_at_1_25(self):
        """비정수 배율에서 반올림이 갈릴 자리를 새로 만들지 않는다.

        용의자는 홀수 px 상자와 소수 px 테두리다(s9-design 「배율 불변」).
        7px 점은 이미 확정된 무대(.cdot)를 **그대로 쓰는** 것이라 예외다 —
        여기서 다시 그리지 않는다."""
        body = re.sub(r"/\*[\s\S]*?\*/", "", read(CSS))
        for prop, val in re.findall(
                r"\b(width|height|min-height|min-width)\s*:\s*([0-9.]+)px", body):
            n = float(val)
            if (prop, val) in (("width", "7"), ("height", "7")):
                continue                      # .cdot 무대 — 확정값
            self.assertEqual(n, int(n), "%s:%spx — 소수 치수" % (prop, val))
            self.assertEqual(int(n) % 2, 0,
                             "%s:%spx — 홀수 치수는 1.25배에서 갈린다"
                             % (prop, val))
        for w in re.findall(r"border[a-z-]*\s*:\s*([0-9.]+)px", body):
            self.assertEqual(float(w), 1.0, "소수/굵은 테두리: %spx" % w)


# ─── 띄워 봐야 아는 것 ────────────────────────────────────────────────────

PROBE = r"""
(() => {
  const q = (s, r) => (r || document).querySelector(s);
  const qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const cases = qa(".case");
  const byTitle = t => cases.find(c => q("h2", c).textContent.includes(t));
  const cs = (el, p) => getComputedStyle(el).getPropertyValue(p);
  const resolve = v => { const e = document.createElement("span");
    e.style.color = v; document.body.appendChild(e);
    const c = getComputedStyle(e).color; e.remove(); return c; };
  const listN = byTitle("N개"), list0 = byTitle("0개"),
        list1 = byTitle("1개"), listNo = byTitle("만들 권한 없음"),
        pOwner = byTitle("owner (전부"), pMaint = byTitle("maintainer"),
        pView = byTitle("뷰어"), pNoMem = byTitle("넣을 사람 있음"),
        pNoUser = byTitle("등록 사용자도 0"), strip = byTitle("32px 한 줄");
  const rows = qa(".pjrow", listN);
  const ownerTr = q('[data-pjmem="nicehugepark"]', pOwner);
  const maintOwnerTr = q('[data-pjmem="nicehugepark"]', pMaint);
  const stripEl = q(".pjstrip", strip);
  const expTr = qa(".pmem tr.exp", pOwner)[0];
  const soonInp = q('[data-pjmem="e7test"] [data-pjuntil]', pOwner);
  return {
    rowIds: rows.map(r => r.dataset.doc),
    rowMeta: rows.map(r => q(".pjmeta", r).textContent),
    rowStatus: rows.map(r => q(".st", r).textContent),
    listNCreate: !!q("[data-prjnew]", listN),
    list0Create: !!q("[data-prjnew]", list0),
    list0None: (q(".pjnone", list0) || {}).textContent || "",
    list1Head: !!q(".pjhead", list1),
    list1Create: !!q("[data-prjnew]", list1),
    listNoCreate: !!q("[data-prjnew]", listNo),
    fold: (q("[data-prjarc]", listN) || {}).textContent || "",
    ownerControls: qa(".pmem select, .pmem input", pOwner).length,
    viewControls: qa(".pmem select, .pmem input, .pmem button", pView).length,
    viewNote: (q(".pjnote", pView) || {}).textContent || "",
    viewSetEdit: qa("[data-pjset]", pView).length,
    viewSetRows: qa(".pjset tr", pView).length,
    ownerSetRows: qa(".pjset tr", pOwner).length,
    maintOwnerRoleDisabled: q("[data-pjrole]", maintOwnerTr).disabled,
    maintOwnerRoleTitle: q("[data-pjrole]", maintOwnerTr).title,
    ownerRmDisabled: q("[data-pjrm]", ownerTr).disabled,
    rmOffColour: cs(q("[data-pjrm]", ownerTr), "color"),
    rmOnColour: cs(q('[data-pjmem="e7test"] [data-pjrm]', pOwner), "color"),
    ownerRmTitle: q("[data-pjrm]", ownerTr).title,
    ownerRmAria: q("[data-pjrm]", ownerTr).getAttribute("aria-label"),
    caption: q(".pmem caption", pOwner).textContent,
    scopes: qa(".pmem th", pOwner).map(th => th.getAttribute("scope")),
    addRow: !!q(".pjadd", pNoMem),
    noUserTable: !!q(".pmem", pNoUser),
    noUserLink: (q(".pjnote a", pNoUser) || {}).getAttribute
      ? q(".pjnote a", pNoUser).getAttribute("href") : "",
    expColour: expTr ? cs(q(".m-state", expTr), "color") : "",
    // 토큰을 **화면이 푸는 그대로** 재 온다 — `--muted` 는 #hex 로 돌아오고
    // color 는 rgb() 로 돌아와 글자끼리는 견줄 수 없다
    mutedColour: resolve("var(--muted)"),
    blockedColour: resolve("var(--c-blocked)"),
    soonClass: soonInp ? soonInp.className : "",
    stripH: Math.round(stripEl.getBoundingClientRect().height),
    stripLines: qa(".pjstrip > *", stripEl).length,
    stripBorderLeft: cs(stripEl, "border-left-width"),
    stripBg: cs(stripEl, "background-color"),
    stripTable: !!q("table", stripEl),
    stripOpen: (q(".pjs-open", stripEl) || {}).className || "",
    dlgFields: qa("[data-pjf]").map(e => e.dataset.pjf),
    dlgYesDisabled: q(".dlgyes").disabled,
    stripNone: prjStripHTML(null, {}),
  };
})()
"""

TYPE = r"""
(() => {
  const q = s => document.querySelector(s);
  const set = (sel, v) => { const e = q(sel); e.value = v;
    e.dispatchEvent(new Event("input", {bubbles: true})); };
  set('[data-pjf="name"]', %s);
  return {slug: q('[data-pjf="slug"]').value,
          yes: q(".dlgyes").disabled,
          err: q(".pjform .pjerr").textContent,
          errShown: !q(".pjform .pjerr").hidden};
})()
"""

FAIL = r"""
(() => {
  const p = document.querySelector('#failhost .pjpanel');
  const sel = p.querySelector('[data-pjmem="nicehugepark"] [data-pjrole]');
  const was = sel.value;
  sel.value = "maintainer";
  sel.dispatchEvent(new Event("change", {bubbles: true}));
  return new Promise(r => setTimeout(() => {
    const now = document.querySelector('#failhost .pjpanel');
    const line = now.querySelector(".pjerr");
    r({was, back: now.querySelector('[data-pjmem="nicehugepark"] [data-pjrole]').value,
       shown: !line.hidden, text: line.textContent});
  }, 160));
})()
"""

SAVE = r"""
(() => {
  const p = [...document.querySelectorAll(".pjpanel")]
    .find(x => x.dataset.pjslug === "section9");
  const line = p.querySelector(".pjerr");
  const sel = p.querySelector('[data-pjmem="e7test"] [data-pjrole]');
  // ① 값이 그대로면 아무것도 나가지 않는다 (같은 값 재선택 = 요청 0회)
  sel.dispatchEvent(new Event("change", {bubbles: true}));
  return new Promise(r => setTimeout(() => {
    const idle = line.textContent;
    // ② 값이 바뀌면 한 번 나간다
    sel.value = "viewer";
    sel.dispatchEvent(new Event("change", {bubbles: true}));
    setTimeout(() => r({idle, sent: line.textContent}), 120);
  }, 120));
})()
"""


def probe(scale=1.0):
    """검증 자를 실브라우저에 띄워 DOM 을 재 온다 (없으면 SkipTest)."""
    chrome = chrome_path()
    if chrome is None:
        raise unittest.SkipTest("실브라우저 미검증 — Chrome/Edge 를 찾지 못했다")
    win = chrome.startswith("/mnt/")
    marker = "s9prj-%d" % os.getpid()
    prof_wsl = ("/mnt/c/Temp/" + marker) if win else "/tmp/" + marker
    prof_arg = ("C:\\Temp\\" + marker) if win else prof_wsl
    if win:
        os.makedirs("/mnt/c/Temp", exist_ok=True)
    # 검증 자는 조각(css/·app/)을 상대 주소로 부른다 — 파일 하나가 아니라
    # 자리(web/)를 통째로 내주는 정적 서버가 필요하다. 포트는 풀에서 빌리고
    # 기다림은 백오프로 (tests/portpool.py 의 규율).
    port = free_port()
    srv = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=WEB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_server(port)
        url = "http://127.0.0.1:%d/%s" % (port, FIX)
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu",
             "--user-data-dir=" + prof_arg, "--no-first-run",
             "--no-default-browser-check", "--disable-extensions",
             "--disable-background-networking", "--remote-debugging-port=0",
             "--force-device-scale-factor=%g" % scale,
             "--window-size=1280,900", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws = None
        try:
            dev = os.path.join(prof_wsl, "DevToolsActivePort")
            cdp = None
            for _ in range(120):
                if os.path.exists(dev):
                    try:
                        cdp = int(open(dev, encoding="utf-8")
                                  .read().splitlines()[0])
                        break
                    except (ValueError, IndexError, OSError):
                        pass
                time.sleep(0.25)
            if cdp is None:
                raise ConnectionError("DevToolsActivePort 미출현")
            pages = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:%d/json/list" % cdp, timeout=10).read())
            page = next(p for p in pages if p.get("type") == "page")
            ws = WS(page["webSocketDebuggerUrl"])
            # 판이 **실제로 섰는지**를 묻는다 — readyState=="complete" 는
            # about:blank 에서도 참이다. 스위트를 병렬로 돌리면 붙는 순간의
            # 탭이 아직 이동 전이라 빈 판을 재고, 그 위의 모든 물음이
            # null.disabled 로 죽어 열넷이 한꺼번에 ERROR 로 나온다
            # (전체 실행에서 실제로 그랬다 — 단독 실행에서는 안 났다).
            for _ in range(160):
                if ws.eval("document.querySelectorAll('.case').length"):
                    break
                time.sleep(0.25)
            else:
                raise ConnectionError("검증 자가 판을 세우지 못했다")
            out = {"dom": ws.eval(PROBE)}
            out["typed"] = ws.eval(TYPE % json.dumps("고객사 포털 개편"))
            out["typedAscii"] = ws.eval(TYPE % json.dumps("Portal Rework"))
            out["taken"] = ws.eval(TYPE % json.dumps("section9"))
            r = ws.call("Runtime.evaluate", expression=SAVE,
                        returnByValue=True, awaitPromise=True)
            out["saved"] = r.get("result", {}).get("value")
            r = ws.call("Runtime.evaluate", expression=FAIL,
                        returnByValue=True, awaitPromise=True)
            out["failed"] = r.get("result", {}).get("value")
            # 못 잰 것을 **잰 척하지 않는다** — 하나라도 비면 그 자리에서 말한다
            # (안 그러면 시험마다 'NoneType' 이 열넷 쏟아져 원인이 묻힌다).
            for k, v in out.items():
                if v is None:
                    raise ConnectionError("검증 자에서 %s 를 재지 못했다" % k)
            return out
        finally:
            if ws is not None:
                ws.close()
            try:
                proc.terminate()
            except OSError:
                pass
            reclaim(marker, win)
    finally:
        srv.terminate()
        import shutil
        shutil.rmtree(prof_wsl, ignore_errors=True)


class TheStatesAreAllDrawn(unittest.TestCase):
    """상태 전부 — 0·1·N · 보관 · 권한 셋 · 멤버 0 두 갈래 · 만료 · 띠."""

    out = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.out = probe()
        except (ConnectionError, StopIteration, OSError,
                RuntimeError, urllib.error.URLError) as e:
            raise unittest.SkipTest("실브라우저 미검증 — CDP 실패: %r" % e)

    @property
    def d(self):
        return self.out["dom"]

    def test_the_list_sorts_by_recent_work(self):
        """일하는 사람은 최근 것을 찾는다 — 이름순이 아니다."""
        self.assertEqual(self.d["rowIds"],
                         ["PRJ-20260823-001", "PRJ-20260901-002"])
        self.assertIn("멤버 2", self.d["rowMeta"][0])
        self.assertIn("열린 요청 12", self.d["rowMeta"][0])
        self.assertIn("4분 전", self.d["rowMeta"][0])
        self.assertEqual(self.d["rowStatus"], ["active", "active"])

    def test_archived_folds_and_says_so_without_colour(self):
        self.assertEqual(self.d["fold"], "보관됨 1개")

    def test_zero_and_one_keep_the_same_shape(self):
        """0 에서는 안내가 아니라 행동이 서고, 1 에서 구조가 바뀌지 않는다."""
        # 빈 자리의 말은 **문장**이다 — 한 낱말(「없음」)은 안내도 행동도 아니다
        self.assertIn("프로젝트가 없습니다", self.d["list0None"])
        self.assertTrue(self.d["list0Create"])
        self.assertTrue(self.d["list1Head"])
        self.assertTrue(self.d["list1Create"])

    def test_without_the_right_the_button_is_gone_not_grey(self):
        self.assertTrue(self.d["listNCreate"])
        self.assertFalse(self.d["listNoCreate"],
                         "만들 권한이 없는데 단추가 그려졌다 — 회색 단추는 "
                         "눌릴 것 같은 거짓 약속이다")

    def test_the_viewer_sees_values_not_dead_controls(self):
        self.assertGreater(self.d["ownerControls"], 0)
        self.assertEqual(self.d["viewControls"], 0,
                         "뷰어에게 컨트롤을 그렸다")
        self.assertEqual(self.d["viewSetEdit"], 0,
                         "뷰어에게 설정 편집 자리를 그렸다")
        self.assertIn("보기 권한", self.d["viewNote"])

    def test_an_empty_slot_is_a_place_only_for_who_can_fill_it(self):
        """읽기만 하는 사람에게 「— · — · — · —」 넉 줄은 아무 말도 하지 않는다 —
        문서 뷰의 메타 표가 이미 빈 줄을 안 그리는 문법이다(docs.js)."""
        self.assertGreater(self.d["ownerSetRows"], self.d["viewSetRows"],
                           "빈 칸이 고칠 수 없는 사람에게도 자리를 차지한다")

    def test_only_the_owner_row_is_grey(self):
        """maintainer 는 나머지를 고칠 수 있고 owner 행만 잠긴다 — 왜 이 한
        행만 다른가에 답해야 하므로 여기만 회색을 허용한다."""
        self.assertTrue(self.d["maintOwnerRoleDisabled"])
        self.assertIn("owner", self.d["maintOwnerRoleTitle"])

    def test_the_last_owner_cannot_be_removed(self):
        self.assertTrue(self.d["ownerRmDisabled"])
        self.assertIn("마지막 owner", self.d["ownerRmTitle"])
        self.assertIn("nicehugepark", self.d["ownerRmAria"])

    def test_a_dead_button_looks_dead(self):
        """못 누르는 단추가 멀쩡한 단추와 같은 얼굴이면 그것도 거짓 약속이다 —
        `.acts button` 이 잉크색을 못박아 브라우저 기본 회색을 덮는다(실캡처에서
        마지막 owner 의 「제거」가 살아 있는 단추로 보였다)."""
        self.assertNotEqual(self.d["rmOffColour"], self.d["rmOnColour"],
                            "잠긴 「제거」가 살아 있는 것과 같은 잉크다")

    def test_the_table_names_itself_and_its_columns(self):
        self.assertIn("활성", self.d["caption"])
        self.assertTrue(all(s == "col" for s in self.d["scopes"]),
                        "열 머리에 scope 가 없다 — 읽어 주는 화면이 표를 못 읽는다")

    def test_no_members_gives_an_action_or_a_way_out(self):
        self.assertTrue(self.d["addRow"], "넣을 사람이 있는데 추가 행이 없다")
        self.assertFalse(self.d["noUserTable"],
                         "후보가 0명인데 추가 폼을 보여 준다 — 막다른 길이다")
        self.assertEqual(self.d["noUserLink"], "#settings/users")

    def test_expiry_is_muted_not_red(self):
        self.assertEqual(self.d["expColour"], self.d["mutedColour"],
                         "만료 잉크가 --muted 가 아니다")
        self.assertNotEqual(self.d["expColour"], self.d["blockedColour"],
                            "만료를 고장(붉은 잉크)으로 그렸다")
        self.assertIn("m-soon", self.d["soonClass"],
                      "만료 14일 이내인데 임박 잉크가 없다")

    def test_the_strip_is_one_line(self):
        self.assertEqual(self.d["stripH"], 32,
                         "문맥 띠가 한 줄(32px)이 아니다 — 244px 표를 대신하는 자리다")
        self.assertFalse(self.d["stripTable"], "띠에 표가 남아 있다")
        self.assertEqual(self.d["stripBorderLeft"], "0px", "좌측 세로 띠 금지")
        self.assertIn(self.d["stripBg"],
                      ("rgba(0, 0, 0, 0)", "transparent"), "색면 금지")
        self.assertIn("doclink", self.d["stripOpen"])

    def test_the_form_asks_four_things(self):
        self.assertEqual(self.d["dlgFields"],
                         ["name", "slug", "summary", "customer"])
        self.assertTrue(self.d["dlgYesDisabled"],
                        "빈 창인데 확인이 눌린다 — 눌러 보고 다그치는 창이 된다")

    def test_the_slug_candidate_never_guesses_korean(self):
        """한글은 로마자로 옮기지 않는다 — 후보가 없으면 비워 두고 사람이 적는다."""
        self.assertEqual(self.out["typed"]["slug"], "")
        self.assertTrue(self.out["typed"]["yes"])
        self.assertTrue(self.out["typed"]["errShown"])
        self.assertIn("짧은 이름", self.out["typed"]["err"])
        self.assertEqual(self.out["typedAscii"]["slug"], "portal-rework")
        self.assertFalse(self.out["typedAscii"]["yes"])

    def test_a_taken_name_is_told_on_the_spot(self):
        self.assertTrue(self.out["taken"]["yes"], "중복인데 만들 수 있다")
        self.assertIn("이미 있는", self.out["taken"]["err"])

    def test_a_member_change_goes_out_once_through_the_gate(self):
        """바뀐 것만 나간다 — 같은 값을 다시 고르면 요청 0회."""
        self.assertEqual(self.out["saved"]["idle"], "",
                         "값이 그대로인데 요청이 나갔다")
        self.assertIn("/api/project/member", self.out["saved"]["sent"])
        self.assertIn('"role":"viewer"',
                      self.out["saved"]["sent"].replace(" ", ""))

    def test_the_strip_has_no_place_without_a_project(self):
        self.assertEqual(self.d["stripNone"], "",
                         "고른 프로젝트가 없는데 띠가 자리를 먹는다")

    def test_a_refusal_puts_the_control_back_and_says_why(self):
        """거부당하면 ① 컨트롤이 원복되고 ② 사유가 **서버의 말 그대로** 선다.

        ②가 어려운 자리다: 원복은 판을 다시 그리는 일이라, 실패 줄을 미리 잡아 둔
        노드에 쓰면 떨어져 나간 판에 남아 아무도 못 본다(멤버 패널이 한 번 치른 값).
        그래서 화면에 **지금 서 있는** 판에서 읽는다."""
        f = self.out["failed"]
        self.assertEqual(f["back"], f["was"], "거부당했는데 화면에 바뀐 값이 남았다")
        self.assertTrue(f["shown"], "거부 사유가 안 보인다")
        self.assertIn("maintainer 이상이 필요합니다", f["text"],
                      "서버가 준 문장이 아니라 화면이 지어낸 말이 섰다")
