"""화면이 조각으로 갈라진 뒤에도 한 장으로 선다 (REQ-20260829-027).

`web/index.html` 은 14,792 줄이었다. 오늘 하루에만 네 팀이 이 파일에 붙었고,
서로를 덮지 않으려고 줄을 세워야 했다 — 한 기능을 고치려면 남의 자리를 열어야
했기 때문이다. 그래서 갈랐다: 껍데기(`web/index.html`) + `web/css/` + `web/app/`.

가르기가 만드는 새 실패 모드는 셋이고, 셋 다 **화면은 멀쩡해 보이면서** 무너진다.

  ① 조각이 사라진다. 껍데기가 부르는 파일이 없으면 그 기능만 조용히 죽는다.
  ② 조각이 고아가 된다. 아무도 안 부르는 파일이 남으면 다음 사람은 그것을
     고치고 화면이 안 바뀐다고 한다 — 오늘 워크트리에서 이미 겪은 종류다.
  ③ 껍데기가 다시 붓는다. 급할 때 규칙 한 줄을 `index.html` 에 인라인으로
     끼워 넣기 시작하면, 몇 주 뒤 이 작업은 없던 일이 된다.

실행: python3 tests/ web_split
"""
import os
import re
import subprocess
import unittest
import urllib.error
import urllib.request

import webasset

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
S9 = os.path.join(ROOT, "bin", "s9")
WEB = os.path.join(ROOT, "web")
SHELL = os.path.join(WEB, "index.html")

from portpool import free_port, wait_server  # noqa: E402

# 껍데기의 천장. 넉넉하되 "판이 하나 더 들어갈 만큼"은 아니다 — 이 숫자를
# 올려야 통과하는 변경이라면, 그것은 조각으로 갔어야 할 변경이다.
SHELL_MAX_LINES = 220


def shell():
    with open(SHELL, encoding="utf-8") as f:
        return f.read()


class Parts(unittest.TestCase):
    """① 부른 조각은 전부 있다 · ② 안 부른 조각은 없다."""

    def test_s1_every_called_part_exists(self):
        css, app = webasset.parts()
        self.assertTrue(css and app, "껍데기가 아무 조각도 부르지 않는다")
        missing = [f"css/{n}" for n in css
                   if not os.path.isfile(os.path.join(WEB, "css", n))]
        missing += [f"app/{n}" for n in app
                    if not os.path.isfile(os.path.join(WEB, "app", n))]
        self.assertEqual(missing, [], "껍데기가 없는 파일을 부른다")

    def test_s2_no_orphan_part(self):
        css, app = webasset.parts()
        for sub, called in (("css", css), ("app", app)):
            on_disk = sorted(n for n in os.listdir(os.path.join(WEB, sub))
                             if not n.startswith("."))
            self.assertEqual(sorted(called), on_disk,
                             f"web/{sub}/ 의 파일과 껍데기가 부르는 목록이 다르다 "
                             "— 아무도 안 부르는 조각은 고쳐도 화면이 안 바뀐다")

    def test_s2b_no_part_called_twice(self):
        css, app = webasset.parts()
        for called in (css, app):
            self.assertEqual(len(called), len(set(called)),
                             "같은 조각을 두 번 부른다 — 순서가 곧 계약인데 "
                             "두 번 실행되면 그 계약이 깨진다")


class Assembled(unittest.TestCase):
    """이어 붙인 한 장이 가르기 전의 그 화면인가."""

    @classmethod
    def setUpClass(cls):
        cls.src = webasset.source()

    def test_s3_the_page_is_whole(self):
        for mark in ('"use strict";', ":root{", "boot();",
                     '<div id="view"></div>', "</html>"):
            self.assertIn(mark, self.src, f"이어 붙인 한 장에 {mark!r} 이 없다")

    def test_s3b_one_style_block_and_one_app_block(self):
        self.assertEqual(self.src.count("<style>"), 1)
        blocks = re.findall(r"<script[^>]*>(.*?)</script>", self.src, re.S)
        self.assertTrue(max(len(b) for b in blocks) > 300000,
                        "가장 큰 스크립트 덩어리가 화면 하나치가 안 된다")


class Shell(unittest.TestCase):
    """③ 껍데기가 다시 붓지 않는다."""

    def test_s4_shell_stays_thin(self):
        n = len(shell().splitlines())
        self.assertLessEqual(
            n, SHELL_MAX_LINES,
            f"web/index.html 이 {n} 줄이다 — 규칙이 껍데기로 되돌아오고 있다. "
            "새 CSS 는 web/css/ 로, 새 JS 는 web/app/ 로 간다")

    def test_s4b_no_style_block_in_shell(self):
        self.assertNotIn("<style>", shell(),
                         "껍데기에 <style> 이 생겼다 — 토큰·규칙의 자리는 "
                         "web/css/ 다 (스킨이 그 순서에 기대고 있다)")

    def test_s5_the_missing_parts_notice_is_inline(self):
        """조각을 못 받았을 때의 알림만은 껍데기 안에 있어야 한다.

        그것을 조각으로 빼면 **자기도 안 온다** — 알릴 사람이 없어지고 화면은
        다시 말 없는 흰 판이 된다. 이 저장소가 낡은 코드 알림에서 이미 산 교훈.
        """
        src = shell()
        inline = re.findall(r"<script>(?!\s*</script>)(.*?)</script>", src, re.S)
        self.assertEqual(len(inline), 1,
                         "껍데기의 인라인 스크립트는 '조각을 못 받았다' 알림 "
                         "하나뿐이어야 한다")
        self.assertIn("__S9_APP_READY", inline[0])
        self.assertIn("--bg", inline[0], "모양(css)이 왔는지도 함께 봐야 한다")

    def test_s5b_the_last_part_raises_the_flag(self):
        _, app = webasset.parts()
        last = os.path.join(WEB, "app", app[-1])
        with open(last, encoding="utf-8") as f:
            self.assertIn("window.__S9_APP_READY = true;", f.read(),
                          f"마지막 조각({app[-1]})이 표식을 세우지 않는다 — "
                          "그러면 알림이 멀쩡한 화면을 지운다")


class Served(unittest.TestCase):
    """서버가 조각을 실제로 내주는가 — 여기가 통과해야 화면이 뜬다.

    껍데기만 내주고 조각을 404 로 돌려주면 사용자는 흰 화면을 본다. 정적 서빙은
    `bin/s9` do_GET 의 몫이고, MIME 까지 맞아야 한다: `text/html` 로 내준
    스타일시트는 표준 모드 브라우저가 **거부한다**(그래서 조각을 `.html` 로
    위장하는 우회는 애초에 성립하지 않는다).
    """

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            # `S9_ROOT` 를 **못박는다**. 다른 시험 모듈 여럿이
            # `os.environ["S9_ROOT"] = <임시자리>` 로 전역을 갈아 끼우는데,
            # 여기서 `os.environ` 을 그대로 물려받으면 서버가 `web/` 이 없는
            # 임시 자리를 뿌리로 삼아 조각을 404 로 돌려준다 — 혼자 돌리면
            # 통과하고 스위트에서만 깨지는, 가장 읽기 어려운 실패다.
            # 이 시험이 묻는 것은 **이 저장소의** 조각이 서빙되는가다.
            env={**os.environ, "S9_ROOT": ROOT, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_server(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    def get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", ""), e.read()

    def test_s6_style_parts_are_served_as_css(self):
        css, _ = webasset.parts()
        st, ctype, body = self.get(f"/css/{css[0]}")
        self.assertEqual(st, 200, f"/css/{css[0]} 를 못 받았다")
        self.assertTrue(ctype.startswith("text/css"),
                        f"스타일시트를 {ctype!r} 로 내준다 — 브라우저가 거부한다")
        self.assertIn(b":root{", body)

    def test_s6b_script_parts_are_served_as_js(self):
        _, app = webasset.parts()
        st, ctype, body = self.get(f"/app/{app[0]}")
        self.assertEqual(st, 200, f"/app/{app[0]} 를 못 받았다")
        self.assertRegex(ctype, r"^(?:application|text)/javascript")
        self.assertIn(b'"use strict";', body)

    def test_s6c_every_part_is_reachable(self):
        css, app = webasset.parts()
        bad = [f"/css/{n}" for n in css if self.get(f"/css/{n}")[0] != 200]
        bad += [f"/app/{n}" for n in app if self.get(f"/app/{n}")[0] != 200]
        self.assertEqual(bad, [], "못 받는 조각이 있다 — 그만큼 화면이 죽는다")

    def test_s6d_no_side_door_out_of_web(self):
        """조각 길이 web/ 밖으로 나가지 않는다 — html 길과 같은 규율."""
        for path in ("/app/../../bin/s9", "/css/../../CLAUDE.md",
                     "/app/../index.html"):
            self.assertNotEqual(self.get(path)[0], 200, f"{path} 가 열린다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
