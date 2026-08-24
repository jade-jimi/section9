"""위임 보고 귀속 테스트 (REQ-20260824-023).

SubagentStop 캡처가 stale last_req 대신, 보고가 언급한 REQ(실행 등록 교집합 우선)에
귀속되고, generic 무언급 진행 보고는 노트를 만들지 않는다.
실행: python3 tests/test_subagent_attr.py
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_loader(
    "s9sub", importlib.machinery.SourceFileLoader(
        "s9sub", os.path.join(HERE, "..", "bin", "s9-audit-subagent")))
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

BIND = json.dumps({"last_req": "REQ-20260824-001",
                   "active_reqs": ["REQ-20260824-002", "REQ-20260824-003"]})


def run_hook(payload, show_rc=0):
    calls = []

    def fake_run(env, *argv, inp=None):
        calls.append((argv, inp))
        out, rc = "", 0
        if argv == ("bind",):
            out = BIND
        elif argv[0] == "show":
            rc = show_rc
        return mock.Mock(returncode=rc, stdout=out)

    with mock.patch.object(hook, "run", fake_run), \
         mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))):
        hook.main()
    return calls


class TestAttribution(unittest.TestCase):
    # C1. 보고가 언급한 REQ가 실행 등록에 있으면 last_req 대신 그쪽으로 귀속
    def test_c1_mentioned_active_wins(self):
        calls = run_hook({"session_id": "s1", "agent_type": "designer",
                          "last_assistant_message":
                          "REQ-20260824-002 재작업 완료 보고"})
        notes = [c for c in calls if c[0][0] == "note"]
        self.assertEqual(len(notes), 1, calls)
        self.assertEqual(notes[0][0][1], "REQ-20260824-002", notes)

    # C2. generic 타입 + REQ 무언급 → 노트 생략(log만)
    def test_c2_generic_unmentioned_skipped(self):
        calls = run_hook({"session_id": "s1",
                          "last_assistant_message": "중간 진행 상황입니다"})
        self.assertFalse([c for c in calls if c[0][0] == "note"], calls)
        self.assertTrue([c for c in calls if c[0][0] == "log"], calls)

    # C3. 역할 명시 에이전트 + 무언급 → 기존대로 last_req 귀속
    def test_c3_typed_falls_back_to_last(self):
        calls = run_hook({"session_id": "s1", "agent_type": "backend-developer",
                          "last_assistant_message": "결과 요약입니다"})
        notes = [c for c in calls if c[0][0] == "note"]
        self.assertEqual(notes[0][0][1], "REQ-20260824-001", calls)

    # C4. 언급 REQ가 등록에 없어도 실문서면 그쪽으로 (show --meta 성공)
    def test_c4_mentioned_existing_doc(self):
        calls = run_hook({"session_id": "s1", "agent_type": "designer",
                          "last_assistant_message": "REQ-20260824-009 관련 산출"})
        notes = [c for c in calls if c[0][0] == "note"]
        self.assertEqual(notes[0][0][1], "REQ-20260824-009", calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
