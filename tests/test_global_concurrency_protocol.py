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
            "spawn_agent(task_name, message)",
            "list_agents",
            "followup_task",
            "interrupt_agent",
            "wait_agent",
            "한 assistant message에서",
            "subagent_type",
            "run_in_background:true",
            "TaskOutput",
            "SendMessage",
        )
        for phrase in required:
            self.assertIn(phrase, protocol)

    def test_claude_role_skill_repeats_the_operational_threshold(self):
        skill = read("harness", "claude", "skills", "s9-protocol", "SKILL.md")
        for phrase in ("size S/단일 파일", "size M/L", "최대 3개", "REQ/work order",
                       "별도 T3", "spawn_agent", "list_agents", "Agent"):
            self.assertIn(phrase, skill)

    def test_global_credential_routing_is_local_conditional_and_never_switches_default(self):
        protocol = read("harness", "common", "PROTOCOL.md")
        for phrase in (
                "/home/jade/.bitbucket_creds",
                "/home/jade/chief/bin/atlassian-env.sh",
                "ATLASSIAN_EMAIL",
                "다른 credential source로 바꾸지 않는다",
                "Git fetch/push",
                "Louisville/다른 호스트로 복사·전송하지 않는다",
                "GCP 일반 작업은 crew의 현재 `default` configuration",
                "특별 작업이 명시적으로",
                "gcloud --configuration=jade",
                "gcloud config configurations activate jade",
                "CLOUDSDK_ACTIVE_CONFIG_NAME=jade`를 export하지 않는다",
        ):
            self.assertIn(phrase, protocol)

    def test_codex_reversible_artifact_fast_lane_delivers_primary_output_first(self):
        protocol = read("harness", "common", "PROTOCOL.md")
        adapter = read("harness", "codex", "README.md")
        required = (
            "Codex reversible-artifact fast lane",
            "size M/L",
            "evidence/source",
            "diagram/plot/table",
            "QA 트랙",
            "spawn_agent",
            "리드는 기다리지 않고 primary artifact",
            "basic open/render validation",
            "PPT/report/draft",
            "TDD ceremony",
            "HTML/preview",
            "artifact registry",
            "Section9 note/status",
            "bookkeeping",
        )
        for phrase in required:
            self.assertIn(phrase, protocol)
            self.assertIn(phrase, adapter)

    def test_codex_fast_lane_preserves_durable_external_and_claude_boundaries(self):
        protocol = read("harness", "common", "PROTOCOL.md")
        adapter = read("harness", "codex", "README.md")
        for phrase in (
            "durable code/PR",
            "별도 T3 worker session",
            "merge/push/deploy",
            "production write·traffic·grade/data/resource",
            "destructive action",
            "외부 메시지·게시",
            "Jira 변경·close",
            "credential source",
            "Claude",
            "gate 순서",
        ):
            self.assertIn(phrase, protocol)
            self.assertIn(phrase, adapter)

    def test_installer_manages_global_codex_agents_from_common_protocol(self):
        installer = read("bin", "s9-install")
        self.assertIn('os.path.expanduser("~/.codex/AGENTS.md")', installer)
        self.assertIn('"harness", "common", "PROTOCOL.md"', installer)
        self.assertIn("managed_block(dst, name)", installer)
        self.assertIn("managed_claude_concurrency()", installer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
