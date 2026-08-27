"""테스트 네트워크 규율 테스트 — 고갈을 만들지 않는다 (REQ-20260825-100).

감지(`s9 doctor`)와 회수(`--recover`)는 불이 난 뒤에 쓰는 소화기다. 불씨는
우리가 여는 커넥션 수다 — 실측으로 리눅스 localhost 커넥션 30개가 윈도우
Bound 소켓 +30 을 만들었다(리스너를 새로 공개하는 건 +0~1, 윈도우에서
WSL 로 들어오는 요청은 +0). portpool 모듈 머리말에 측정표가 있다.

여기서 고정하는 것:
1) 서버 대기가 지수 백오프다 — 40초를 기다려도 시도는 30회 이하. 예전
   400회 루프는 호스트가 마르는 순간 고갈을 가속하는 되먹임이었다.
2) 풀이 윈도우 동적 범위·커널 임시 범위 **밖**에 있고, 몇 번을 할당하든
   서로 다른 포트 번호가 풀 크기를 넘지 않는다.
3) 소스 규율 — 임시 포트 직접 bind 금지, 촘촘한 재시도 루프 금지.
4) 사용자 대시보드 포트(9909~9950)를 테스트가 물지 않는다 — 물면 사람이 보는
   화면이 404 나 **옛 화면**으로 바뀐다(REQ-20260828-001).

실행: python3 tests/ port_pool
"""
import os
import re
import socket
import tempfile
import time
import unittest

import portpool

HERE = os.path.dirname(os.path.abspath(__file__))


class PoolRange(unittest.TestCase):
    def test_below_windows_dynamic_range(self):
        """풀 전체가 윈도우 동적 범위 아래여야 한다 — 여기가 마르면 망이 끊긴다."""
        ports = portpool.pool_ports()
        self.assertLess(max(ports), portpool.WIN_DYNAMIC_START,
                        "풀이 윈도우 동적 포트 범위를 침범한다")

    def test_outside_kernel_ephemeral_range(self):
        """커널이 아웃바운드 연결에 나눠주는 범위와 겹치면 무작위로 충돌한다."""
        lo, hi = portpool.ephemeral_range()
        ports = portpool.pool_ports()
        self.assertTrue(max(ports) < lo or min(ports) > hi,
                        f"풀 {min(ports)}~{max(ports)} 이 임시 범위 {lo}~{hi} 와 겹친다")

    def test_avoids_dashboard_ports(self):
        """대시보드 기본 포트와 그 스캔 대역(9909~9950)은 피한다."""
        ports = set(portpool.pool_ports())
        self.assertFalse(ports & set(range(9909, 9951)))


class BoundedReuse(unittest.TestCase):
    def test_distinct_ports_are_capped(self):
        """할당을 몇 번 하든 서로 다른 포트 수는 풀 크기 이하."""
        seen = {portpool.free_port() for _ in range(portpool.POOL_SIZE * 5)}
        self.assertLessEqual(len(seen), portpool.POOL_SIZE)
        self.assertTrue(seen <= set(portpool.pool_ports()))

    def test_repeated_runs_reuse_the_same_ports(self):
        """반복 할당은 같은 구간을 돌려쓴다 — 쓰는 포트 번호가 계속 늘지 않는다.

        (정확히 같은 집합을 요구하지는 않는다 — 다른 테스트의 서버가 잠깐
        한 칸을 쥐고 있으면 그 회차만 건너뛰기 때문이다. 고정하려는 성질은
        '구간 밖으로 새지 않는다'와 '총량이 슬롯 크기 이하다' 두 가지다.)
        """
        slot = set(portpool.slot_ports())
        first = {portpool.free_port() for _ in range(portpool.SLOT_SIZE * 2)}
        second = {portpool.free_port() for _ in range(portpool.SLOT_SIZE * 2)}
        self.assertTrue(first <= slot, first - slot)
        self.assertTrue(second <= slot, second - slot)
        self.assertLessEqual(len(first | second), portpool.SLOT_SIZE)

    def test_allocated_port_is_usable(self):
        port = portpool.free_port()
        srv = socket.socket()
        try:
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            socket.create_connection(("127.0.0.1", port), 3).close()
        finally:
            srv.close()

    def test_time_wait_port_is_still_allocatable(self):
        """요청을 처리하고 내려간 서버의 포트는 60초쯤 TIME_WAIT 로 남는다.

        그걸 '사용 중'으로 판정하면 방금 쓴 칸이 1분간 죽고 풀이 헛되이 마른다
        (실제로 test_whoami 가 '풀 소진'으로 깨졌다). 실서버(HTTPServer)는
        allow_reuse_address 로 그 포트를 다시 잡으므로 판정도 같아야 한다.
        """
        srv = portpool.pool_socket()
        port = srv.getsockname()[1]
        c = socket.create_connection(("127.0.0.1", port), 3)
        a, _peer = srv.accept()
        a.close()          # 서버가 먼저 닫는다 → 서버 쪽 포트가 TIME_WAIT
        c.close()
        srv.close()
        s = portpool._try_bind(port)
        self.assertIsNotNone(s, f"TIME_WAIT 인 {port} 를 다시 잡지 못한다")
        s.close()

    def test_pool_socket_holds_the_port(self):
        a = portpool.pool_socket()
        b = portpool.pool_socket()
        try:
            self.assertNotEqual(a.getsockname()[1], b.getsockname()[1])
        finally:
            a.close()
            b.close()

    def test_exhausted_pool_says_what_to_do(self):
        """다 찼으면 임시 포트로 몰래 도망가지 말고 회수를 안내하며 실패한다."""
        base = portpool.free_port()          # 지금 비어 있는 한 칸
        held = portpool.pool_socket(base=base, size=1)
        try:
            with self.assertRaises(RuntimeError) as cm:
                portpool.free_port(base=base, size=1)
            self.assertIn("doctor", str(cm.exception))
        finally:
            held.close()


class WaitBackoff(unittest.TestCase):
    """서버 대기는 '시도 횟수'가 비용이다 — 커넥션 1개 = 호스트 동적 포트 1개."""

    def test_gives_up_after_few_attempts(self):
        """40초를 기다리더라도 두드리는 횟수는 30회 이하 — 예전엔 400회였다."""
        calls = []

        def never():
            calls.append(1)
            raise OSError("refused")

        t0 = time.monotonic()
        with self.assertRaises(RuntimeError):
            portpool.wait_server(1, timeout=3.0, _connect=never)
        elapsed = time.monotonic() - t0
        self.assertGreaterEqual(elapsed, 2.9)      # 대기 시간은 줄이지 않는다
        self.assertLessEqual(len(calls), 12, f"{len(calls)}회 시도 — 너무 자주 두드린다")

    def test_full_timeout_stays_under_thirty_attempts(self):
        """기본 40초 대기의 시도 횟수 상한(수식으로 계산 — 실제로 기다리지 않는다)."""
        n, t, delay = 0, 0.0, portpool.WAIT_FIRST
        while t < portpool.WAIT_TIMEOUT:
            n += 1
            t += delay
            delay = min(delay * portpool.WAIT_GROWTH, portpool.WAIT_MAX)
        self.assertLessEqual(n, 30)

    def test_returns_attempt_count_on_success(self):
        seq = [OSError, OSError, None]

        def flaky():
            x = seq.pop(0)
            if x:
                raise x("refused")

        self.assertEqual(portpool.wait_server(1, timeout=5, _connect=flaky), 3)

    def test_http_server_answers_on_first_try(self):
        """진짜 HTTP 서버는 첫 시도에 준비됨으로 잡힌다."""
        import http.server
        import threading
        s = portpool.pool_socket()
        port = s.getsockname()[1]
        s.close()
        srv = http.server.HTTPServer(
            ("127.0.0.1", port), http.server.SimpleHTTPRequestHandler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            self.assertEqual(portpool.wait_server(port, timeout=10), 1)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_bare_listener_is_not_ready(self):
        """**연결됨 ≠ 준비됨.** 듣기만 하고 응답하지 않는 소켓은 준비된 게 아니다.

        WSL virtioproxy 는 리스너가 없어도 connect 를 받아준다 — connect 만으로
        판정하면 서버가 뜨기 전에 통과하고, 뒤이은 요청이 ConnectionReset 으로
        깨진다. 아무 응답도 주지 않는 리스너로 그 판정을 재현한다."""
        s = portpool.pool_socket()
        try:
            with self.assertRaises(RuntimeError):
                portpool.wait_server(s.getsockname()[1], timeout=3)
        finally:
            s.close()


class NoEphemeralBind(unittest.TestCase):
    """테스트가 임시 포트를 직접 뽑는 습관으로 돌아가지 못하게 막는다."""

    EPHEMERAL_BIND = re.compile(r"\.bind\(\(\s*[\"'][^\"']*[\"']\s*,\s*0\s*\)\)")

    def test_no_test_file_binds_an_ephemeral_port(self):
        offenders = []
        for name in sorted(os.listdir(HERE)):
            if not name.startswith("test_") or not name.endswith(".py"):
                continue
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if self.EPHEMERAL_BIND.search(line):
                        offenders.append(f"{name}:{i}")
        self.assertEqual(offenders, [], "portpool.free_port() 를 써라 — "
                         "임시 포트 bind 는 윈도우 동적 포트를 영구히 소모한다: "
                         + ", ".join(offenders))

    def test_no_tight_retry_loop(self):
        """서버 기동을 촘촘히 두드리는 루프 금지 — 고갈 중일 때 고갈을 가속한다."""
        offenders = []
        for name in sorted(os.listdir(HERE)):
            if not name.startswith("test_") or not name.endswith(".py"):
                continue
            src = open(os.path.join(HERE, name), encoding="utf-8").read()
            for m in re.finditer(r"for\s+\w+\s+in\s+range\((\d+)\)", src):
                if int(m.group(1)) >= 50 and "create_connection" in src:
                    offenders.append(f"{name}:range({m.group(1)})")
        self.assertEqual(offenders, [], "wait_server() 를 써라 — "
                         "연결 시도 1회가 호스트 동적 포트 1개다: " + ", ".join(offenders))

    def test_server_tests_use_the_pool(self):
        """서버를 띄우는 테스트는 풀에서 포트를 받아야 한다."""
        missing = []
        for name in sorted(os.listdir(HERE)):
            if not name.startswith("test_") or not name.endswith(".py"):
                continue
            src = open(os.path.join(HERE, name), encoding="utf-8").read()
            if "free_port(" not in src and "pool_socket(" not in src:
                continue
            if "import portpool" not in src and "from portpool import" not in src:
                missing.append(name)
        self.assertEqual(missing, [])


class StrayDashboardServers(unittest.TestCase):
    """테스트가 **사용자 대시보드 포트**를 물지 않는다 (REQ-20260828-001).

    2026-08-28: 스위트가 끝난 뒤에도 `/tmp/s9smx-*` 작업공간의 `s9 serve` 가
    9909 를 물고 살아남았다. 진짜 서버와 번갈아 응답해 새로고침마다 404 가
    났고, 더 나쁘게는 **테스트 시작 시점의 옛 web/index.html** 을 내줘 화면을
    고치고 눈으로 확인하는 절차를 조용히 통과시켰다.
    """

    REPO = os.path.dirname(HERE)
    TMP = tempfile.gettempdir()

    def proc(self, **kw):
        base = {"pid": 4242, "argv": ["/repo/bin/s9", "serve", "--port", "9909"],
                "cwd": "", "root": ""}
        base.update(kw)
        return base

    # ---------- 무엇을 거두고 무엇을 남기는가 ----------

    def test_temp_workspace_on_dashboard_port_is_stray(self):
        p = self.proc(root=os.path.join(self.TMP, "s9smx-abcd"))
        self.assertTrue(portpool.is_stray_dashboard_server(p))

    def test_cwd_alone_is_enough_to_recognize(self):
        """S9_ROOT 를 못 읽어도 작업 디렉토리로 알아본다 — 사람이 쓴 방법과 같다."""
        p = self.proc(cwd=os.path.join(self.TMP, "s9smx-abcd"))
        self.assertTrue(portpool.is_stray_dashboard_server(p))

    def test_real_server_is_never_touched(self):
        """진짜 서버(작업공간=저장소)는 절대 회수 대상이 아니다."""
        p = self.proc(cwd=self.REPO, root=self.REPO)
        self.assertFalse(portpool.is_stray_dashboard_server(p))

    def test_pool_port_test_server_is_left_alone(self):
        """풀 포트를 쓰는 정상적인 테스트 서버는 남의 몫이다(s9-doctor --sweep).

        여기서 거두면 **동시에 도는 다른 스위트**의 서버를 죽인다.
        """
        p = self.proc(argv=["/repo/bin/s9", "serve", "--port",
                            str(portpool.POOL_BASE)],
                      root=os.path.join(self.TMP, "s9guardp-x"))
        self.assertFalse(portpool.is_stray_dashboard_server(p))

    def test_scan_band_counts_too(self):
        """9909 하나가 아니라 스캔 대역 전체가 사용자 자리다."""
        p = self.proc(argv=["/repo/bin/s9", "serve", "--port", "9931"],
                      root=os.path.join(self.TMP, "s9smx-abcd"))
        self.assertTrue(portpool.is_stray_dashboard_server(p))

    def test_other_programs_are_not_ours(self):
        p = self.proc(argv=["python3", "-m", "http.server", "--port", "9909"],
                      root=os.path.join(self.TMP, "x"))
        self.assertFalse(portpool.is_stray_dashboard_server(p))

    def test_port_flag_forms(self):
        self.assertEqual(portpool._argv_port(["s9", "serve", "--port=9909"]), 9909)
        self.assertEqual(portpool._argv_port(["s9", "serve", "--port", "9909"]), 9909)
        self.assertIsNone(portpool._argv_port(["s9", "serve"]))

    # ---------- 거두는 방식 ----------

    def test_guard_dies_before_its_child(self):
        """감시자를 먼저 죽여야 한다 — 자식만 죽이면 곧바로 되살아난다."""
        tmp = os.path.join(self.TMP, "s9smx-abcd")
        child = self.proc(pid=101, root=tmp)
        guard = self.proc(pid=100, root=tmp,
                          argv=["/repo/bin/s9", "serve", "--supervise",
                                "--port", "9909"])
        killed = []
        rounds = [[child, guard], []]
        portpool.reap_stray_dashboard_servers(
            snapshot=lambda: rounds.pop(0) if rounds else [],
            kill=lambda pid, sig: killed.append(pid),
            sleep=lambda _s: None)
        self.assertEqual(killed, [100, 101])

    def test_reap_retries_until_gone(self):
        """한 바퀴로 안 죽으면 다시 본다 — 되살아난 자식을 놓치지 않는다."""
        tmp = os.path.join(self.TMP, "s9smx-abcd")
        alive = [[self.proc(pid=1)], [self.proc(pid=2)], []]
        for p in (alive[0][0], alive[1][0]):
            p["root"] = tmp
        killed = []
        reaped = portpool.reap_stray_dashboard_servers(
            snapshot=lambda: alive.pop(0) if alive else [],
            kill=lambda pid, sig: killed.append(pid),
            sleep=lambda _s: None)
        self.assertEqual(killed, [1, 2])
        self.assertEqual([p["pid"] for p in reaped], [1, 2])

    def test_nothing_to_reap_is_silent(self):
        self.assertEqual(portpool.reap_stray_dashboard_servers(
            snapshot=lambda: [], kill=None, sleep=lambda _s: None), [])

    def test_runner_reaps_and_fails(self):
        """러너가 회수를 부르고, 남은 게 있으면 실패로 센다 — 조용히 치우면
        다음 실행에서 또 생긴다."""
        src = open(os.path.join(HERE, "__main__.py"), encoding="utf-8").read()
        self.assertIn("reap_stray_dashboard_servers", src,
                      "러너가 스위트 뒤에 포트를 거두지 않는다")
        self.assertIn("return 1", src.split("leaked")[-1][:400],
                      "포트를 뺏은 채 끝났는데 성공으로 끝난다")

    # ---------- 소스 규율 ----------

    HOOK_RUN = re.compile(
        r"(?:run|Popen)\(\s*\[[^\]]*(?:SESSION_HOOK|\bHOOK\b|hook|"
        r"\"s9-audit-session\")", re.S)

    def test_session_hook_tests_isolate_the_port(self):
        """세션 훅을 돌리는 테스트는 S9_PORT 로 격리해야 한다.

        훅의 `ensure_serve()` 는 S9_PORT 가 없으면 `state/port` → 9909 로
        떨어진다. 임시 작업공간에는 그 파일이 없으니 **사용자 포트**에
        감시자를 세운다. 이 검사가 없으면 다음 테스트가 같은 자리에 빠진다.
        """
        offenders = []
        for name in sorted(os.listdir(HERE)):
            if not name.startswith("test_") or not name.endswith(".py"):
                continue
            src = open(os.path.join(HERE, name), encoding="utf-8").read()
            if "s9-audit-session" not in src:
                continue
            if not self.HOOK_RUN.search(src):
                continue          # 소스만 읽는 테스트 — 훅을 돌리지 않는다
            # 주석에 이름만 적어 두는 것으로는 격리가 되지 않는다 —
            # env 에 실제로 들어간 형태(따옴표로 감싼 키)를 본다.
            if not re.search(r"[\"']S9_PORT[\"']", src):
                offenders.append(name)
        self.assertEqual(offenders, [],
                         "세션 훅을 돌리면서 포트를 격리하지 않는다 — "
                         "S9_PORT='1' 을 env 에 넣어라: " + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
