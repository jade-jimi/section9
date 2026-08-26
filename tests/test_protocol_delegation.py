"""디자인 위임 규약 영속화 계약 테스트 (REQ-20260825-082, 승인 후속 REQ-057).

승인 메모 "화면 디자인은 기본적으로 새로 만든 에이전트를 사용"이 CLAUDE.md에만
있고(47a975e) 하네스 공통 규약 원본(harness/common/PROTOCOL.md)에는 없으면,
GEMINI.md/AGENTS.md 주입 경로가 규칙을 받지 못해 드리프트한다. 이 계약이 고정한다.
실행: python3 tests/test_protocol_delegation.py
"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestProtocolDelegation(unittest.TestCase):
    # P1. PROTOCOL.md에 designer 기본 위임과 스킬 계보·금지 제약이 명시된다
    def test_p1_protocol_has_design_delegation(self):
        proto = read("harness", "common", "PROTOCOL.md")
        for kw in ["designer", "s9-design", "browser-verify",
                   "색면 하이라이트", "세로 띠", "무채색 미니멀"]:
            self.assertIn(kw, proto, f"PROTOCOL.md에 '{kw}' 누락")

    # P2. CLAUDE.md와 PROTOCOL.md가 같은 핵심 규칙을 담는다 (드리프트 방지)
    def test_p2_claude_md_in_sync(self):
        claude = read("CLAUDE.md")
        for kw in ["designer", "s9-design", "색면 하이라이트", "무채색 미니멀"]:
            self.assertIn(kw, claude, f"CLAUDE.md에 '{kw}' 누락")

    # P3. 시각화 3 에이전트 정의가 s9-design 스킬을 참조한다 (U계약 유지)
    def test_p3_agents_reference_ux_craft(self):
        for name in ["designer", "ux-writer", "frontend-developer"]:
            body = read("harness", "claude", "agents", name + ".md")
            self.assertIn("s9-design", body, f"{name}.md에 s9-design 누락")


if __name__ == "__main__":
    unittest.main(verbosity=2)
