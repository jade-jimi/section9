"""위임은 **지명된 문서**에 붙는다 (REQ-20260828-041-62x6 ①).

실사고 2026-08-28 21:10. designer 가 REQ-20260828-039 를 실제로 작업 중이었는데
`s9 stalled` 이 "69분째 진전 없음" 으로 실었다. 원인은 판정이 아니라 **입력**이다:
`bin/s9-audit-agent` 의 `target_req()` 가 세션이 클레임한 것(active_reqs·last_req)
중에서만 골라서, 리드가 자기가 클레임하지 않은 문서에 위임하면 그 위임이 엉뚱한
REQ 에 붙거나 아무 데도 안 붙었다. 그날 designer 의 일은 028 에 기록됐다.

`delegated_live()` 는 문서의 `contributions[].result == "running"` 을 보므로
그 오귀속이 그대로 판정 오류가 된다 — 도는 것이 "멈췄다" 로 보인다.

고친 방향: **위임을 띄우는 쪽은 대상을 알고 있다.** 훅이 받는 `tool_input`
(description·prompt)에 리드가 그 REQ 를 적어 넣는다. 추측이 아니라 아는 값을
읽는다. 다만 지명이 **유일하지 않으면 고르지 않는다** — 이 저장소가 반복해 지킨
규칙이고, 엉뚱한 데 붙이는 것보다 아무 데도 안 붙이는 편이 낫다.

실행: python3 tests/ delegation_target
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


class DelegationTarget(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9dt-")
        self.env = {**os.environ, "S9_ROOT": self.root, "S9_MACHINE": "testbox"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        # A: 이 세션이 클레임한 것 / B: 위임이 지명할 것 / C: 두 번째 지명 후보
        self.a = self.mkreq("잡아 둔 것")
        self.b = self.mkreq("실제로 맡긴 것")
        self.c = self.mkreq("또 하나")
        for rid in (self.a, self.b, self.c):
            self.cli("status", rid, "in-progress", "--note", "t", sess="sess1234")
        # 클레임은 A 뿐이다 — 리드가 위임하는 것은 B 다.
        self.bind(active=[self.a], last=self.a)
        self.hook = self.load_hook()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def cli(self, *a, sess=None):
        env = dict(self.env)
        if sess:
            env["S9_SESSION"] = sess
        r = subprocess.run([S9, *a], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0, f"{a}: {r.stderr}"
        return r.stdout.strip()

    def mkreq(self, title):
        return self.cli("new", "request", "--title", title, "--summary", "s",
                        "--size", "S", "--user", "alice", "--goal", "g",
                        "--body", "x").split()[0]

    def bind(self, active, last=""):
        p = os.path.join(self.root, "state", "sessions", "testbox__sess1234.json")
        with open(p, encoding="utf-8") as f:
            b = json.load(f)
        b["active_reqs"] = list(active)
        b["last_req"] = last
        with open(p, "w", encoding="utf-8") as f:
            json.dump(b, f)

    def load_hook(self):
        spec = importlib.util.spec_from_loader(
            "s9ah_dt", importlib.machinery.SourceFileLoader("s9ah_dt", AGENT_HOOK))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def target(self, inp):
        return self.hook.target_req({**self.env, "S9_SESSION": "sess1234"}, inp)

    # ---- D1. 지명이 클레임을 이긴다 -------------------------------------
    def test_d1_named_req_wins_over_session_claim(self):
        got = self.target({"description": "화면 손보기",
                           "prompt": f"{self.b} 를 읽고 그 화면을 고쳐라"})
        self.assertEqual(got, self.b,
                         f"리드가 지명한 {self.b} 대신 {got} 에 붙었다 — "
                         f"실제로 도는 요청이 '멈춤' 으로 보인다")

    def test_d1b_description_names_the_target(self):
        got = self.target({"description": f"{self.b} 화면", "prompt": "고쳐라"})
        self.assertEqual(got, self.b)

    def test_d1c_short_id_resolves_to_canonical(self):
        short = "-".join(self.b.split("-")[:3])   # 접미 없는 짧은 id
        got = self.target({"description": "", "prompt": f"{short} 를 해라"})
        self.assertEqual(got, self.b, "짧은 id 지명이 정식 id 로 풀리지 않는다 — "
                                      "클레임·기여 매칭이 깨진다")

    # ---- D2. 끝난 문서는 지명돼도 고르지 않는다 --------------------------
    def test_d2_terminal_named_falls_back_to_claim(self):
        self.cli("status", self.b, "done", "--note", "t", sess="sess1234")
        got = self.target({"description": "", "prompt": f"{self.b} 를 해라"})
        self.assertEqual(got, self.a,
                         "끝난 문서에 위임이 붙는다 — 화면이 '작업 중' 으로 거짓말한다")

    # ---- D3. 유일하지 않으면 고르지 않는다 -------------------------------
    def test_d3_ambiguous_names_fall_back_to_claim(self):
        got = self.target({"description": "",
                           "prompt": f"{self.b} 를 하되 {self.c} 와 겹치지 마라"})
        self.assertEqual(got, self.a,
                         "지명이 둘인데 하나를 골랐다 — 추측은 오귀속의 입구다")

    def test_d3b_ambiguous_without_claim_attaches_nowhere(self):
        self.bind(active=[], last="")
        got = self.target({"description": "",
                           "prompt": f"{self.b} 와 {self.c} 를 보라"})
        self.assertEqual(got, "",
                         "고를 근거가 없는데 골랐다 — 아무 데도 안 붙이는 편이 낫다")

    # ---- D4. 지명이 없으면 종전 경로 그대로 ------------------------------
    def test_d4_no_mention_keeps_session_claim(self):
        got = self.target({"description": "이름 없는 일", "prompt": "그냥 해라"})
        self.assertEqual(got, self.a)

    def test_d4b_legacy_single_arg_call_still_works(self):
        self.assertEqual(self.hook.target_req(
            {**self.env, "S9_SESSION": "sess1234"}), self.a)

    # ---- D5. 없는 문서를 지명해도 아무 일이 없다 -------------------------
    def test_d5_unknown_id_falls_back(self):
        got = self.target({"description": "",
                           "prompt": "REQ-19990101-001-zzzz 를 해라"})
        self.assertEqual(got, self.a)

    def test_d5b_unknown_id_without_claim_is_empty(self):
        self.bind(active=[], last="")
        got = self.target({"description": "", "prompt": "REQ-19990101-001-zzzz"})
        self.assertEqual(got, "")

    # ---- D6. 훅 전체 경로 — 지명된 문서에 running 이 실제로 남는다 ------
    def test_d6_hook_records_on_named_req(self):
        payload = {
            "tool_name": "Agent", "session_id": "sess1234",
            "tool_input": {"description": "화면 손보기", "subagent_type": "designer",
                           "prompt": f"{self.b} 의 화면을 고쳐라"},
            "tool_response": {"agentId": "abc12345",
                              "output_file": "/tmp/nonexistent.output"}}
        r = subprocess.run(
            ["python3", AGENT_HOOK], input=json.dumps(payload),
            capture_output=True, text=True,
            env={**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(r.returncode, 0, r.stderr)
        meta = self.cli("show", self.b, "--meta")
        self.assertIn("sub:designer:abc12345", meta,
                      "지명된 문서에 위임 기록이 없다 — 화면은 '아무도 안 붙었다'")
        self.assertIn('"result": "running"', meta)
        # 클레임도 그 문서로 간다 — 워처가 겹쳐 띄우지 않게.
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        with open(p, encoding="utf-8") as f:
            self.assertIn(self.b, json.load(f).get("active_reqs") or [])
        # 잡아 두기만 한 문서에는 아무것도 안 붙는다.
        self.assertNotIn("sub:designer", self.cli("show", self.a, "--meta"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
