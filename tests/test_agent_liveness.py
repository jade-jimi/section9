"""서브에이전트가 살아 있다는 것이 보이는가 (REQ-20260829-013-62x6).

사용자: "대시보드 터미널에서는 시간의 흐름이나 로그의 흐름, 웨이팅 스크립트
같은 장치가 없어서 작동 중인지 아닌지 즉각 판단이 어렵다."

두 자리가 고장 나 있었다.

**하나 — 라벨이 시각 도장을 말한다.** 스트립의 "지금 하는 일" 자리는 에이전트
응답의 첫 줄을 쓰는데, 이 저장소 규약상 모든 응답이 `` `[시각 - 역할명]` `` 로
시작한다. 그래서 그 자리에 늘 시각만 찍혔다. 규약이 스스로의 눈을 가린 것이다.

**둘 — 조용하면 행이 사라진다.** 스트립은 `active` 인 행만 그리고, 살아있음의
창은 180초다. 그런데 서브에이전트 transcript 93개의 기록 간격 23,203건을 재
보면 180초를 넘는 침묵이 49번(0.21%) 있다 — 긴 도구 하나를 붙잡고 있는
순간들이다. 그때마다 **일하는 중인 에이전트의 행이 화면에서 없어진다.** 침묵이
보이지 않는 것과 침묵이 보이는 것은 다르다: 앞엣것은 "아무 일도 없다"로 읽힌다.

고침의 갈래가 여기서 갈린다. 살아있음의 창을 넓히지 **않는다** — 그것은 죽음을
의심하는 잣대이고, 넓히면 죽은 것을 살아 있다고 말하게 된다(REQ-20260825-089:
한도로 죽은 워커가 10분간 "기동 중"이었던 사고). 대신 **화면에서 지우는 잣대를
따로 둔다**: 조용해도 600초까지는 행을 남기되 조용하다고 적는다. 600초는 잰
값에서 나왔다 — 침묵의 99.98%가 그 안이다.

실행: python3 tests/ agent_liveness
"""
import importlib.machinery
import importlib.util
import os
import re
import unittest
from webasset import index_path   # 화면은 조각이다 — 계약은 이어 붙인 한 장을 본다 (REQ-20260829-027)

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
INDEX = index_path()

STAMP = "`[2026-08-29 10:20:37 KST - designer]`"


def _load():
    spec = importlib.util.spec_from_loader(
        "s9live", importlib.machinery.SourceFileLoader("s9live", S9))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class LabelSkipsTheStamp(unittest.TestCase):
    """L1. 라벨이 시각 도장을 말하지 않는다."""

    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        fn = getattr(cls.m, "agent_label_line", None)
        assert fn, ("agent_label_line() 이 없다 — 도장 건너뛰기 규칙이 "
                    "서버 안쪽에만 있으면 시험이 그것을 못 본다")
        cls.fn = staticmethod(fn)   # 클래스에 그냥 매달면 self 가 딸려 들어간다

    def test_the_stamp_alone_yields_nothing(self):
        """도장만 있는 응답은 라벨이 없다 — 시각을 '하는 일'로 적지 않는다."""
        self.assertEqual(self.fn(STAMP), "")

    def test_the_line_after_the_stamp_wins(self):
        """도장 다음의 뜻 있는 줄이 라벨이다."""
        self.assertEqual(self.fn(f"{STAMP}\n\n원인과 경계가 잡혔다. 계약을 먼저 잠근다."),
                         "원인과 경계가 잡혔다. 계약을 먼저 잠근다.")

    def test_a_stamp_with_text_on_the_same_line(self):
        """도장 뒤에 같은 줄로 이어 쓴 경우도 도장은 버린다."""
        self.assertEqual(self.fn(f"{STAMP} Red(8). 구현한다."), "Red(8). 구현한다.")

    def test_plain_text_is_untouched(self):
        """도장이 없으면 첫 줄 그대로 — 흔한 경우를 망치지 않는다."""
        self.assertEqual(self.fn("이제 실브라우저로 본다.\n둘째 줄"),
                         "이제 실브라우저로 본다.")

    def test_it_is_bounded(self):
        """한 줄 자리다 — 문단이 통째로 들어가면 스트립이 무너진다."""
        self.assertLessEqual(len(self.fn("가" * 400)), 70)

    def test_empty_is_empty(self):
        for s in ("", "   ", "\n\n"):
            with self.subTest(repr(s)):
                self.assertEqual(self.fn(s), "")


class QuietIsNotGone(unittest.TestCase):
    """L2·L3·L4. 조용함과 사라짐은 다른 일이다."""

    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    def test_the_death_window_is_untouched(self):
        """L4. 죽음의 잣대는 그대로다 — 넓히면 죽은 것이 살아 보인다."""
        self.assertEqual(self.m.HEALTH_WIN["sub"], 180,
                         "살아있음의 창을 넓혔다 — REQ-20260825-089 의 사고로 "
                         "되돌아가는 길이다. 넓혀야 할 것은 화면에서 지우는 잣대다")

    def test_there_is_a_separate_keep_window(self):
        """L2·L3. 지우는 잣대가 따로 있고, 잰 값에서 나왔다."""
        keep = getattr(self.m, "AGENT_KEEP_SEC", None)
        self.assertIsNotNone(keep, "AGENT_KEEP_SEC 이 없다")
        self.assertGreater(keep, self.m.HEALTH_WIN["sub"],
                           "지우는 잣대가 죽음의 잣대보다 좁으면 아무 의미가 없다")
        self.assertGreaterEqual(keep, 600,
                                "측정: 침묵의 99.98%가 600초 안이다. 그보다 좁으면 "
                                "일하는 에이전트의 행이 계속 사라진다")

    def test_the_row_carries_quiet_and_show(self):
        """행이 스스로 말한다 — 화면이 자기 숫자를 들면 헬스체크와 갈린다."""
        i = self.src.find("srvAgents")
        self.assertGreaterEqual(i, 0)
        for key in ("quiet", "show"):
            self.assertRegex(self.src, r"\ba\.%s\b" % key,
                             f"화면이 {key} 를 읽지 않는다")

    def test_the_strip_no_longer_filters_on_active_alone(self):
        """L2. `active` 만으로 거르면 조용한 순간마다 행이 사라진다."""
        m = re.search(r"const srv = \(T\.srvAgents \|\| \[\]\)\.filter\("
                      r"(.+?)\)", self.src)
        self.assertIsNotNone(m, "스트립 필터를 찾지 못했다")
        self.assertNotEqual(m.group(1).strip(), "a => a.active",
                            "여전히 active 만 본다 — 180초 침묵마다 행이 사라진다")
        self.assertIn("show", m.group(1), "지우는 잣대(show)를 보지 않는다")

    def test_quiet_is_said_out_loud(self):
        """조용하다는 사실이 행에 적힌다 — 안 적히면 멈춘 것과 구별이 안 된다."""
        self.assertRegex(self.src, r'AGENT_QUIET_MARK\s*=\s*"[^"]+"',
                         "조용함을 말하는 낱말이 없다")

    def test_the_target_chip_is_released_on_the_same_rule(self):
        """회귀: 지목 해제도 같은 잣대를 쓴다 — 갈리면 조용해진 순간에 지목이
        풀렸다가 다시 붙는다."""
        m = re.search(r"termTargetClear\(T, \"대상이 종료돼[\s\S]{0,80}", self.src)
        self.assertIsNotNone(m, "지목 자동 해제 자리를 찾지 못했다")
        blk = self.src[max(0, self.src.find("T.srvAgentsOk && T.target") - 40):]
        self.assertIn("a.show", blk[:400],
                      "지목 해제가 여전히 active 만 본다")


class TheScreenKeepsMoving(unittest.TestCase):
    """L5·L6. 리드가 조용해도 화면은 서브에이전트를 따라 움직인다."""

    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    def _fn(self, name):
        m = re.search(r"function %s\([^)]*\)\{[\s\S]*?\n\}" % name, self.src)
        self.assertIsNotNone(m, "%s() 를 찾지 못했다" % name)
        return m.group(0)

    def test_the_spinner_watches_subagents_too(self):
        """L5. 리드가 async 에이전트를 띄우고 조용해지면 lastRole 은
        assistant 가 된다 — 그때 스피너가 꺼지면 한 시간짜리 작업 내내 화면이
        완전 정지다."""
        fn = self._fn("termSpinnerEval")
        self.assertIn("srvAgents", fn,
                      "스피너가 리드의 마지막 이벤트만 본다")

    def test_elapsed_ticks_without_events(self):
        """L6. 이벤트가 안 와도 초가 오른다 — 멈춘 숫자는 멈춘 것으로 읽힌다."""
        self.assertRegex(self.src, r"agTick|termAgentsTick",
                         "스트립의 초를 올리는 자리가 없다")
        m = re.search(r"function termAgentsTick\([\s\S]{0,700}", self.src)
        self.assertIsNotNone(m, "termAgentsTick() 이 없다")
        self.assertIn("setInterval", m.group(0),
                      "1초마다 올리는 자리가 없다")
        self.assertNotIn("innerHTML", m.group(0),
                         "초를 올리려고 행을 다시 짓는다 — 누르던 손잡이가 "
                         "1초마다 사라진다")


if __name__ == "__main__":
    unittest.main()
