"""끝난 문서는 클레임을 다시 받지 않는다 (REQ-20260828-036-62x6 0단계).

실사고 2026-08-28 13:35~18:20. REQ-20260828-016 이 13:35 에 done 됐는데, 그 뒤
이 세션이 띄운 위임 **네 건이 전부 그 문서에 `running` 으로 기록됐다.** 실제로
일하던 REQ-20260828-035 는 "아무도 안 붙었다" 로, 끝난 016 은 "에이전트 4명
작업 중" 으로 보였다. 사용자가 세 번 "진짜 진행중인건가" 를 물어야 했던 화면의
거짓말이 여기서 나온다.

경로는 둘이다:
  ① `_claim_req` 에 상태 가드가 없어 done 된 문서가 active_reqs 로 되돌아온다.
     `update_active_reqs` 가 done 전이 때 지운 것을 훅이 되살린다.
  ② `bin/s9-audit-agent` 의 `target_req()` 가 소유만 보고 상태를 안 봐서,
     되살아난 done REQ 가 그 뒤 모든 위임을 빨아들이는 블랙홀이 된다.

되살아난 done 문서는 `agent_health` 의 시야(in-progress 문서) 밖이라 그 좀비
기여가 영영 마감되지 않는다 — vault 에 열린 `running` 이 28건 쌓여 있었다.

실행: python3 tests/ claim_terminal
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
AGENT_HOOK = os.path.join(HERE, "..", "bin", "s9-audit-agent")


class ClaimTerminal(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9ct-")
        self.env = {**os.environ, "S9_ROOT": self.root,
                    "S9_MACHINE": "testbox"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        self.rid = self.cli("new", "request", "--title", "끝난 것",
                            "--summary", "s", "--size", "S", "--user", "alice",
                            "--goal", "g", "--body", "x").split()[0]
        self.live = self.cli("new", "request", "--title", "도는 것",
                             "--summary", "s", "--size", "S", "--user", "alice",
                             "--goal", "g", "--body", "x").split()[0]
        self.cli("status", self.rid, "in-progress", "--note", "t",
                 sess="sess1234")
        self.cli("status", self.rid, "done", "--note", "t", sess="sess1234")
        self.cli("status", self.live, "in-progress", "--note", "t",
                 sess="sess1234")
        os.environ["S9_ROOT"] = self.root
        spec = importlib.util.spec_from_loader(
            "s9_ct", importlib.machinery.SourceFileLoader("s9_ct", S9))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def tearDown(self):
        os.environ.pop("S9_ROOT", None)
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *a, sess=None):
        env = dict(self.env)
        if sess:
            env["S9_SESSION"] = sess
        r = subprocess.run([S9, *a], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0, f"{a}: {r.stderr}"
        return r.stdout.strip()

    def _binding(self):
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return {}

    # N1. done 전이가 active_reqs 에서 지운다 — 기존 계약.
    def test_n1_done_removes_from_active(self):
        self.assertNotIn(self.rid, self._binding().get("active_reqs") or [],
                         "done 인데 등록이 남아 있다")

    # B1. **끝난 문서를 다시 클레임해도 되살아나지 않는다.**
    def test_b1_claim_does_not_resurrect_terminal(self):
        self.cli("claim", self.rid, sess="sess1234")
        ar = self._binding().get("active_reqs") or []
        self.assertNotIn(self.rid, ar,
                         "done 된 문서가 클레임으로 되살아난다 — "
                         "그 뒤 모든 위임을 빨아들이는 블랙홀이 된다")

    # B2. 진행 중인 문서는 그대로 클레임된다 (기능을 죽이지 않는다).
    def test_b2_live_doc_still_claimable(self):
        self.cli("claim", self.live, sess="sess1234")
        self.assertIn(self.live, self._binding().get("active_reqs") or [])

    # B3. 위임 기록의 대상은 **진행 중인 것** 중에서 고른다.
    def test_b3_delegation_target_skips_terminal(self):
        b = self._binding()
        b["last_req"] = self.rid            # 끝난 문서가 포인터에 남아 있다
        b["active_reqs"] = [self.live]
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f)
        spec = importlib.util.spec_from_loader(
            "s9ah", importlib.machinery.SourceFileLoader("s9ah", AGENT_HOOK))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        got = m.target_req({**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(got, self.live,
                         f"끝난 문서({self.rid})에 위임을 붙인다 — "
                         f"화면이 '에이전트 N명 작업 중' 으로 거짓말한다")


if __name__ == "__main__":
    unittest.main()
