"""반려된 낱말은 그 파일이 아니라 **화면 전체**에서 걷힌다 (REQ-20260830-039-62x6).

이 게이트가 생긴 실사고는 둘이고, 둘 다 같은 뿌리다.

  ① 사용자가 REQ-20260829-024-62x6 라운드4에서 낱말 둘을 직접 반려했다 —
     "깨우기, 세우기 라는 용어가 너무 어색한데". `card.js` 는 「이어가기」·
     「중단하기」로 고쳤는데, **같은 낱말이 살아 있던 세 자리**(session.js 둘,
     input.js 하나, terminal.js 하나)는 손대지 않았다. 한 화면에 반려어와
     채택어가 나란히 섰고, 그 상태로 다음 반려까지 갔다.
  ② 「맡은 손」도 같은 모양이었다 — 조어 하나를 캡션 자리에 세우고, 같은 뜻의
     낱말이 툴팁·확인창에 따로 남았다.

뿌리는 **반려를 낱말 하나에 내린 판정으로 읽은 것**이다. 반려는 개념에 내린
판정이라, 걷어낼 자리는 그 낱말이 나온 파일이 아니라 사람이 보는 화면 전부다.
그래서 이 시험은 파일을 가리지 않고 `web/app/*.js` 와 `web/*.html` 의 **사용자
문자열 전체**를 훑는다.

주석은 보지 않는다. 주석에는 "사용자가 「깨우기」를 반려했다" 처럼 **반려어를
인용해야만 쓸 수 있는 근거**가 들어 있고, 그 근거를 지우면 다음 사람이 같은
낱말을 다시 짓는다. 개발자 표면(진단 출력)도 같은 이유로 밖에 둔다.

유지 판정 낱말(맡은 창·일손·손길·치운 것·바로 보임 …)은 이 목록에 **없다** —
근거와 함께 REQ-20260830-039-62x6 의 tech-writer 노트에 재론 금지로 남았고,
과잉 게이트는 그 판정을 뒤엎는 다음 사고가 된다.

실행: python3 tests/ screen_lexicon
"""
import glob
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")

# 낱말 → 왜 반려됐고 무엇으로 바뀌었나. 메시지가 곧 다음 사람이 읽을 판정문이다.
BANNED = {
    "맡은 손": "가리킬 실체가 없는 조어 — 「담당」·「없음」으로",
    "세션 깨우기": "사용자가 직접 반려한 낱말(라운드4) — 「여기서 세션 시작」으로",
    "세워 두면": "반려어 「세우기」의 활용형 — 「중단해 두면」으로",
    "세워 둡니다": "반려어 「세우기」의 활용형 — 「중단해 둡니다」로",
    "붙은 일": "국어에 없는 연어 — 「맡은 요청」으로",
    "집기 해제": "같은 × 버튼이 세 은유로 갈렸다 — 「문서 지목 해제」로",
    "자리 지우기": "오류 제목에 내부 은유 — 「계정 지우기」로",
    "화면 조각": "조각 = JS 모듈, 사용자에게 지시 대상이 없다 — 「화면 기능」으로",
    "손잡이가 붙습니다": "사용자 창이 버튼을 손잡이라 부른다 — 「이 버튼이 다시 생깁니다」로",
}
# 낱말 하나가 두 표면에 살면 안 되는 것은 아니다 — 개발자만 보는 진단 출력은
# 이 게이트 밖이다(진단은 코드 말이 오히려 정확하다). 파일 단위로 뺀다.
DIAG_FILES = {"boot.js", "graph.js", "diag.js"}


def _strings(src):
    """주석을 걷고 **따옴표 안**만 남긴다 — 화면에 나가는 것은 그것뿐이다.

    블록/줄 주석을 먼저 지운다. 남은 코드에서 홑·겹따옴표와 백틱 문자열을
    모아 한 덩어리로 잇는다(어느 줄에 있었는지는 아래에서 다시 찾는다)."""
    src = re.sub(r"/\*[\s\S]*?\*/", " ", src)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)
    src = re.sub(r"(?m)\s//[^\"'`]*$", " ", src)
    out = []
    for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"'
                         r"|'((?:[^'\\\n]|\\.)*)'"
                         r"|`((?:[^`\\]|\\.)*)`", src):
        out.append(m.group(1) or m.group(2) or m.group(3) or "")
    return "\n".join(out)


def _html_text(src):
    """HTML 은 태그 밖의 글자와 title·placeholder 같은 사람 읽는 속성만 본다."""
    src = re.sub(r"<!--[\s\S]*?-->", " ", src)
    src = re.sub(r"<script[\s\S]*?</script>", " ", src, flags=re.I)
    keep = " ".join(re.findall(
        r'(?:title|placeholder|aria-label|alt|value)="([^"]*)"', src))
    return re.sub(r"<[^>]*>", " ", src) + "\n" + keep


class ScreenLexicon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surfaces = {}          # 표시 이름 → 사람이 읽는 글자만
        for p in sorted(glob.glob(os.path.join(WEB, "app", "*.js"))):
            name = os.path.basename(p)
            if name in DIAG_FILES:
                continue
            with open(p, encoding="utf-8") as f:
                cls.surfaces["app/" + name] = _strings(f.read())
        for p in sorted(glob.glob(os.path.join(WEB, "*.html"))):
            with open(p, encoding="utf-8") as f:
                cls.surfaces[os.path.basename(p)] = _html_text(f.read())

    def test_the_sweep_actually_read_the_screen(self):
        """게이트가 빈 문자열을 훑고 초록이 되는 일이 없게 — 먼저 눈을 확인한다.

        문자열 추출이 조용히 실패하면 이 시험은 영원히 통과하고, 그때부터
        게이트는 없는 것과 같아진다(이 저장소가 파이프 종료코드에서 배운 것)."""
        self.assertGreaterEqual(len(self.surfaces), 20,
                                "훑은 화면 파일이 너무 적다 — 경로가 틀렸다")
        joined = "\n".join(self.surfaces.values())
        self.assertGreater(len(joined), 50000,
                           "사용자 문자열을 못 읽었다 — 추출기가 고장 났다")
        # 살아 있는 낱말 몇 개로 추출기가 진짜 화면을 봤는지 확인한다
        for anchor in ("이어가기", "중단하기", "선행 대기"):
            self.assertIn(anchor, joined, "화면에 있어야 할 「%s」를 못 찾았다" % anchor)

    def test_no_rejected_word_lives_on_any_screen(self):
        hits = []
        for word, why in BANNED.items():
            for name, text in self.surfaces.items():
                if word in text:
                    hits.append("%s: 「%s」 — %s" % (name, word, why))
        self.assertEqual([], hits,
                         "반려된 낱말이 화면에 남아 있다:\n  " + "\n  ".join(hits))

    def test_the_kept_words_are_not_swept_away(self):
        """유지 판정 낱말까지 함께 지우면 그것이 다음 사고다.

        「맡은 창」은 실재하는 터미널 창을 가리키는 지시어이고, 「일손」은 사전
        낱말이며 늘 "나눠 맡은"을 달고 나온다 — 셋의 4역 합의로 유지가 확정됐다
        (REQ-20260830-039-62x6). 금지 목록이 이들을 삼키지 않았는지 못박는다."""
        for kept in ("맡은 창", "일손", "이어가기", "중단하기", "끝났는지 확인"):
            for word in BANNED:
                self.assertNotIn(kept, word,
                                 "유지 판정 낱말 「%s」가 금지 목록의 「%s」에 "
                                 "삼켜졌다" % (kept, word))

    def test_the_kept_words_still_stand_on_the_screen(self):
        """유지 판정 낱말이 **화면에 살아 있다** — 목록에서 빠진 것만으로는
        지워지지 않았다는 증거가 못 된다. 재론 금지의 근거는 화면이다."""
        joined = "\n".join(self.surfaces.values())
        for kept in ("맡은 창", "일손", "바로 보임", "끝나면 보임", "치운 것",
                     "이어가기", "중단하기", "끝났는지 확인"):
            self.assertIn(kept, joined,
                          "유지 판정 낱말 「%s」가 화면에서 사라졌다" % kept)

    def test_the_replacements_actually_stand(self):
        """걷어낸 자리에 채택어가 실제로 서 있다 — 지우기만 하고 안 채우면
        화면에서 문장이 통째로 사라진다."""
        joined = "\n".join(self.surfaces.values())
        for word in ("여기서 세션 시작", "담당하는 것이 없습니다", "맡은 요청",
                     "문서 지목 해제", "계정 지우기", "화면 기능",
                     "이 버튼이 다시 생깁니다", "선행 작업"):
            self.assertIn(word, joined,
                          "채택어 「%s」가 화면 어디에도 없다" % word)


if __name__ == "__main__":
    unittest.main()
