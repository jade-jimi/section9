"""Global bounded-concurrency contract shared by every Section9 harness."""

import os
import unittest


ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


class GlobalConcurrencyProtocolTests(unittest.TestCase):
    def test_common_protocol_has_bounded_parallel_default_and_safety_boundary(self):
        protocol = read("harness", "common", "PROTOCOL.md")
        required = (
            "전역 병렬 위임 기본값",
            "size S",
            "size M/L",
            "최대 3개 subagent",
            "겹치지 않는 파일/컴포넌트/증거 범위",
            "REQ 또는 repo work order",
            "deploy/production write",
            "리드가 결과를 통합",
            "subagent 기능이 없으면",
            "별도 T3 worker session + work order",
        )
        for phrase in required:
            self.assertIn(phrase, protocol)

    def test_claude_role_skill_repeats_the_operational_threshold(self):
        skill = read("harness", "claude", "skills", "s9-protocol", "SKILL.md")
        for phrase in ("size S/단일 파일", "size M/L", "최대 3개", "REQ/work order",
                       "별도 T3"):
            self.assertIn(phrase, skill)

    def test_installer_manages_global_codex_agents_from_common_protocol(self):
        installer = read("bin", "s9-install")
        self.assertIn('os.path.expanduser("~/.codex/AGENTS.md")', installer)
        self.assertIn('"harness", "common", "PROTOCOL.md"', installer)
        self.assertIn("managed_block(dst, name)", installer)
        self.assertIn("managed_claude_concurrency()", installer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
