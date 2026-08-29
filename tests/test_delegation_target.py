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


class DelegationTargetShortNames(unittest.TestCase):
    """D7~D9. 리드는 대상을 **번호로** 적는다 (REQ-20260829-036-62x6).

    실사고 2026-08-29 20:09:58. 리드가 designer 를 띄우며 description 에
    `030·031 화면 몫` 이라 적었다. 위 D1 의 지명 경로는 정식 id 정규식만 보므로
    그 둘이 하나도 안 잡혔고, prompt 에 배경으로 실린 정식 id 는 여럿이라
    D3(유일하지 않으면 고르지 않는다)에 걸려 클레임 경로로 물러났다. 세션의
    active_reqs 는 [027,024,025,029] 였고 최근 것인 029 가 뽑혔다.

    결과가 둘이다 — 030 은 손이 안 보여 25분째 '멈춤' 이 됐고 20:34 의 깨우기가
    designer 가 `web/index.html` 을 쓰는 중에 무인 작업자를 하나 더 띄웠다.
    029 는 없는 손이 보여 진짜 멈춤이 가려졌다. **한 오귀속이 사고 둘을 낳는다.**

    그래서 둘을 고친다: ① description 의 번호를 살아 있는 요청으로 푼다
    ② 리드가 둘을 적었으면 **둘 다**에 붙인다 — 실제로 둘을 하고 있으니까.
    그리고 추측으로 물러난 경우는 추측이라고 적는다(`--guess`).

    실행: python3 tests/ delegation_target
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9dtn-")
        self.env = {**os.environ, "S9_ROOT": self.root, "S9_MACHINE": "testbox"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        self.ids = [self.mkreq(f"요청 {i}") for i in range(4)]
        for rid in self.ids:
            self.cli("status", rid, "in-progress", "--note", "t",
                     sess="sess1234")
        # 리드가 잡고 있는 것은 마지막 하나뿐 — 위임은 앞의 둘로 간다.
        self.claimed = self.ids[3]
        self.bind([self.claimed])
        self.hook = DelegationTarget.load_hook(self)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    cli = DelegationTarget.cli
    mkreq = DelegationTarget.mkreq
    bind = DelegationTarget.bind

    @staticmethod
    def num(rid):
        """REQ-20260829-030-62x6 → '030' — 리드가 실제로 적는 형태."""
        return rid.split("-")[2]

    def targets(self, inp):
        return self.hook.target_reqs({**self.env, "S9_SESSION": "sess1234"},
                                     inp)

    # ---- D7. 번호 지명이 풀린다 (실사고 재현) ---------------------------
    def test_d7_the_actual_incident(self):
        """description `030·031 화면 몫` + prompt 에 배경 id 여럿."""
        inp = {"description": f"{self.num(self.ids[0])}·{self.num(self.ids[1])}"
                              f" 화면 몫",
               "prompt": f"배경: {self.ids[2]} 와 {self.claimed} 도 보라"}
        got, src = self.targets(inp)
        self.assertEqual(got, [self.ids[0], self.ids[1]],
                         f"리드가 적은 두 문서 대신 {got} 에 붙었다 — "
                         f"도는 요청이 '멈춤' 이 되고 안 도는 요청은 "
                         f"'작업 중' 이 된다 (2026-08-29 20:09 그대로)")
        self.assertEqual(src, "지명")

    def test_d7b_single_number_resolves(self):
        got, _ = self.targets({"description": f"{self.num(self.ids[1])} 백엔드 몫",
                               "prompt": "고쳐라"})
        self.assertEqual(got, [self.ids[1]])

    def test_d7c_dates_and_ports_are_not_doc_numbers(self):
        """네 자리 수와 날짜는 번호가 아니다 — 아무거나 잡으면 오귀속이 는다."""
        got, src = self.targets({"description": "9909 포트와 2026 년치 정리",
                                 "prompt": "그냥 해라"})
        self.assertEqual(got, [self.claimed])
        self.assertEqual(src, "클레임")

    def test_d7d_resolution_lives_in_s9_not_in_the_hook(self):
        """판정은 훅이 아니라 `bin/s9` 에 있다 — 훅은 시험이 잘 안 닿는 자리다."""
        out = self.cli("delegate-target", "--description",
                       f"{self.num(self.ids[0])} 어쩌고", "--session", "sess1234")
        got = json.loads(out)
        self.assertEqual(got["reqs"], [self.ids[0]])
        self.assertEqual(got["src"], "지명")

    # ---- D8. 추측은 추측이라고 적힌다 -----------------------------------
    def test_d8_claim_fallback_is_marked_a_guess(self):
        payload = {
            "tool_name": "Agent", "session_id": "sess1234",
            "tool_input": {"description": "이름 없는 일",
                           "subagent_type": "designer", "prompt": "그냥 해라"},
            "tool_response": {"agentId": "abc12345",
                              "output_file": "/tmp/nonexistent.output"}}
        r = subprocess.run(["python3", AGENT_HOOK], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env={**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(r.returncode, 0, r.stderr)
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        with open(p, encoding="utf-8") as f:
            b = json.load(f)
        self.assertEqual((b.get("agent_req") or {}).get("/tmp/nonexistent.output"),
                         "", "추측을 확정으로 적었다 — 그 손은 '미상' 으로 "
                             "세어져야 겹쳐 띄우기를 막는다")

    def test_d8b_named_target_is_recorded_as_certain(self):
        payload = {
            "tool_name": "Agent", "session_id": "sess1234",
            "tool_input": {"description": f"{self.num(self.ids[1])} 화면",
                           "subagent_type": "designer", "prompt": "고쳐라"},
            "tool_response": {"agentId": "abc12345",
                              "output_file": "/tmp/nonexistent.output"}}
        r = subprocess.run(["python3", AGENT_HOOK], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env={**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(r.returncode, 0, r.stderr)
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        with open(p, encoding="utf-8") as f:
            b = json.load(f)
        self.assertEqual((b.get("agent_req") or {}).get("/tmp/nonexistent.output"),
                         self.ids[1])

    # ---- D9. 둘을 지명하면 둘 다에 기여가 남는다 -------------------------
    def test_d9_both_named_docs_get_the_contribution(self):
        payload = {
            "tool_name": "Agent", "session_id": "sess1234",
            "tool_input": {"description": f"{self.num(self.ids[0])}·"
                                          f"{self.num(self.ids[1])} 화면 몫",
                           "subagent_type": "designer", "prompt": "고쳐라"},
            "tool_response": {"agentId": "abc12345",
                              "output_file": "/tmp/nonexistent.output"}}
        r = subprocess.run(["python3", AGENT_HOOK], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env={**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(r.returncode, 0, r.stderr)
        for rid in self.ids[:2]:
            self.assertIn("sub:designer:abc12345", self.cli("show", rid, "--meta"),
                          f"{rid} 에 위임 기록이 없다")
        self.assertNotIn("sub:designer",
                         self.cli("show", self.claimed, "--meta"),
                         "지명하지 않은 문서에 붙었다")

    # ---- D10. 붙일 곳이 없어도 손은 보인다 ------------------------------
    def test_d10_a_homeless_hand_is_still_registered(self):
        """대상 REQ 를 못 골라도 **손이 있다는 사실**은 남는다.

        종전에는 여기서 훅이 그냥 돌아섰고 바인딩에 transcript 조차 안 남았다 —
        `s9 workers` 도 못 보는 손이 되고, 아무도 못 보는 손 위에 무인 작업자가
        겹쳐 뜬다. 그것이 2026-08-29 20:34 사고의 모양이다."""
        self.bind([])                       # 클레임 없음
        # 실제로 존재하는 파일이어야 한다 — 바인딩 경계(`_norm_binding`)가
        # 파일 아닌 경로를 걷어낸다 (REQ-20260827-011).
        tp = os.path.join(self.root, "hand.output")
        open(tp, "w").write("x")
        payload = {
            "tool_name": "Agent", "session_id": "sess1234",
            "tool_input": {"description": "이름도 번호도 없는 일",
                           "subagent_type": "designer", "prompt": "그냥 해라"},
            "tool_response": {"agentId": "abc12345", "output_file": tp}}
        r = subprocess.run(["python3", AGENT_HOOK], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env={**self.env, "S9_SESSION": "sess1234"})
        self.assertEqual(r.returncode, 0, r.stderr)
        p = os.path.join(self.root, "state", "sessions",
                         "testbox__sess1234.json")
        with open(p, encoding="utf-8") as f:
            b = json.load(f)
        self.assertIn(tp, b.get("agent_transcript_path") or [],
                      "귀속을 못 정했다고 손까지 지웠다")
        self.assertEqual((b.get("agent_req") or {}).get(tp), "",
                         "미상으로 적히지 않았다")
        # 모르는 문서를 잡지는 않는다 — 클레임은 그대로 비어 있어야 한다.
        self.assertEqual(b.get("active_reqs") or [], [],
                         "어느 문서인지 모르면서 문서를 잡았다")

    def test_d10b_claim_without_id_needs_a_transcript(self):
        r = subprocess.run([S9, "claim", "--session", "sess1234"],
                           capture_output=True, text=True, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("문서 id", r.stdout + r.stderr)
