"""서버 코드 낡음 알림의 화면 계약 (REQ-20260826-011-62x6).

이 알림이 지켜야 할 것은 "예쁘게 떴는가"가 아니라 **믿을 수 있는가** 세 가지다.
셋 다 코드를 조금만 손대면 조용히 무너지고, 무너져도 화면은 멀쩡해 보인다.

  ① 낡지 않았으면 흔적이 없어야 한다. 상시 자리표시자를 두면 곧 아무도 안
     읽고, 그러면 진짜 낡았을 때도 안 읽힌다. → 마크업은 hidden 으로 시작하고
     stale=false 경로는 반드시 el.hidden = true 로 끝난다.
  ② 자동 재기동은 하지 않는다. 재기동은 진행 중 요청과 SSE 를 끊는다 —
     화면은 사실과 명령까지만 준다. → 알림 경로에서 재기동 API 를 부르지 않고,
     사람이 붙여넣을 명령 문자열을 준다.
  ③ 서버 무응답과 코드 낡음은 다른 사실이다. 터미널 뷰가 쓰는 "stale" 은
     **세션 무응답**을 뜻한다 — 같은 말을 쓰면 둘 다 못 믿게 된다. → 이 알림의
     식별자·사용자 문구는 그 단어를 쓰지 않는다(서버 응답 필드명 d.stale 은
     API 계약이라 예외).

캔버스와 마찬가지로 픽셀은 단위 테스트가 볼 수 없다. 여기서는 "알림을 못
믿게 만들던 방식으로 되돌아갔는가"만 검사한다 — 실제 가시성은 사람의 캡처
검증이 맡는다(test_dep_arrow.py·test_priority_visible.py 와 같은 계보).

실행: python3 tests/ oldcode_banner
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


def _read():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


class OldCodeBanner(unittest.TestCase):
    def setUp(self):
        self.src = _read()

    def test_markup_starts_hidden(self):
        """알림 자리는 기본이 hidden — 낡지 않은 서버에는 흔적이 없다."""
        m = re.search(r'<div class="hrow3" id="oldcode"[^>]*>', self.src)
        self.assertIsNotNone(m, "헤더에 #oldcode 자리가 없다")
        tag = m.group(0)
        self.assertIn("hidden", tag, "기본 hidden 이 아니면 빈 경고 줄이 상시 남는다")
        self.assertIn('role="status"', tag, "동적 알림은 상태 변화를 알려야 한다")

    def test_not_stale_path_hides(self):
        """stale=false 경로는 반드시 감춘다 (그리고 접어둔 기록도 지운다)."""
        body = self._fn("renderOldCode")
        head = body[:body.index("const folded")]
        self.assertIn("el.hidden = true", head,
                      "낡지 않았을 때 감추는 경로가 사라졌다")
        self.assertIn("ocSetAck(null)", head,
                      "재기동된 뒤에도 '접힘'이 남으면 다음 낡음이 한 줄로만 뜬다")

    def test_reads_serveinfo(self):
        """판정 근거는 서버의 /api/serveinfo 하나 — 화면이 자체 추측하지 않는다."""
        body = self._fn("checkOldCode")
        self.assertIn("/api/serveinfo", body)
        self.assertIn("typeof d.stale", body,
                      "무응답을 낡음으로 단정하면 근거 없는 경고가 된다")

    def test_no_auto_restart(self):
        """화면은 재기동을 대신 실행하지 않는다 — 붙여넣을 명령만 준다."""
        js = self._fn("renderOldCode") + self._fn("ocCopyCmd")
        self.assertIn("s9 serve --restart", js, "사용자가 칠 명령이 화면에 없다")
        for banned in ("/api/restart", "/api/serve/restart", "method: \"POST\""):
            self.assertNotIn(banned, js,
                             "알림 경로에서 재기동을 실행하면 진행 중 요청·SSE 가 끊긴다")

    def test_terminology_does_not_collide(self):
        """터미널 뷰의 'stale'(세션 무응답)과 말을 섞지 않는다."""
        js = self._fn("renderOldCode")
        # 서버 응답 필드 d.stale 은 API 계약이므로 제외하고 본다
        js = js.replace("d.stale", "")
        self.assertNotIn("stale", js,
                         "코드 낡음을 'stale' 로 부르면 세션 무응답과 구별되지 않는다")

    def _fn(self, name):
        """function <name>( … ) 의 본문을 중괄호 균형으로 잘라낸다."""
        m = re.search(r"(?:async\s+)?function\s+%s\s*\(" % re.escape(name), self.src)
        self.assertIsNotNone(m, "%s 함수가 없다 — 이름이 바뀌었으면 이 파일도 고쳐라" % name)
        i = self.src.index("{", m.end())
        depth, j = 0, i
        while j < len(self.src):
            if self.src[j] == "{":
                depth += 1
            elif self.src[j] == "}":
                depth -= 1
                if depth == 0:
                    return self.src[i:j + 1]
            j += 1
        self.fail("%s 본문의 끝을 못 찾았다" % name)


if __name__ == "__main__":
    unittest.main()
