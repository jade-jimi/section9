"""맥에서 살아 있음을 못 본다 (REQ-20260829-037).

친구의 맥북에서 대시보드 터미널이 **대화는 되는데** 하단이 `live` 가 아니라
`idle` 로 섰다. 화면의 그 글자는 `/api/chat/target` 의 `listening` 하나로
정해지고(`web/app/terminal.js`), `listening` 은 `_inbox_watch_alive()` 다.
그 함수는 `/proc` 를 뒤진다 — **맥에는 `/proc` 이 없다.** 그래서 수신 대기
tail 이 멀쩡히 돌아도 판정은 언제나 거짓이었다. `chat_live` 의 attach pid
검사(`os.path.exists("/proc/<pid>")`)도, 워커 생존(`_pid_is_claude`)도,
계정 조회(`/proc/<pid>/environ`)도, 포트 주인(`/proc/net/tcp`)도 같은 자리에
서 있었다.

고침의 모양은 "맥용 분기를 여기저기 덧대기"가 아니다. **프로세스를 보는 눈을
한 문으로 모으고(`proc_table`·`pid_alive`·`pid_comm`·`pid_cmdline`), 그 문
안에서만 플랫폼을 가른다.** 문이 여럿이면 플랫폼 구멍도 여럿이 된다.

맥이 이 자리에 없으므로 **갈래를 가짜로 세워** 시험한다: `S9_PROC_BACKEND`
로 `/proc` 을 못 쓰는 기계인 척하고, 리눅스에서 돌던 것과 **같은 답**이
나오는지를 본다. 이것은 "맥에서 된다"의 증명이 아니라 "맥이라면 어느 길로
가고 그 길이 답을 내는가"의 못박음이다 — 그 구별을 보고에 정직하게 적는다.

실행: python3 tests/ platform_live
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import portpool                 # 포트는 풀에서만 (REQ-20260825-100)

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

TMP = tempfile.mkdtemp(prefix="s9plat-")
_prev = {k: os.environ.get(k) for k in ("S9_ROOT", "S9_MACHINE",
                                        "S9_PROC_BACKEND")}
os.environ.update({"S9_ROOT": TMP, "S9_MACHINE": "testbox"})
os.environ.pop("S9_PROC_BACKEND", None)
try:
    spec = importlib.util.spec_from_loader(
        "s9_mod_plat", importlib.machinery.SourceFileLoader("s9_mod_plat", S9))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
finally:
    for k, v in _prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

BACKENDS = ("proc", "ps")     # 이 기계에서 실제로 돌려 볼 수 있는 두 갈래


def backend(name):
    """그 갈래인 척하고 캐시를 비운 뒤 돌린다."""
    mod.proc_cache_clear()
    ctx = mock.patch.dict(os.environ, {"S9_PROC_BACKEND": name})
    ctx.start()
    return ctx


class Backend:
    """`with Backend("ps"):` — 갈래 강제 + 앞뒤로 캐시 비우기."""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.ctx = backend(self.name)
        return self

    def __exit__(self, *a):
        self.ctx.stop()
        mod.proc_cache_clear()
        return False


class TailProc:
    """진짜 수신함 tail 한 벌 — pid 를 지어내면 이 판정을 시험할 수 없다."""

    def __init__(self, sid8):
        self.path = os.path.join(TMP, "state", "terminal",
                                 f"inbox-{sid8}.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        open(self.path, "a").close()
        self.proc = subprocess.Popen(
            ["tail", "-c", "+1", "-f", self.path], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):          # exec 이 끝나야 명령줄이 보인다
            mod.proc_cache_clear()
            if mod._inbox_watch_alive(sid8):
                break
            time.sleep(0.02)

    def kill(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=5)
        except Exception:
            pass


class TestBackendGate(unittest.TestCase):
    """S1·S6. 판정이 지나는 문은 하나고, 문이 없으면 조용히 거짓이다."""

    def test_s1_linux_uses_proc(self):
        """이 기계(리눅스/WSL)는 예전 길 그대로 `/proc` 을 쓴다."""
        mod.proc_cache_clear()
        self.assertEqual(mod.proc_backend(), "proc")

    def test_s1b_proc_table_sees_myself(self):
        """어느 갈래로 보든 **나 자신**은 목록에 있고 명령줄이 붙는다."""
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                t = mod.proc_table()
                self.assertIn(os.getpid(), t, f"{name}: 내 pid 가 안 보인다")
                self.assertIn("python", t[os.getpid()].lower())

    def test_s6_no_backend_is_false_not_crash(self):
        """프로세스를 볼 수 없는 자리에서도 죽지 않는다 — 판정이 없던 때와
        같게 동작한다(거짓). 예외를 던지면 대시보드 폴 전체가 멎는다."""
        with Backend("none"):
            self.assertEqual(mod.proc_table(), {})
            self.assertFalse(mod.pid_alive(os.getpid()))
            self.assertFalse(mod._inbox_watch_alive("abcd1234"))
            self.assertEqual(mod.pid_cmdline(os.getpid()), "")
            self.assertFalse(mod._session_proc_alive("deadbeef"))


class TestInboxWatch(unittest.TestCase):
    """S2. 이 REQ 의 본체 — 맥 갈래에서도 수신 대기가 보여야 한다."""

    @classmethod
    def setUpClass(cls):
        cls.sid = "ab12cd34"
        cls.tail = TailProc(cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.tail.kill()
        mod.proc_cache_clear()

    def test_s2_both_backends_agree_on_listening(self):
        """`/proc` 갈래와 `ps` 갈래가 **같은 답**을 낸다. 맥이 idle 로 굳던
        이유가 바로 이 둘이 갈렸기 때문이다."""
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertTrue(mod._inbox_watch_alive(self.sid),
                                f"{name}: 도는 tail 을 못 봤다")

    def test_s2b_other_session_is_not_listening(self):
        """남의 세션까지 살아 있다고 하면 판정이 아니라 소음이다."""
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertFalse(mod._inbox_watch_alive("00000000"))

    def test_s2c_empty_sid_is_never_listening(self):
        """빈 id 는 아무 명령줄에나 맞는다 — 전부 살아있음이 되면 판정이 죽는다."""
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertFalse(mod._inbox_watch_alive(""))


class TestPidAlive(unittest.TestCase):
    """S3. pid 생존이 `/proc/<pid>` 존재에만 기대지 않는다."""

    def test_s3_live_child_and_reaped_pid(self):
        p = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL)
        try:
            for name in BACKENDS:
                with self.subTest(backend=name), Backend(name):
                    self.assertTrue(mod.pid_alive(p.pid))
        finally:
            p.kill()
            p.wait(timeout=5)
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertFalse(mod.pid_alive(p.pid),
                                 f"{name}: 거둔 pid 가 살아있다고 나온다")

    def test_s3b_garbage_pid_is_false(self):
        for name in BACKENDS + ("none",):
            with self.subTest(backend=name), Backend(name):
                self.assertFalse(mod.pid_alive(0))
                self.assertFalse(mod.pid_alive(""))
                self.assertFalse(mod.pid_alive(None))
                self.assertFalse(mod.pid_alive("nope"))


class TestIsClaude(unittest.TestCase):
    """S4. pid 재사용 방어가 맥 갈래에서도 산다."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="s9plat-claude-", dir=TMP)
        cls.link = os.path.join(cls.dir, "claude")
        os.symlink(shutil.which("sleep") or "/bin/sleep", cls.link)
        cls.claude = subprocess.Popen([cls.link, "30"],
                                      stdin=subprocess.DEVNULL)
        cls.other = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL)
        for _ in range(200):
            mod.proc_cache_clear()
            if mod._pid_is_claude(cls.claude.pid):
                break
            time.sleep(0.02)

    @classmethod
    def tearDownClass(cls):
        for p in (cls.claude, cls.other):
            try:
                p.kill()
                p.wait(timeout=5)
            except Exception:
                pass
        mod.proc_cache_clear()

    def test_s4_claude_yes_other_no(self):
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertTrue(mod._pid_is_claude(self.claude.pid),
                                f"{name}: claude 프로세스를 못 알아본다")
                self.assertFalse(mod._pid_is_claude(self.other.pid),
                                 f"{name}: 아무 프로세스나 claude 로 읽는다")


class TestChatLive(unittest.TestCase):
    """S5. 채팅 생존 판정이 세 갈래 어디서도 같은 답을 낸다."""

    def _binding(self, **kw):
        tp = os.path.join(TMP, "live-transcript.jsonl")
        with open(tp, "w", encoding="utf-8") as f:
            f.write("{}\n")
        b = {"session": "zz999999", "ended": "", "attach_pid": "",
             "transcript_path": tp}
        b.update(kw)
        return b

    def test_s5_fresh_activity_is_live_everywhere(self):
        b = self._binding()
        for name in BACKENDS + ("none",):
            with self.subTest(backend=name), Backend(name):
                self.assertTrue(mod.chat_live(b))

    def test_s5b_attach_pid_alive_is_live_everywhere(self):
        """활동이 낡아도 attach 프로세스가 살아 있으면 live 다 — 맥에서
        `/proc/<pid>` 가 없어 이 갈래가 통째로 죽어 있었다."""
        old = os.path.join(TMP, "old-transcript.jsonl")
        with open(old, "w", encoding="utf-8") as f:
            f.write("{}\n")
        os.utime(old, (time.time() - 9999, time.time() - 9999))
        b = self._binding(transcript_path=old, attach_pid=str(os.getpid()))
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertTrue(mod.chat_live(b),
                                f"{name}: 산 attach pid 를 못 봤다")

    def test_s5c_ended_beats_everything(self):
        """끝난 세션은 어느 갈래에서도 되살아나지 않는다 (REQ-20260829-023 회귀)."""
        b = self._binding(ended="1", attach_pid=str(os.getpid()))
        for name in BACKENDS + ("none",):
            with self.subTest(backend=name), Backend(name):
                self.assertFalse(mod.chat_live(b))


class TestCache(unittest.TestCase):
    """S7. 폴 한 바퀴가 세션 수만큼 `ps` 를 포크하지 않는다."""

    def test_s7_ps_is_forked_once_within_ttl(self):
        with Backend("ps"):
            with mock.patch.object(mod, "_proc_table_read",
                                   wraps=mod._proc_table_read) as spy:
                for _ in range(5):
                    mod.proc_table()
                self.assertEqual(spy.call_count, 1,
                                 "ttl 안에서 프로세스 목록을 여러 번 읽었다")

    def test_s7b_clear_forces_a_reread(self):
        with Backend("ps"):
            with mock.patch.object(mod, "_proc_table_read",
                                   wraps=mod._proc_table_read) as spy:
                mod.proc_table()
                mod.proc_cache_clear()
                mod.proc_table()
                self.assertEqual(spy.call_count, 2)


class TestPortOwner(unittest.TestCase):
    """S9. 포트 주인 조회가 `/proc/net/tcp` 없이도 답한다."""

    def test_s9_listening_port_owner(self):
        # 임시 포트를 직접 뽑지 않는다 — WSL 에서 그 하나가 호스트 동적 포트를
        # 영구히 소모한다 (tests/portpool.py · test_port_pool 이 막는다).
        srv = portpool.pool_socket()
        srv.listen(4)
        port = srv.getsockname()[1]
        try:
            with Backend("proc"):
                self.assertEqual(mod._port_owner_pid(port), os.getpid())
            if shutil.which("lsof"):
                with Backend("ps"):
                    self.assertEqual(mod._port_owner_pid(port), os.getpid(),
                                     "lsof 갈래가 주인을 못 찾는다")
            with Backend("none"):
                self.assertEqual(mod._port_owner_pid(port), 0)
        finally:
            srv.close()

    def test_s9b_unowned_port_is_zero(self):
        for name in BACKENDS + ("none",):
            with self.subTest(backend=name), Backend(name):
                self.assertEqual(mod._port_owner_pid(0), 0)


def _hook(name, alias):
    """훅 하나를 모듈로 들인다 — 훅은 독립 실행 파일이라 판정을 로컬 복제한다."""
    path = os.path.join(HERE, "..", "bin", name)
    sp = importlib.util.spec_from_loader(
        alias, importlib.machinery.SourceFileLoader(alias, path))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


class TestHooksDoNotDrift(unittest.TestCase):
    """복제는 갈라진다 — 갈라지지 않는지를 여기서 못박는다.

    훅(`s9-audit-prompt`·`s9-audit-session`)은 s9 가 못 뜨는 상황에서도 돌아야
    해서 프로세스 판정을 로컬 복제한다. 맥에서 조용히 틀린 것이 정확히 그
    복제본들이었다: `attach_pid` 가 중간 셸의 pid 로 적혔고(둘 다), 수신 대기
    tail 이 안 보여 훅이 이미 전달된 줄을 한 번 더 주입했다(prompt).
    """

    @classmethod
    def setUpClass(cls):
        cls.prompt = _hook("s9-audit-prompt", "s9_hook_prompt")
        cls.session = _hook("s9-audit-session", "s9_hook_session")
        cls.sid = "ef56ab78"
        cls.tail = TailProc(cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.tail.kill()
        mod.proc_cache_clear()

    def test_h1_tail_alive_matches_s9(self):
        """훅의 수신 대기 판정이 s9 의 것과 **같은 답**을 낸다 — 두 갈래 모두."""
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                for probe in (self.sid, "00000000", ""):
                    self.assertEqual(
                        self.prompt._tail_alive(f"inbox-{probe}" if probe else ""),
                        mod._inbox_watch_alive(probe),
                        f"{name}/{probe!r}: 훅과 s9 의 답이 갈렸다")

    def test_h2_proc_info_agrees_across_backends(self):
        """조상 체인의 재료(실행 파일 이름·부모 pid)가 갈래마다 같아야
        `attach_pid` 가 맥에서도 진짜 claude 를 가리킨다."""
        seen = {}
        for name in BACKENDS:
            with Backend(name):
                for hook in (self.prompt, self.session):
                    comm, ppid = hook._proc_info(os.getpid())
                    self.assertEqual(ppid, os.getppid(),
                                     f"{name}: 부모 pid 가 틀리다")
                    self.assertTrue(comm, f"{name}: 실행 파일 이름이 비었다")
                    seen.setdefault(name, comm)
        self.assertEqual(len(set(seen.values())), 1,
                         f"갈래마다 다른 이름이 나온다: {seen}")

    def test_h3_claude_pid_never_returns_zero(self):
        """못 찾으면 getppid 로 물러난다 — 0 이나 예외로 끝나면 바인딩이 깨진다."""
        for name in BACKENDS + ("none",):
            with self.subTest(backend=name), Backend(name):
                for hook in (self.prompt, self.session):
                    self.assertGreater(hook._claude_pid(), 0)

    def test_h4_session_pid_alive_matches_s9(self):
        """이중 접속 경고가 보는 생존이 s9 의 생존과 같다."""
        p = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL)
        try:
            for name in BACKENDS:
                with self.subTest(backend=name), Backend(name):
                    self.assertEqual(self.session._pid_alive(p.pid),
                                     mod.pid_alive(p.pid))
        finally:
            p.kill()
            p.wait(timeout=5)
        for name in BACKENDS:
            with self.subTest(backend=name), Backend(name):
                self.assertEqual(self.session._pid_alive(p.pid),
                                 mod.pid_alive(p.pid))
                self.assertFalse(self.session._pid_alive(p.pid))


class TestDoctorLive(unittest.TestCase):
    """S8. 맥이 없는 자리에서 짐작하지 않으려면, 저쪽에서 한 번 돌려
    붙여 넣을 것이 있어야 한다."""

    def _run(self, *flags):
        env = dict(os.environ)
        env["S9_ROOT"] = TMP
        return subprocess.run([sys.executable, S9, "doctor", "--live", *flags],
                              capture_output=True, text=True, timeout=90,
                              env=env)

    def test_s8_json_names_the_branch(self):
        r = self._run("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertIn(d["backend"], ("proc", "ps", "none"))
        self.assertEqual(d["backend"], "proc")      # 이 기계는 리눅스다
        self.assertIn("os", d)
        self.assertIn("processes", d)
        self.assertGreater(d["processes"], 0)
        self.assertIn("sessions", d)
        self.assertIn("checks", d)
        keys = {c["key"] for c in d["checks"]}
        # 판정이 지나는 갈래마다 한 줄씩 — 어디서 끊겼는지 눈으로 보인다
        for want in ("backend", "self", "tail", "attach", "port"):
            self.assertIn(want, keys, f"{want} 갈래가 진단에 없다")

    def test_s8b_human_output_has_no_jargon_and_names_os(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("운영체제", out)
        self.assertIn("프로세스", out)
        for jargon in ("/proc", "backend", "None", "Traceback"):
            self.assertNotIn(jargon, out, f"내부 용어가 샜다: {jargon}\n{out}")
    def test_s8c_a_deaf_machine_shows_what_a_tail_looks_like_here(self):
        """듣고 있는 것이 0일 때가 **친구의 화면**이다.

        그때 "0개"만 말하면 다음 한 걸음이 또 짐작이 된다. 수신함 파일은
        있는가 · 이 기계에서 tail 이라는 것이 도는가 · 그 명령줄이 우리가
        찾는 모양인가 — 셋을 한 번에 보여 줘야 붙여 넣은 한 번으로 끝난다.
        """
        os.makedirs(os.path.join(TMP, "state", "terminal"), exist_ok=True)
        box = os.path.join(TMP, "state", "terminal", "inbox-deadbeef.jsonl")
        with open(box, "w", encoding="utf-8") as f:
            f.write("")
        self.addCleanup(os.unlink, box)
        env = dict(os.environ)
        env["S9_ROOT"] = TMP
        env["S9_PROC_BACKEND"] = "none"      # 프로세스를 못 보는 기계인 척
        r = subprocess.run([sys.executable, S9, "doctor", "--live"],
                           capture_output=True, text=True, timeout=90, env=env)
        self.assertEqual(r.returncode, 1, "볼 수 없는 기계는 1로 끝나야 한다")
        self.assertIn("수신함", r.stdout, "수신함이 있는지를 안 말한다")
        self.assertIn("deadbeef", r.stdout, "어느 수신함인지를 안 말한다")
        self.assertIn("tail", r.stdout,
                      "이 기계에서 tail 이 어떤 모양인지를 안 보여 준다 — "
                      "그러면 다음 한 걸음이 또 짐작이 된다")
        d = json.loads(subprocess.run(
            [sys.executable, S9, "doctor", "--live", "--json"],
            capture_output=True, text=True, timeout=90, env=env).stdout)
        self.assertIn("deadbeef", d["inboxes"])
        self.assertIn("tails", d, "기계 판독용에도 증거가 실려야 한다")


if __name__ == "__main__":
    unittest.main()
