"""시각화 에이전트 강화 계약 (REQ-20260825-057).

designer·ux-writer·frontend-developer는 ux-craft 스킬을 필수 로드하고,
참조 계보(Apple HIG·토스류)를 기준으로 명시해야 한다. 스킬 본문은 원칙
나열이 아니라 실행 규칙(상태 설계·모션·접근성·문구)을 담는다.

실행: python3 tests/ ux_agents
"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.join(HERE, "..", "harness", "claude", "agents")
SKILL = os.path.join(HERE, "..", "harness", "claude", "skills", "ux-craft",
                     "SKILL.md")
VISUAL = ("designer", "ux-writer", "frontend-developer")


class TestUxAgents(unittest.TestCase):
    def _read(self, name):
        with open(os.path.join(AGENTS, name + ".md"), encoding="utf-8") as f:
            return f.read()

    # U1. 세 에이전트 모두 ux-craft를 필수 스킬로 로드
    def test_u1_skill_required(self):
        for a in VISUAL:
            txt = self._read(a)
            self.assertIn("- **ux-craft**", txt, a)
            self.assertIn("필수 스킬", txt, a)

    # U2. 참조 계보가 정의에 명시된다 (요청: Apple·토스 참조)
    def test_u2_reference_lineage(self):
        for a in VISUAL:
            txt = self._read(a)
            self.assertIn("HIG", txt, a)
            self.assertIn("토스", txt, a)

    # U3. 스킬이 실행 규칙을 담는다 — 원칙 이름만 나열하지 않는다
    def test_u3_skill_actionable(self):
        with open(SKILL, encoding="utf-8") as f:
            s = f.read()
        for key in ("빈 상태", "로딩", "에러", "prefers-reduced-motion",
                    "4.5:1", "44", "되돌리기", "자가 점검"):
            self.assertIn(key, s, key)

    # U4. 이 저장소 대시보드에서는 s9-design 시각 언어가 우선임을 명시
    def test_u4_design_system_precedence(self):
        with open(SKILL, encoding="utf-8") as f:
            s = f.read()
        self.assertIn("s9-design", s)


class TestBoardUxApplied(unittest.TestCase):
    """ux-craft 기준의 실제 적용 (REQ-20260825-062) — 보드 화면 계약."""
    def setUp(self):
        with open(os.path.join(HERE, "..", "web", "index.html"),
                  encoding="utf-8") as f:
            self.html = f.read()

    def test_b1_review_point_clamped(self):
        """판정 대기 카드를 훑을 수 있게 확인 포인트는 3줄 클램프."""
        self.assertIn("-webkit-line-clamp:3", self.html)

    def test_b2_no_elapsed_on_terminal(self):
        """완료·취소 카드의 경과시간은 소음 — 표시하지 않는다."""
        self.assertIn("showElapsed", self.html)
        self.assertIn("!TERMINAL.has(r.status)", self.html)

    def test_b3_empty_states_actionable(self):
        """빈 컬럼은 다음 행동을 준다(안내문만 있는 빈칸 금지)."""
        self.assertIn("EMPTY_COL", self.html)
        for key in ("open:", '"in-progress":', "review:"):
            self.assertIn(key, self.html)
        self.assertIn("끌어다 놓으면", self.html)

    def test_b4_keyboard_reachable(self):
        """카드는 키보드로 도달 가능하고 포커스가 보인다."""
        self.assertIn('tabindex="0"', self.html)
        self.assertIn(".card:focus-visible", self.html)

    def test_b5_raw_title_flagged(self):
        """제목이 원문인 카드는 표식으로 드러난다(방치 방지)."""
        self.assertIn("rawt", self.html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
