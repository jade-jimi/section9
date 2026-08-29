"""서브에이전트의 말이 한 줄기로 흐른다 (REQ-20260829-014-62x6).

서브에이전트의 말은 리드 세션 transcript 에 **한 줄도 없다** — 별도 파일
(`<sessionUUID>/subagents/agent-<id>.jsonl`)에 isSidechain 으로 쌓인다. 그래서
대시보드 터미널은 스폰 두 줄을 그린 뒤 완료 통지가 올 때까지 통째로 침묵했다.
십 분이고 이십 분이고 "아무 일도 안 하는 화면"이 그 구간의 정답처럼 보였다.

겹치는 자리를 **화면**으로 잡는다. 서버 `/api/stream` 의 offset 은 파일 하나의
바이트값이라 두 파일을 서버에서 머지하면 그 계약이 바뀐다. 원천마다 자기
offset 을 들고 화면이 시각으로만 겹치면 계약은 그대로 두고 침묵만 사라진다 —
읽을 길은 이미 있다(`/api/agents` · `/api/agentstream`).

이 시험이 지키는 계약 — 가장 중요한 것부터:

  ① **열쇠는 표시 시각(ts)이다.** 섞이는 원천이 셋인데(수신함 채팅·리드
     transcript·에이전트 파일) 채팅 줄에는 원본 UTC(`at`)가 없다. UTC 를 우선
     열쇠로 삼으면 UTC 와 지역시각을 나란히 비교하게 되어 채팅 줄이 아홉 시간
     어긋난 자리로 끌려간다 — 이 저장소에서 가장 조용한 실패 모양이다.
  ② **순서가 안정적이다.** 같은 초의 두 줄은 받은 순서를 지킨다. 아니면 같은
     화면이 새로고침마다 다른 이야기를 한다.
  ③ **offset 은 원천마다 따로다.** 에이전트마다 자기 자리에서 이어 받는다 —
     같은 줄을 두 번 그리지 않고, 한 번 실패해도 그 자리를 잃지 않는다.
  ④ **지나간 에이전트를 새로 따라잡지 않는다.** 이미 내려간 에이전트의 옛말을
     지금 자리에 흘리면 순서가 거짓말이 된다. 단 **붙는 순간의 되돌려 읽기는
     규칙이 다르다** — 그때는 과거 전체를 시각 순으로 다시 그리므로 끝난
     에이전트도 포함한다(그러지 않으면 낮에 끝난 위임 구간이 영영 침묵이다).
  ⑤ **누구의 말인지 보인다.** 요약선이 에이전트 종류를 말한다 — 전부 "agent"
     이던 익명이 아니라.

순수 로직은 index.html 안에 `subagent merge core (pure)` 마커로 묶여 있고 이
시험은 그것을 **그대로 떼어 node 로 실행한다**. node 가 없으면 실행 검증만
건너뛰고 소스·서버 계약은 언제나 검사한다.

실행: python3 tests/ subagent_flow
"""
import glob
import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")
S9 = os.path.join(HERE, "..", "bin", "s9")

CORE_RE = re.compile(
    r"/\* ==== subagent merge core \(pure\).*?\*/\n(.*?)\n/\* ==== /subagent merge core",
    re.S)


def find_node():
    n = shutil.which("node") or shutil.which("nodejs")
    if n:
        return n
    for pat in ("/home/*/.vscode-server/bin/*/node",
                "/root/.vscode-server/bin/*/node"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


NODE = find_node()


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class MergeCore(unittest.TestCase):
    """순수 로직을 실제로 돌려 본다."""

    @classmethod
    def setUpClass(cls):
        src = read(INDEX)
        m = CORE_RE.search(src)
        assert m, ("subagent merge core (pure) 블록을 못 찾았다 — 순수 로직이 "
                   "DOM/fetch 와 얽히면 시험이 그것을 못 본다")
        cls.core = m.group(1)

    def run_js(self, body):
        if not NODE:
            self.skipTest("node 없음 — 실행 검증 생략 (소스 계약은 별도 검사)")
        p = subprocess.run([NODE, "-e", self.core + "\n" + body],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout.strip().splitlines()[-1])

    # ---------------------------------------------------------------- ①·②

    def test_lead_and_agent_lines_interleave_by_time(self):
        """리드 줄과 에이전트 줄이 쓰인 시각 순으로 겹친다."""
        got = self.run_js("""
        const lead = [{ts:"2026-08-29 10:00:00", text:"L1"},
                      {ts:"2026-08-29 10:00:04", text:"L2"}];
        const sub  = subTag([{ts:"2026-08-29 10:00:01", text:"S1"},
                             {ts:"2026-08-29 10:00:03", text:"S2"}],
                            {id:"a1", type:"designer"});
        console.log(JSON.stringify(subOrder([...lead, ...sub]).map(e => e.text)));
        """)
        self.assertEqual(got, ["L1", "S1", "S2", "L2"])

    def test_the_chat_line_is_not_dragged_nine_hours(self):
        """채팅 줄(at 없음, 지역시각 ts)이 UTC 와 섞여 제자리를 잃지 않는다."""
        got = self.run_js("""
        const chat = {ts:"2026-08-29T17:41:48+09:00", __chat:true, text:"C"};
        const lead = {ts:"2026-08-29 17:41:47", at:"2026-08-29T08:41:47.000Z", text:"L"};
        const sub  = subTag([{ts:"2026-08-29 17:41:49",
                              at:"2026-08-29T08:41:49.000Z", text:"S"}], {id:"a1"})[0];
        console.log(JSON.stringify(subOrder([sub, chat, lead]).map(e => e.text)));
        """)
        self.assertEqual(got, ["L", "C", "S"])

    def test_the_same_second_keeps_arrival_order(self):
        """같은 초는 받은 순서가 이긴다 — 화면이 매번 다른 이야기를 하지 않게."""
        got = self.run_js("""
        const t = "2026-08-29 10:00:00";
        const evs = [{ts:t, text:"1"}, {ts:t, text:"2"}, {ts:t, text:"3"}];
        console.log(JSON.stringify(subOrder(evs).map(e => e.text)));
        """)
        self.assertEqual(got, ["1", "2", "3"])

    def test_a_line_without_time_keeps_its_place(self):
        """시각이 없는 줄도 사라지지 않는다 — 열쇠가 없으면 받은 자리 그대로."""
        got = self.run_js("""
        const evs = [{ts:"2026-08-29 10:00:02", text:"a"}, {text:"b"},
                     {ts:"2026-08-29 10:00:01", text:"c"}];
        const r = subOrder(evs);
        console.log(JSON.stringify([r.length, r.map(e => e.text)]));
        """)
        self.assertEqual(got[0], 3)
        self.assertIn("b", got[1])

    # ------------------------------------------------------------------ ③

    def test_each_source_carries_its_own_offset(self):
        """따라가던 에이전트는 자기 offset 에서 이어 받는다."""
        got = self.run_js("""
        const subs = {a1:{off:512, type:"designer"}, a2:{off:0, type:"deep-diver"}};
        const rows = [{id:"a1", show:true, type:"designer"},
                      {id:"a2", show:true, type:"deep-diver"}];
        console.log(JSON.stringify(subFollowPlan(subs, rows)
          .map(p => [p.id, p.after, p.type])));
        """)
        self.assertEqual(got, [["a1", 512, "designer"], ["a2", 0, "deep-diver"]])

    def test_a_new_agent_starts_from_the_beginning(self):
        got = self.run_js("""
        console.log(JSON.stringify(
          subFollowPlan({}, [{id:"z", show:true, type:"ux-writer"}])));
        """)
        self.assertEqual(got[0]["after"], 0)
        self.assertFalse(got[0]["tail"])

    # ------------------------------------------------------------------ ④

    def test_a_gone_agent_is_not_newly_followed(self):
        """스트립에서 내려간 에이전트를 처음부터 따라잡지 않는다."""
        got = self.run_js("""
        console.log(JSON.stringify(
          subFollowPlan({}, [{id:"old", show:false, active:false, type:"designer"}])));
        """)
        self.assertEqual(got, [])

    def test_a_followed_agent_gets_one_last_catch_up(self):
        """따라가던 것은 내려간 뒤 **한 번** 더 받고 그것으로 닫는다."""
        got = self.run_js("""
        const rows = [{id:"a1", show:false, active:false, type:"designer"}];
        const first = subFollowPlan({a1:{off:9, type:"designer"}}, rows);
        const after = subFollowPlan({a1:{off:12, type:"designer", tail:true}}, rows);
        console.log(JSON.stringify([first.map(p => [p.id, p.after, p.tail]), after]));
        """)
        self.assertEqual(got[0], [["a1", 9, True]])
        self.assertEqual(got[1], [], "닫은 에이전트를 계속 두드리면 틱마다 요청이 쌓인다")

    def test_show_falls_back_to_active(self):
        """show 를 모르는 구버전 응답은 active 로 읽는다."""
        got = self.run_js("""
        console.log(JSON.stringify([
          subFollowPlan({}, [{id:"a", active:true}]).length,
          subFollowPlan({}, [{id:"b", active:false}]).length]));
        """)
        self.assertEqual(got, [1, 0])

    def test_backfill_includes_the_agents_that_already_finished(self):
        """붙는 순간엔 끝난 에이전트도 되돌려 읽는다 — 과거의 침묵을 메우는 자리."""
        got = self.run_js("""
        const rows = [{id:"live", show:true, type:"designer"},
                      {id:"done", show:false, active:false, type:"deep-diver"}];
        console.log(JSON.stringify(subBackfillPlan(rows)
          .map(p => [p.id, p.after, p.tail])));
        """)
        self.assertEqual(got, [["live", 0, False], ["done", 0, True]])

    def test_backfill_is_bounded(self):
        """에이전트당 되돌려 그릴 줄에 상한이 있다 — 붙을 때마다 수천 줄을 그리지 않게."""
        got = self.run_js("""
        const many = Array.from({length: 900}, (_, i) => ({ts:"t", text:String(i)}));
        const cut = subCap(many);
        console.log(JSON.stringify(
          [cut.length, cut[cut.length - 1].text, SUB_BACKFILL_MAX]));
        """)
        self.assertEqual(got[0], got[2])
        self.assertLessEqual(got[0], 400)
        self.assertEqual(got[1], "899", "상한은 **최근** 줄을 남긴다")

    # ------------------------------------------------------------------ ⑤

    def test_the_line_says_who_spoke(self):
        """태그가 종류·식별자를 싣고 원래 내용을 잃지 않는다."""
        got = self.run_js("""
        const t = subTag([{role:"tool", name:"Edit", text:"x", ts:"t"}],
                         {id:"a7", type:"frontend-developer"})[0];
        console.log(JSON.stringify(t));
        """)
        self.assertTrue(got["agent"])
        self.assertEqual(got["atype"], "frontend-developer")
        self.assertEqual(got["aid"], "a7")
        self.assertEqual(got["text"], "x")
        self.assertEqual(got["name"], "Edit")

    def test_tagging_does_not_mutate_the_source(self):
        """원본을 건드리지 않는다 — 같은 배열을 두 곳이 보고 있다."""
        got = self.run_js("""
        const src = [{text:"x"}];
        subTag(src, {id:"a", type:"designer"});
        console.log(JSON.stringify(src[0]));
        """)
        self.assertEqual(got, {"text": "x"})

    def test_missing_pieces_do_not_throw(self):
        """빈 응답·없는 필드에도 터지지 않는다 — 화면이 멈추는 것이 최악이다."""
        got = self.run_js("""
        console.log(JSON.stringify([
          subOrder(null).length, subTag(null, null).length,
          subCap(null).length, subFollowPlan(null, null).length,
          subBackfillPlan(null).length,
          subFollowPlan({}, [null, {show:true}]).length]));
        """)
        self.assertEqual(got, [0, 0, 0, 0, 0, 0])


class ScreenContract(unittest.TestCase):
    """화면이 실제로 두 원천을 읽어 한 판에 그리는가 (소스 계약)."""

    @classmethod
    def setUpClass(cls):
        cls.src = read(INDEX)

    def test_attach_reads_the_agent_files_too(self):
        """세션에 붙을 때 에이전트 목록과 그 파일을 함께 읽는다."""
        m = re.search(r"async function termAttach\(T, nt\)\{[\s\S]*?\n\}", self.src)
        self.assertTrue(m, "termAttach 를 못 찾았다")
        body = m.group(0)
        self.assertIn("/api/agents?session=", body)
        self.assertIn("/api/agentstream?session=", body)
        self.assertIn("subBackfillPlan", body)
        self.assertIn("subOrder(", body)

    def test_a_tick_keeps_following_while_it_talks(self):
        """살아 있는 동안 증분을 계속 받는 틱이 있다 — 그것도 자기 offset 으로."""
        m = re.search(r"const subTick = async \(\) => \{[\s\S]*?\n  \};", self.src)
        self.assertTrue(m, "subTick 이 없다 — 붙을 때 한 번만 읽으면 다시 침묵한다")
        body = m.group(0)
        self.assertIn("subFollowPlan(T.subs", body)
        self.assertIn("after=${p.after}", body)
        self.assertIn("termScheduleFlush(T)", body)
        self.assertRegex(self.src, r"setInterval\(subTick, \d+\)")

    def test_the_batch_is_drawn_in_time_order(self):
        """한 틱에 들어온 두 원천을 그릴 때 시각으로 겹친다."""
        m = re.search(r"function termScheduleFlush\(T\)\{[\s\S]*?\n\}", self.src)
        self.assertTrue(m)
        self.assertIn("subOrder(T.buf)", m.group(0))

    def test_the_summary_line_names_the_agent(self):
        """요약선이 종류를 말한다 — 익명 'agent · ' 로 되돌아가지 않게."""
        m = re.search(r"function ccEvent\(T, e\)\{[\s\S]*?\n\}", self.src)
        self.assertTrue(m)
        body = m.group(0)
        self.assertIn("e.atype", body)
        self.assertNotIn('agent · ${nm}', body)

    def test_the_summary_line_is_not_a_clock(self):
        """요약선이 시각 도장으로 시작하지 않는다 — 110자 미리보기를 시각이
        먹으면 무슨 말인지가 잘려 나간다 (REQ-20260829-013 과 같은 규칙)."""
        m = re.search(r"function ccEvent\(T, e\)\{[\s\S]*?\n\}", self.src)
        self.assertIn("String(t).replace(STAMP_RE", m.group(0))

    def test_the_agent_tool_line_reads_like_the_lead_one(self):
        """에이전트의 도구 줄도 같은 요약을 쓴다 — 한 판에서 두 문법을 배우지 않게."""
        m = re.search(r"function ccEvent\(T, e\)\{[\s\S]*?\n\}", self.src)
        head = m.group(0).split("if (e.role === \"user\")")[0]
        self.assertIn("ccToolSummary(e.name, t)", head)

    def test_the_attach_resets_the_offsets(self):
        """세션을 바꾸면 offset 도 그 세션의 것으로 — 남의 자리에서 이어 읽지 않는다."""
        m = re.search(r"async function termAttach\(T, nt\)\{[\s\S]*?\n\}", self.src)
        self.assertIn("T.subs = {}", m.group(0))


class ScriptParses(unittest.TestCase):
    """화면 스크립트가 통째로 문법이 맞는가 — 이 판의 가장 나쁜 실패는 빈 화면이다."""

    def test_the_dashboard_script_parses(self):
        if not NODE:
            self.skipTest("node 없음")
        blocks = re.findall(r"<script[^>]*>(.*?)</script>", read(INDEX), re.S)
        self.assertTrue(blocks, "스크립트 블록을 못 찾았다")
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8",
                                         delete=False) as f:
            f.write(max(blocks, key=len))
            path = f.name
        try:
            p = subprocess.run([NODE, "--check", path], capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
        finally:
            os.unlink(path)


class ServerContract(unittest.TestCase):
    """화면이 기대는 두 길이 서버에 있는가."""

    @classmethod
    def setUpClass(cls):
        cls.src = read(S9)

    def test_the_agent_stream_route_exists(self):
        self.assertIn('parsed.path == "/api/agentstream"', self.src)
        self.assertIn('parsed.path == "/api/agents"', self.src)

    def test_the_agent_stream_returns_an_offset_of_its_own(self):
        """에이전트 파일의 offset 은 그 파일의 것이다 — /api/stream 계약은 그대로."""
        m = re.search(r'parsed\.path == "/api/agentstream"[\s\S]{0,1400}', self.src)
        self.assertIn("parse_stream_file(apath, after)", m.group(0))
        m2 = re.search(r"def parse_stream_file\(path, after=0\):[\s\S]*?return \{[\s\S]*?\}",
                       self.src)
        self.assertIn('"offset": new_offset', m2.group(0))

    def test_the_events_carry_both_clocks(self):
        """줄마다 표시 시각(ts)과 원본(at)이 함께 온다 — 정렬 열쇠의 전제."""
        m = re.search(r"def parse_stream_file\(path, after=0\):[\s\S]*?\n        return \{",
                      self.src)
        self.assertIn('ts = local_ts(', m.group(0))
        self.assertIn('at = str(o.get("timestamp") or "")', m.group(0))


class TheSilenceIsFilled(unittest.TestCase):
    """실서버 두 길로 침묵의 구간이 실제로 메워지는가 (통합).

    리드 파일에는 스폰 두 줄과 십 분 뒤 완료 한 줄뿐이고 그 사이는 0이다 —
    사용자가 본 그 화면. 같은 구간의 말이 에이전트 파일에 있고, 화면이 읽는
    두 길(/api/agents · /api/agentstream)로 그것이 온다.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.tmp = tempfile.mkdtemp(prefix="s9subflow-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)

        def cli(*argv, env_extra=None):
            r = subprocess.run([S9, *argv], capture_output=True, text=True,
                               env={**cls.env, **(env_extra or {})}, timeout=20,
                               stdin=subprocess.DEVNULL)
            if r.returncode:
                raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
        cli("init")
        cli("user", "add", "tester")

        cls.sid = "livesess"
        # 세션 바인딩 — 이게 있어야 화면이 그 세션의 기록을 열 수 있다
        cli("log", "session start", env_extra={"S9_SESSION": cls.sid})
        cli("bind", "attach_pid", "1", env_extra={"S9_SESSION": cls.sid})
        apath = os.path.join(cls.tmp, "agent-adeadbeef.jsonl")
        os.makedirs(os.path.join(cls.tmp, "streams"), exist_ok=True)
        lead = [
            {"type": "assistant", "timestamp": "2026-08-29T10:00:00.000Z",
             "message": {"content": [
                 {"type": "text", "text": "designer 에게 맡긴다"},
                 {"type": "tool_use", "id": "tu1", "name": "Agent",
                  "input": {"subagent_type": "designer",
                            "description": "카드 손질"}}]}},
            {"type": "user", "timestamp": "2026-08-29T10:00:01.000Z",
             "message": {"content": [
                 {"type": "tool_result", "tool_use_id": "tu1",
                  "content": f"agentId: adeadbeef\noutput_file: {apath}"}]}},
            {"type": "assistant", "timestamp": "2026-08-29T10:10:00.000Z",
             "message": {"content": [{"type": "text", "text": "끝났다"}]}},
        ]
        with open(os.path.join(cls.tmp, "streams", f"{cls.sid}-full.jsonl"),
                  "w", encoding="utf-8") as f:
            for o in lead:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        with open(apath, "w", encoding="utf-8") as f:
            for i, t in enumerate(("10:02:00", "10:05:00", "10:08:00")):
                f.write(json.dumps({
                    "type": "assistant", "isSidechain": True,
                    "timestamp": f"2026-08-29T{t}.000Z",
                    "message": {"content": [
                        {"type": "text", "text": f"에이전트 진행 {i}"}]}},
                    ensure_ascii=False) + "\n")

        from portpool import free_port, wait_server
        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env={**cls.env, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_server(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def api(cls, path):
        import urllib.request
        with urllib.request.urlopen(
                f"http://127.0.0.1:{cls.port}{path}", timeout=5) as r:
            return json.loads(r.read().decode())

    def test_the_gap_is_empty_in_the_lead_file_and_full_in_the_agent_file(self):
        lead = self.api(f"/api/stream?session={self.sid}")
        row = self.api(f"/api/agents?session={self.sid}")["agents"]
        self.assertEqual([a["id"] for a in row], ["adeadbeef"])
        self.assertEqual(row[0]["type"], "designer")
        sub = self.api(f"/api/agentstream?session={self.sid}&agent=adeadbeef")
        texts = [e["text"] for e in sub["events"]]
        self.assertEqual(texts, ["에이전트 진행 0", "에이전트 진행 1",
                                 "에이전트 진행 2"])
        lo, hi = sub["events"][0]["ts"], sub["events"][-1]["ts"]
        between = [e for e in lead["events"] if lo <= e["ts"] <= hi]
        self.assertEqual(between, [], "리드 파일에 그 구간의 말이 있었다면 "
                                      "이 문서의 전제가 틀린 것이다")
        self.assertTrue(lead["events"][0]["ts"] < lo,
                        "에이전트의 말은 스폰 뒤에 온다")
        self.assertTrue(lead["events"][-1]["ts"] > hi,
                        "완료 통지는 에이전트의 마지막 말 뒤에 온다")

    def test_the_agent_offset_is_its_own_and_increments(self):
        """두 번째 물음엔 새 줄이 없다 — 같은 줄을 두 번 그리지 않는다."""
        first = self.api(f"/api/agentstream?session={self.sid}&agent=adeadbeef")
        self.assertGreater(first["offset"], 0)
        again = self.api(f"/api/agentstream?session={self.sid}"
                         f"&agent=adeadbeef&after={first['offset']}")
        self.assertEqual(again["events"], [])
        self.assertEqual(again["offset"], first["offset"])
        lead = self.api(f"/api/stream?session={self.sid}")
        self.assertNotEqual(lead["offset"], first["offset"],
                            "두 원천의 offset 이 우연히 같으면 이 시험이 "
                            "섞인 것을 못 본다 — 픽스처를 바꿔라")


if __name__ == "__main__":
    unittest.main(verbosity=2)
