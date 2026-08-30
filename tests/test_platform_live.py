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
        self.assertIn(d["backend"], ("proc", "ps", "win", "none"))
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

    def test_s8d_a_branch_that_sees_nothing_is_not_a_success(self):
        """갈래 이름이 붙었다는 것과 그 갈래가 실제로 무엇을 봤다는 것은 다른
        일이다. 조회 도구가 없는 기계에서 `win` 갈래는 이름은 서지만 목록이
        빈다 — 거기서 ✓ 와 0 을 내면 아무것도 못 보는 기계가 스스로 멀쩡하다고
        말하게 되고, 이 진단이 있는 이유가 사라진다."""
        env = dict(os.environ)
        env["S9_ROOT"] = TMP
        env["S9_PROC_BACKEND"] = "win"    # 이 기계에 PowerShell 은 없다
        r = subprocess.run([sys.executable, S9, "doctor", "--live"],
                           capture_output=True, text=True, timeout=90, env=env)
        self.assertEqual(r.returncode, 1,
                         "아무것도 못 본 기계가 0 으로 끝났다")
        self.assertIn("✗", r.stdout, "못 본다는 표시가 없다")
        d = json.loads(subprocess.run(
            [sys.executable, S9, "doctor", "--live", "--json"],
            capture_output=True, text=True, timeout=90, env=env).stdout)
        self.assertEqual(d["backend"], "win")
        self.assertTrue(d["blind"])
        self.assertEqual(d["processes"], 0)

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



# ── 윈도우 갈래 ────────────────────────────────────────────────────────────
# 이 REQ 의 목표는 "맥·윈도우·리눅스 어디서든" 이다. 맥을 고치면서 문을 하나로
# 모았지만 그 문 안에 윈도우 갈래가 없었다: 네이티브 윈도우에는 `/proc` 도
# `ps` 도 없어 `proc_backend()` 가 `none` 으로 떨어지고, 그러면 대화가 되는
# 세션도 영원히 `idle` 이다 — **맥과 같은 결함이 자리만 옮긴 것**이다.
# (`bin/s9.cmd`·`bin/s9-install.cmd` 가 있는 이상 그 자리는 가상이 아니다.)
#
# 윈도우가 이 자리에 없으므로 맥과 같은 방법을 쓴다: 갈래를 강제하고 그
# 기계의 조회 출력을 **가짜로 세워** 넣은 뒤, 리눅스에서 돌던 것과 같은 답이
# 나오는지를 본다. "윈도우에서 된다"의 증명이 아니라 "윈도우라면 어느 길로
# 가고 그 길이 답을 내는가"의 못박음이다.

def win_lines(table, ppid=1):
    """{pid: 명령줄} → PowerShell 조회가 내는 모양 (`pid ppid 명령줄`)."""
    return [f"{pid} {ppid} {cmd}" for pid, cmd in table.items()]


class FakeWin:
    """`_ps_lines` 를 가로채 윈도우 조회 출력을 흉내 낸다.

    가로채는 것은 **명령을 띄우는 한 줄**뿐이다 — 파싱도 판정도 진짜 코드가
    그대로 돈다. 그래야 이 시험이 '윈도우 갈래가 답을 내는가'를 재게 된다.
    """

    def __init__(self, ps_out=(), wmic_out=(), netstat_out=()):
        self.ps_out, self.wmic_out = list(ps_out), list(wmic_out)
        self.netstat_out = list(netstat_out)
        self.seen = []

    def __call__(self, argv, timeout=10):
        argv = list(argv)
        self.seen.append(argv)
        head = os.path.basename(argv[0]).lower()
        if "powershell" in head or "pwsh" in head:
            return self.ps_out
        if head.startswith("wmic"):
            return self.wmic_out
        if head.startswith("netstat"):
            return self.netstat_out
        return []

    def __enter__(self):
        self.ctx = mock.patch.object(mod, "_ps_lines", self)
        self.ctx.start()
        return self

    def __exit__(self, *a):
        self.ctx.stop()
        return False


class TestWindowsBackend(unittest.TestCase):
    """W1~W7. 윈도우 갈래가 리눅스 갈래와 **같은 답**을 낸다."""

    @classmethod
    def setUpClass(cls):
        cls.sid = "cc90ff21"
        cls.tail = TailProc(cls.sid)
        mod.proc_cache_clear()
        cls.real = dict(mod.proc_table())      # 진짜 목록 = 가짜 조회의 재료

    @classmethod
    def tearDownClass(cls):
        cls.tail.kill()
        mod.proc_cache_clear()

    def test_w1_backend_name_is_forceable(self):
        """`win` 이 강제할 수 있는 이름이어야 이 자리에서 시험할 수 있다."""
        with Backend("win"):
            self.assertEqual(mod.proc_backend(), "win")

    def test_w2_listening_matches_the_linux_answer(self):
        """이 REQ 의 본체가 윈도우 자리로 옮겨온 것 — 수신 대기 판정이
        `/proc` 갈래와 같은 답을 낸다."""
        with Backend("proc"):
            want = {p: mod._inbox_watch_alive(p)
                    for p in (self.sid, "00000000", "")}
        self.assertTrue(want[self.sid], "이 기계에서 tail 이 안 잡혔다")
        with Backend("win"), FakeWin(ps_out=win_lines(self.real)):
            for probe, exp in want.items():
                self.assertEqual(mod._inbox_watch_alive(probe), exp,
                                 f"{probe!r}: 윈도우 갈래가 다른 답을 냈다")

    def test_w3_pid_alive_never_calls_os_kill(self):
        """윈도우 파이썬의 `os.kill` 은 시그널 0 에도 프로세스를 **죽인다**.
        목록으로만 답해야 한다 — 여기서 죽이면 사용자의 세션이 죽는다."""
        with Backend("win"), FakeWin(ps_out=win_lines(self.real)), \
                mock.patch.object(os, "kill",
                                  side_effect=AssertionError("os.kill 호출")):
            self.assertTrue(mod.pid_alive(os.getpid()))
            self.assertFalse(mod.pid_alive(max(self.real) + 900000))
            self.assertFalse(mod.pid_alive(0))
            self.assertFalse(mod.pid_alive("x"))

    def test_w4_ppid_comes_from_the_same_lookup(self):
        """부모 pid 를 따로 묻지 않는다 — 조상 체인을 열 걸음 올라갈 때마다
        프로세스를 띄우면 프롬프트마다 도는 훅이 못 쓰게 느려진다."""
        fake = FakeWin(ps_out=[f"{os.getpid()} {os.getppid()} python3 x"])
        with Backend("win"), fake:
            self.assertEqual(mod.pid_ppid(os.getpid()), os.getppid())
            self.assertEqual(mod.pid_ppid(max(self.real) + 900000), 0)
        self.assertEqual(len(fake.seen), 1,
                         f"조회를 여러 번 띄웠다: {fake.seen}")

    def test_w5_wmic_fallback_keeps_commas_in_the_command_line(self):
        """PowerShell 이 없는 옛 기계는 wmic 다. csv 인데 명령줄 안에 쉼표가
        있으므로 **양 끝에서** 잘라야 명령줄이 잘리지 않는다 — 잘리면
        수신함 이름이 사라져 판정이 조용히 거짓이 된다."""
        cmd = f'tail -c +1 -f C:\\s9\\state\\terminal\\inbox-{self.sid}.jsonl,x'
        wmic = ["Node,CommandLine,ParentProcessId,ProcessId",
                f"BOX,{cmd},44,77"]
        with Backend("win"), FakeWin(ps_out=[], wmic_out=wmic):
            self.assertEqual(mod.proc_table().get(77), cmd)
            self.assertTrue(mod._inbox_watch_alive(self.sid))
            self.assertEqual(mod.pid_ppid(77), 44)

    def test_w6_exe_name_survives_quotes_and_backslashes(self):
        """`"C:\Program Files\nodejs\node.exe" x` 의 이름은 `node.exe` 다.
        공백으로만 자르면 `"C:\Program` 이 되어 claude 판정이 통째로 어긋난다."""
        line = '901 1 "C:\\Program Files\\nodejs\\node.exe" --y cli.js'
        with Backend("win"), FakeWin(ps_out=[line]):
            self.assertEqual(mod.pid_comm(901), "node.exe")
        with Backend("win"), FakeWin(ps_out=["902 1 C:\\bin\\tail.exe -f a"]):
            self.assertEqual(mod.pid_comm(902), "tail.exe")

    def test_w7_port_owner_reads_netstat_in_any_language(self):
        """`netstat` 의 상태 낱말은 언어팩을 탄다(한국어는 "수신 대기" —
        공백까지 있어 열 수가 달라진다). 낱말이 아니라 상대 주소가 `:0` 인
        것으로 갈라야 어느 나라 윈도우에서도 답이 나온다."""
        rows = ["  TCP    0.0.0.0:9909     0.0.0.0:0     수신 대기      4321",
                "  TCP    127.0.0.1:9909   127.0.0.1:5511  ESTABLISHED  9999"]
        with Backend("win"), FakeWin(netstat_out=rows):
            self.assertEqual(mod._port_owner_pid(9909), 4321)
            self.assertEqual(mod._port_owner_pid(7000), 0)
            self.assertEqual(mod._port_owner_pid(0), 0)

    def test_w8_unknown_env_is_blank_not_a_guess(self):
        """윈도우 조회는 환경을 주지 않는다. 모르는 것은 모른다고 해야
        계정 표시가 조용히 틀리지 않는다 — 그리고 없는 `ps` 를 부르지 않는다."""
        fake = FakeWin(ps_out=win_lines(self.real))
        with Backend("win"), fake:
            self.assertEqual(mod.pid_env(os.getpid(), "HOME"), "")
            self.assertEqual(mod.proc_env_table(), {})
        self.assertFalse([a for a in fake.seen
                          if os.path.basename(a[0]) == "ps"],
                         "윈도우에서 `ps` 를 불렀다")

    def test_w9b_exe_suffix_does_not_hide_claude(self):
        """윈도우의 실행 파일 이름에는 `.exe` 가 붙는다. 그대로 견주면
        `node.exe` 가 런타임 목록에 안 걸려 **아무것도 claude 로 안 잡힌다**
        — attach pid 재사용 방어가 늘 거짓을 내고, 조상 체인이 중간 셸에서
        멈춰 그 셸의 pid 가 `attach_pid` 로 적힌다."""
        lines = ['700 1 "C:\\Program Files\\nodejs\\node.exe" cli.js claude',
                 "701 1 C:\\Windows\\System32\\notepad.exe",
                 "702 1 C:\\bin\\claude.exe --resume"]
        with Backend("win"), FakeWin(ps_out=lines):
            self.assertTrue(mod._pid_is_claude(700))
            self.assertTrue(mod._pid_is_claude(702))
            self.assertFalse(mod._pid_is_claude(701), "아무거나 claude 가 됐다")
        self.assertEqual(mod.exe_name("node.exe"), "node")
        self.assertEqual(mod.exe_name("node"), "node")

    def test_w9_empty_lookup_is_false_not_crash(self):
        """조회가 아무것도 못 냈을 때(권한·정책) 판정은 거짓으로 떨어지고
        프로그램은 산다. 대시보드 폴 한 바퀴가 예외로 멎으면 화면이 죽는다."""
        with Backend("win"), FakeWin():
            self.assertEqual(mod.proc_table(), {})
            self.assertFalse(mod._inbox_watch_alive(self.sid))
            self.assertFalse(mod.pid_alive(os.getpid()))
            self.assertEqual(mod.pid_cmdline(os.getpid()), "")
            self.assertEqual(mod.pid_comm(os.getpid()), "")


class TestWindowsHooksDoNotDrift(unittest.TestCase):
    """W10~W11. 훅의 복제본에도 같은 갈래가 있어야 한다 — 없으면 윈도우에서
    `attach_pid` 가 중간 셸로 적히고(맥에서 났던 그 사고), 이미 전달된 줄을
    훅이 한 번 더 주입한다."""

    @classmethod
    def setUpClass(cls):
        cls.prompt = _hook("s9-audit-prompt", "s9_hook_prompt_win")
        cls.session = _hook("s9-audit-session", "s9_hook_session_win")

    def _fake(self, hook, lines):
        """훅은 `subprocess.run` 을 직접 부른다 — 거기만 가로챈다."""
        hook._WIN_ROWS.clear()
        hook._WIN_READ[0] = False
        self.addCleanup(lambda: (hook._WIN_ROWS.clear(),
                                 hook._WIN_READ.__setitem__(0, False)))
        return mock.patch.object(
            hook.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout="\n".join(lines), stderr=""))

    def test_w10_hook_tail_alive_matches_s9(self):
        sid = "b71c0d92"
        cmd = f"tail -c +1 -f C:\\s9\\state\\terminal\\inbox-{sid}.jsonl"
        lines = [f"500 1 {cmd}", "501 1 C:\\Windows\\explorer.exe"]
        with Backend("win"), self._fake(self.prompt, lines), \
                FakeWin(ps_out=lines):
            self.assertTrue(self.prompt._tail_alive(f"inbox-{sid}"))
            self.assertEqual(self.prompt._tail_alive(f"inbox-{sid}"),
                             mod._inbox_watch_alive(sid))
            self.assertFalse(self.prompt._tail_alive("inbox-00000000"))
            self.assertFalse(self.prompt._tail_alive(""))

    def test_w11_hook_proc_info_and_alive_match_s9(self):
        lines = ['700 1 "C:\\Program Files\\nodejs\\node.exe" cli.js',
                 "800 700 C:\\Windows\\System32\\cmd.exe /c hook"]
        for hook in (self.prompt, self.session):
            with self.subTest(hook=hook.__name__), Backend("win"), \
                    self._fake(hook, lines), FakeWin(ps_out=lines):
                self.assertEqual(hook._proc_info(800), ("cmd.exe", 700))
                self.assertEqual(hook._proc_info(700), ("node.exe", 1))
                self.assertEqual(hook._proc_info(999), ("", 0))
                self.assertEqual(hook._proc_info(700)[0], mod.pid_comm(700))
                self.assertEqual(hook._proc_info(800)[1], mod.pid_ppid(800))
        with Backend("win"), self._fake(self.session, lines), \
                FakeWin(ps_out=lines):
            self.assertTrue(self.session._pid_alive(700))
            self.assertFalse(self.session._pid_alive(999))
            self.assertEqual(self.session._pid_alive(700), mod.pid_alive(700))

    def test_w12_hook_claude_pid_walks_the_chain_on_windows(self):
        """조상 체인이 윈도우에서도 걸어 올라가야 `attach_pid` 가 진짜
        claude 를 가리킨다 — 못 찾으면 0 이 아니라 getppid 로 물러난다."""
        lines = [f'700 1 "C:\\Program Files\\nodejs\\node.exe" cli.js',
                 f"800 700 C:\\Windows\\System32\\cmd.exe /c hook",
                 f"{os.getpid()} 800 python3 hook"]
        for hook in (self.prompt, self.session):
            with self.subTest(hook=hook.__name__), Backend("win"), \
                    self._fake(hook, lines):
                with mock.patch.object(os, "getppid", return_value=800):
                    self.assertEqual(hook._claude_pid(), 700)
            with self.subTest(hook=hook.__name__, case="빈 조회"), \
                    Backend("win"), self._fake(hook, []):
                self.assertGreater(hook._claude_pid(), 0)


if __name__ == "__main__":
    unittest.main()
