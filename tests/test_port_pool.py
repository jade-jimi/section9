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

실행: python3 tests/ port_pool
"""
import os
import re
import socket
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
        """스위트를 반복 실행해도 새 포트 번호가 늘지 않는다(중계 누수 상한 고정)."""
        first = {portpool.free_port() for _ in range(portpool.POOL_SIZE)}
        second = {portpool.free_port() for _ in range(portpool.POOL_SIZE)}
        self.assertEqual(first, second)

    def test_allocated_port_is_usable(self):
        port = portpool.free_port()
        srv = socket.socket()
        try:
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            socket.create_connection(("127.0.0.1", port), 3).close()
        finally:
            srv.close()

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


if __name__ == "__main__":
    unittest.main()
