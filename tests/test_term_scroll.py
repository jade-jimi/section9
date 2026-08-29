"""스킨이 스트림 본문의 세로 스크롤을 덮지 못한다 (REQ-20260827-010-62x6).

사용자 반려는 "본문이 다 보이지도 않고, 스크롤도 안되고" 두 가지였다.
뒤 절반이 이 테스트가 지키는 계약이다.

`.term`(Stream 탭 본문)은 **자기 자신이 스크롤 컨테이너**다 —
`max-height:calc(100vh - 150px); overflow-y:auto`. calm 스킨이 둥근 모서리를
자르려고 같은 요소에 `overflow:hidden` 을 얹어 그 스크롤을 덮었다.
1440x900 실측: 보이는 654px / 실제 2057px, computed overflow-y = hidden,
굴려도 scrollTop 0, 마지막 이벤트가 상자 밖으로 1376px. 사용자의 기본 스킨이
calm 이라 사용자에게만 무너졌다.

이 저장소는 **같은 함정을 이미 한 번 밟았다**: 세 줄 위 `[data-skin="calm"]
.doclist` 가 REQ-20260826-004 에서 똑같은 이유로 `overflow-x:hidden;
overflow-y:auto` 로 고쳐졌는데, 바로 옆 `.term` 은 같이 고쳐지지 않았다.
그래서 계약을 "calm 을 고쳤다"가 아니라 **"어느 스킨도 `.term` 의 세로 흐름을
덮지 못한다"** 로 적는다 — 다음에 생길 스킨까지 잡히도록.

지키는 것 넷.
  ① 주어가 `.term` 인 어떤 규칙도 세로를 막는 overflow 를 선언하지 않는다
     (스킨 10종 전수 — 새 스킨도 자동으로 걸린다).
  ② 베이스 `.term` 은 높이 상한 + `overflow-y:auto` 를 갖는다
     (스크롤을 죽이는 두 번째 경로 — 규칙 자체가 사라지는 것).
  ③ calm 의 둥근 모서리·그림자는 살아 있다 — 스크롤을 살리자고 스킨의
     성격을 지우면 그것도 결함이다. 가로는 계속 잘린다.
  ④ `.ccterm`(Terminal 탭)은 자기가 스크롤 컨테이너가 아니라 안에
     `.ccout{flex:1;overflow-y:auto}` 를 따로 둔다 — 그래서 거기의
     `overflow:hidden` 은 모서리만 자르고 스크롤은 건드리지 않는다.
     그 면책의 근거가 사라지는 순간(자식 스크롤러를 잃는 순간)을 잡는다.

픽셀이 아니라 이 계약만 본다. 실제 렌더는 measure 프록시 실측 캡처 몫이다.

실행: python3 tests/ term_scroll
"""
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = index_path()

# 세로 흐름을 막는 선언들. overflow 축약형은 한 값이면 세로에도 걸린다.
KILLERS = ("hidden", "clip", "scroll")


def rules(css):
    """CSS 를 (셀렉터목록, 선언블록) 으로 훑는다. @media 안쪽도 그대로 걸린다."""
    for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", css):
        sel, decl = m.group(1).strip(), m.group(2)
        if not sel or sel.startswith("@"):
            continue
        yield sel, decl


def subjects(sel):
    """셀렉터 목록에서 '주어'(마지막 복합 셀렉터)만 뽑는다.
    `[data-skin="calm"] .term` -> `.term`, `.term .ev` -> `.ev`."""
    out = []
    for one in sel.split(","):
        one = one.strip()
        if not one:
            continue
        out.append(re.split(r"[\s>+~]+", one)[-1])
    return out


def decls(block):
    d = {}
    for part in block.split(";"):
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        d[k.strip().lower()] = v.strip().lower()
    return d


class TermScroll(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.src = f.read()
        m = re.search(r"<style>([\s\S]*?)</style>", self.src)
        self.assertIsNotNone(m, "<style> 블록을 찾지 못했다")
        self.css = m.group(1)

    # ---------- ① 어떤 스킨도 세로를 막지 못한다 ----------

    def test_no_rule_kills_vertical_overflow_of_term(self):
        """주어가 .term 인 규칙에 세로를 막는 overflow 선언이 없어야 한다."""
        bad = []
        for sel, block in rules(self.css):
            if not any(s == ".term" for s in subjects(sel)):
                continue
            d = decls(block)
            if d.get("overflow-y") in KILLERS:
                bad.append((sel, "overflow-y:" + d["overflow-y"]))
            ov = d.get("overflow")
            if ov and any(v in KILLERS for v in ov.split()):
                bad.append((sel, "overflow:" + ov))
        self.assertEqual(
            bad, [],
            "`.term` 은 자기 자신이 스크롤 컨테이너다 — 이 선언이 본문 아래쪽을\n"
            "영원히 닿을 수 없게 만든다. 둥근 모서리만 자르고 싶으면\n"
            "`overflow-x:hidden;overflow-y:auto` 를 쓴다 (계약 위반: %r)" % (bad,))

    def test_every_offered_skin_is_reachable_by_the_sweep(self):
        """설정에서 고를 수 있는 스킨 전부가 이 스캔 범위 안에 있는지.

        스캔은 주어가 `.term` 이면 셀렉터를 가리지 않으므로 새 스킨도 자동으로
        걸린다. 다만 스킨 표기 자체가 `[data-skin=…]` 를 떠나면 스캔이 조용히
        헛돌게 되므로, 제공 목록과 CSS 표기가 붙어 있는지를 여기서 못 박는다."""
        m = re.search(r'\{key:"s9skin"[\s\S]*?opts:\[([\s\S]*?)\]\}', self.src)
        self.assertIsNotNone(m, "설정의 skin 목록을 찾지 못했다")
        offered = re.findall(r'\["([a-z]+)",', m.group(1))
        self.assertEqual(len(offered), 10,
                         "스킨이 10종이 아니다: %r" % (offered,))
        styled = set(re.findall(r'\[data-skin="([a-z]+)"\]', self.css))
        # ledger 는 베이스 자체라 override 블록이 없는 것이 정상이다.
        missing = [s for s in offered if s != "ledger" and s not in styled]
        self.assertEqual(missing, [],
                         "이 스킨들이 `[data-skin=…]` 표기를 쓰지 않는다 — "
                         "스캔이 헛돈다: %r" % (missing,))

    # ---------- ② 베이스가 스크롤 컨테이너다 ----------

    def test_base_term_scrolls_within_a_height_cap(self):
        base = [b for s, b in rules(self.css) if s.strip() == ".term"]
        self.assertTrue(base, "베이스 `.term` 규칙을 찾지 못했다")
        d = decls(base[0])
        self.assertIn("max-height", d,
                      "높이 상한이 없으면 페이지 전체가 늘어나 내부 스크롤이 사라진다")
        self.assertEqual(d.get("overflow-y"), "auto",
                         "베이스 `.term` 의 세로 스크롤 선언이 사라졌다")

    # ---------- ③ calm 의 성격은 그대로 ----------

    def test_calm_keeps_rounded_corners_and_shadow_on_term(self):
        """스크롤을 살리자고 calm 의 둥근 모서리·그림자를 지우지 않았다."""
        found = None
        for sel, block in rules(self.css):
            if ".term" not in subjects(sel):
                continue
            if '[data-skin="calm"]' not in sel:
                continue
            found = decls(block)
            break
        self.assertIsNotNone(found, "calm 의 `.term` 규칙을 찾지 못했다")
        self.assertIn("border-radius", found, "calm 의 둥근 모서리가 사라졌다")
        self.assertIn("box-shadow", found, "calm 의 그림자가 사라졌다")
        self.assertEqual(found.get("overflow-x"), "hidden",
                         "가로는 계속 잘려야 한다 — 둥근 모서리 클리핑의 목적")

    # ---------- ④ .ccterm 면책의 근거 ----------

    def test_ccterm_delegates_scrolling_to_an_inner_container(self):
        """.ccterm 의 overflow:hidden 이 안전한 이유는 자식이 대신 구르기 때문이다."""
        out = [b for s, b in rules(self.css) if ".ccout" in subjects(s)]
        self.assertTrue(out, "`.ccout` 규칙을 찾지 못했다")
        self.assertTrue(
            any(decls(b).get("overflow-y") == "auto" for b in out),
            "`.ccterm` 안의 스크롤 담당(`.ccout`)이 세로 스크롤을 잃었다 — "
            "그 순간 `.ccterm` 의 overflow:hidden 은 `.term` 과 같은 함정이 된다")
        self.assertRegex(
            self.src, r'class="ccterm[^"]*"[\s\S]{0,4000}?class="ccout"',
            "`.ccout` 이 `.ccterm` 안에 있어야 위임이 성립한다")


if __name__ == "__main__":
    unittest.main()
