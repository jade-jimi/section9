"""대시보드 채팅 테스트 (REQ-20260824-032 아키텍처 v3).

세션 간 메시징 없이 수신함 파일(state/terminal/inbox-<sid8>.jsonl) append로
세션을 깨운다. 서버 라우트(/api/chat*)·대상 자동 선택·전이 즉시 통지·훅의
arming 지시 주입을 검증한다.

격리: S9_ROOT=mktemp. 실행: python3 tests/test_dashboard_chat.py
"""
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
HOOK = os.path.join(HERE, "..", "bin", "s9-audit-session")
PHOOK = os.path.join(HERE, "..", "bin", "s9-audit-prompt")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestDashboardChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9chat-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)

        def cli(*argv, env_extra=None, expect=0):
            env = {**cls.env, **(env_extra or {})}
            r = subprocess.run([S9, *argv], capture_output=True, text=True,
                               env=env, timeout=15, stdin=subprocess.DEVNULL)
            if expect is not None and r.returncode != expect:
                raise AssertionError(f"s9 {' '.join(argv)}: rc={r.returncode}\n"
                                     f"{r.stdout}{r.stderr}")
            return r
        cls.cli = staticmethod(cli)

        cli("init")
        cli("user", "add", "tester")

        # 라이브 세션 바인딩: attach_pid=1(항상 생존) + 신선한 스트림 활동
        cls.sid = "livesess"
        env_s = {"S9_SESSION": cls.sid}
        cli("log", "session start", env_extra=env_s)
        cli("bind", "attach_pid", "1", env_extra=env_s)
        os.makedirs(os.path.join(cls.tmp, "streams"), exist_ok=True)
        cls.stream = os.path.join(cls.tmp, "streams", f"{cls.sid}-full.jsonl")
        with open(cls.stream, "w") as f:
            f.write("{}\n")

        # 죽은 세션 바인딩(attach_pid 비생존) — 자동 대상에서 제외돼야 한다
        env_d = {"S9_SESSION": "deadsess"}
        cli("log", "session start", env_extra=env_d)
        cli("bind", "attach_pid", "999999999", env_extra=env_d)

        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env={**cls.env, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    @classmethod
    def api(cls, path, payload=None):
        url = f"http://127.0.0.1:{cls.port}{path}"
        if payload is None:
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), method="POST",
                headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def inbox(self, sid):
        p = os.path.join(self.tmp, "state", "terminal", f"inbox-{sid}.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return [json.loads(x) for x in f.read().splitlines() if x.strip()]

    def touch_stream(self):
        os.utime(self.stream, None)

    # C1. 수신함 기록: POST /api/chat → {ts,from,kind,text} 줄 append (from=whoami)
    def test_c1_chat_appends_inbox(self):
        self.touch_stream()
        code, res = self.api("/api/chat", {"text": "안녕 리드"})
        self.assertEqual(code, 200, res)
        self.assertEqual(res["sid"], self.sid)
        lines = self.inbox(self.sid)
        self.assertTrue(lines)
        last = lines[-1]
        self.assertEqual(last["text"], "안녕 리드")
        self.assertEqual(last["kind"], "chat")
        self.assertTrue(last["from"])   # 서버 파생 whoami
        self.assertTrue(last["ts"])

    # C2. 대상 자동 선택: 살아있는 attach 세션 — 죽은 세션은 제외. sid 명시 우선.
    def test_c2_target_selection(self):
        self.touch_stream()
        code, res = self.api("/api/chat/target")
        self.assertEqual(code, 200)
        self.assertEqual(res["sid"], self.sid)   # deadsess가 아니라 livesess
        self.assertTrue(res["live"])
        # sid 명시 시 그 세션 (죽어 있어도 명시 대상은 존중)
        code, res = self.api("/api/chat/target?sid=deadsess")
        self.assertEqual(res["sid"], "deadsess")
        self.assertFalse(res["live"])

    # C2b. attach_pid가 낡아 죽었어도 신선한 활동(스트림 mtime)이면 살아있다 —
    #      실세션 회귀(재개·프로세스 교체로 pid는 흔히 낡는다)
    def test_c2b_stale_pid_fresh_activity(self):
        env_s = {"S9_SESSION": "stalesess"}
        self.cli("log", "session start", env_extra=env_s)
        self.cli("bind", "attach_pid", "999999998", env_extra=env_s)
        with open(os.path.join(self.tmp, "streams",
                               "stalesess-full.jsonl"), "w") as f:
            f.write("{}\n")
        code, res = self.api("/api/chat/target?sid=stalesess")
        self.assertEqual(code, 200)
        self.assertTrue(res["live"])
        code, res = self.api("/api/chat", {"text": "핑", "sid": "stalesess"})
        self.assertEqual(code, 200, res)
        self.assertEqual(self.inbox("stalesess")[-1]["text"], "핑")

    # C2c. entry=code 세션은 더 오래된 활동이라도 임시 세션(서브에이전트 등)보다
    #      자동 대상에서 우선한다
    def test_c2c_entry_code_priority(self):
        env_c = {"S9_SESSION": "codesess"}
        self.cli("log", "session start", env_extra=env_c)
        self.cli("bind", "attach_pid", "1", env_extra=env_c)
        self.cli("bind", "entry", "code", env_extra=env_c)
        p = os.path.join(self.tmp, "streams", "codesess-full.jsonl")
        with open(p, "w") as f:
            f.write("{}\n")
        old = time.time() - 120           # livesess보다 오래된 활동
        os.utime(p, (old, old))
        self.touch_stream()               # livesess 활동 최신
        try:
            code, res = self.api("/api/chat/target")
            self.assertEqual(res["sid"], "codesess")
        finally:
            self.cli("bind", "entry", "", env_extra=env_c)
            self.cli("bind", "attach_pid", "999999999", env_extra=env_c)
            os.remove(p)

    # C2d. ended(SessionEnd) 세션은 자동 대상에서 제외
    def test_c2d_ended_excluded(self):
        env_e = {"S9_SESSION": "endsess"}
        self.cli("log", "session start", env_extra=env_e)
        self.cli("bind", "attach_pid", "1", env_extra=env_e)
        self.cli("bind", "entry", "code", env_extra=env_e)
        self.cli("bind", "ended", "1", env_extra=env_e)
        self.touch_stream()
        try:
            code, res = self.api("/api/chat/target")
            self.assertNotEqual(res["sid"], "endsess")
        finally:
            self.cli("bind", "entry", "", env_extra=env_e)
            self.cli("bind", "attach_pid", "999999999", env_extra=env_e)

    # C3. 라이브 세션 없음 → 400 + s9 code 안내
    def test_c3_no_live_session(self):
        # 별도 vault로 서버 하나 더 — 바인딩 없음
        tmp2 = tempfile.mkdtemp(prefix="s9chat2-")
        env2 = {**os.environ, "S9_ROOT": tmp2, "S9_USER": "tester"}
        env2.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], capture_output=True, env=env2, timeout=15)
        port2 = free_port()
        srv2 = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(port2)],
            env={**env2, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", port2), 0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port2}/api/chat",
                data=json.dumps({"text": "hi"}).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    code, res = r.status, json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                code, res = e.code, json.loads(e.read().decode())
            self.assertEqual(code, 400)
            self.assertIn("s9 code", res.get("error", ""))
        finally:
            srv2.terminate()
            srv2.wait(timeout=5)

    # C4. 전이 즉시 통지: 반려(review→in-progress) → 클레임 세션 수신함에 event
    def test_c4_transition_event(self):
        r = self.cli("new", "request", "--title", "통지 대상",
                     "--summary", "x", "--goal", "g", "--size", "S",
                     "--body", "b", env_extra={"S9_SESSION": self.sid})
        rid = r.stdout.split()[0]
        self.cli("status", rid, "in-progress", "--note", "착수",
                 env_extra={"S9_SESSION": self.sid})
        self.cli("note", rid, "- [x] T1. ok", "--label", "tdd",
                 env_extra={"S9_SESSION": self.sid})
        self.cli("status", rid, "review", "--note", "완료",
                 env_extra={"S9_SESSION": self.sid})
        self.touch_stream()
        before = len(self.inbox(self.sid))
        code, res = self.api("/api/status",
                             {"id": rid, "to": "in-progress",
                              "note": "반려 사유: 다시"})
        self.assertEqual(code, 200, res)
        self.assertEqual(res.get("notified"), self.sid)
        lines = self.inbox(self.sid)[before:]
        ev = [x for x in lines if x["kind"] == "event"]
        self.assertTrue(ev, lines)
        self.assertIn(rid, ev[-1]["text"])
        self.assertIn("반려", ev[-1]["text"])
        self.assertIn("반려 사유: 다시", ev[-1]["text"])

    # C9. inbox tail(Monitor) 프로세스가 살아있으면 죽은 pid·무활동이어도 live
    #     (REQ-20260824-042: 프롬프트 무관 생존 신호)
    def test_c9_inbox_tail_signal(self):
        env_t = {"S9_SESSION": "tailsess"}
        self.cli("log", "session start", env_extra=env_t)
        self.cli("bind", "attach_pid", "999999996", env_extra=env_t)
        inbox = os.path.join(self.tmp, "state", "terminal", "inbox-tailsess.jsonl")
        os.makedirs(os.path.dirname(inbox), exist_ok=True)
        open(inbox, "a").close()
        tail = subprocess.Popen(["tail", "-f", inbox],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.2)
            code, res = self.api("/api/chat/target?sid=tailsess")
            self.assertTrue(res["live"], res)          # V1
        finally:
            tail.terminate()
            tail.wait(timeout=5)
        time.sleep(0.2)
        code, res = self.api("/api/chat/target?sid=tailsess")
        self.assertFalse(res["live"], res)             # V2

    # C8. 프롬프트 훅이 attach_pid를 매번 재바인딩 — 낡은 pid 자가 치유
    #     (REQ-20260824-041: 유휴 5분 후 no live session 오검출 회귀)
    def test_c8_prompt_hook_rebinds_attach(self):
        env_r = {"S9_SESSION": "rebindss"}
        self.cli("log", "session start", env_extra=env_r)
        self.cli("bind", "attach_pid", "999999997", env_extra=env_r)
        self.cli("bind", "ended", "1", env_extra=env_r)
        r = subprocess.run([PHOOK], input=json.dumps(
            {"session_id": "rebindss-full", "prompt": "실사용 프롬프트다"}),
            capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(r.returncode, 0, r.stderr)
        b = json.loads(self.cli("bind", env_extra=env_r).stdout)
        # _claude_pid()는 조상 체인에서 claude/node를 찾는다(REQ-065) — 테스트
        # 환경에선 상위 하네스 pid일 수 있으므로 '살아있는 프로세스로 갱신됨'만 검증
        pid = int(b["attach_pid"])
        self.assertNotEqual(pid, 999999997)          # 낡은 값이 교체됨
        self.assertTrue(os.path.exists(f"/proc/{pid}"))
        self.assertFalse(b.get("ended"))

    # C5. 훅 주입: SessionStart 컨텍스트에 수신함 경로 + Monitor arming 지시
    def test_c5_hook_injects_arming(self):
        payload = {"session_id": "hooksess-full-id", "source": "startup"}
        r = subprocess.run([HOOK, "start"], input=json.dumps(payload),
                           capture_output=True, text=True,
                           env={**self.env, "S9_PORT": "1"}, timeout=20)
        self.assertIn("inbox-hooksess.jsonl", r.stdout)
        self.assertIn("Monitor", r.stdout)
        self.assertIn("tail -f", r.stdout)
        # 수신함 파일이 미리 생성됨
        self.assertTrue(os.path.exists(os.path.join(
            self.tmp, "state", "terminal", "inbox-hooksess.jsonl")))
        # resume에도 arming 지시는 주입된다 (Monitor는 재개 후 다시 arm 필요)
        r2 = subprocess.run([HOOK, "start"],
                            input=json.dumps({"session_id": "hooksess-full-id",
                                              "source": "resume"}),
                            capture_output=True, text=True,
                            env={**self.env, "S9_PORT": "1"}, timeout=20)
        self.assertIn("inbox-hooksess.jsonl", r2.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
