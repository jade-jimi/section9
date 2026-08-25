"""테스트의 네트워크 규율 — 호스트 동적 포트 고갈을 만들지 않는다 (REQ-20260825-100).

## 무엇이 실제로 포트를 먹는가 (2026-08-26 실측, 이 머신 / WSL virtioproxy)

`s9 doctor` 가 세는 윈도우 Bound 소켓을 기준으로 하나씩 갈라 재봤다.

| 행동                                   | Bound 증가 |
|----------------------------------------|-----------|
| 리눅스에서 localhost 로 TCP 연결 30개  | **+30** (3회 재현) |
| 리스너 10개를 2초씩 공개(포트 새로 씀) | +1        |
| 순간 bind/listen/close 200회           | +0        |
| 윈도우(curl.exe) → WSL 짧은 요청 30개  | +0        |
| WSL → 외부 인터넷 연결 50개            | +0        |
| 아무것도 안 함 30~90초                 | -13 ~ +13 |

(오래 붙들고 있는 연결 — 대시보드 SSE, 고아 헤드리스 브라우저 — 은 이 표와
다른 경로다. 그쪽은 REQ-20260826-002 에서 다룬다.)

즉 **비용은 포트 번호가 아니라 "우리가 여는 localhost 커넥션 수"** 다.
커넥션 하나당 WSL 중계(DllHost COM 대리)가 윈도우 동적 포트 하나를 잡는다.
측정 시점의 점유도 그 모습이었다 — Bound 555개 중 541개가 그 중계 프로세스,
전부 동적 범위(49152~)의 서로 다른 포트. 다만 영구 누수는 아니다: 몇 분 뒤
수백 개가 한꺼번에 반환되는 것도 관측했다. 여는 속도가 반환 속도를 오래
넘어서면 16,384개가 마르고, 그때 나오는 게 2026-08-25 사고다(96% 점유,
브라우저 ERR_NO_BUFFER_SPACE, 테스트 29건 connection refused).

## 그래서 규율 두 가지

1. **두드리는 횟수를 아낀다** — `wait_server()` 의 지수 백오프. 예전 대기
   루프는 0.1초 간격 400회였다. 호스트가 말라 공개가 늦어지는 바로 그때
   파일마다 400회씩 두드려 고갈을 가속했다(스위트 14파일 = 최대 5,600
   커넥션). 고장이 부하를 키우는 되먹임을 끊는 것이 첫째다.
2. **포트는 고정 풀에서 돌려쓴다** — 윈도우 동적 범위(49152~)와 커널 임시
   범위(32768~) **아래**의 64개(18800~18863). 리스너를 동적 범위 안에 두면
   중계가 쓰려던 포트와 부딪히고, 임시 범위 안에 두면 남의 아웃바운드 연결과
   부딪힌다. 번호가 예측 가능해야 고아 서버 회수도 쉽다.

두 규율 모두 tests/test_port_pool.py 가 강제한다(범위 검사 · 임시 포트 직접
bind 적발 · 촘촘한 재시도 루프 적발).

사용:
    from portpool import free_port          # 포트 번호만 필요할 때
    from portpool import pool_socket        # 포트를 잡은 채 넘겨야 할 때
    from portpool import wait_server        # 서버가 뜰 때까지 (백오프)
"""
import os
import socket
import tempfile
import threading
import time

try:
    import fcntl
except ImportError:      # 윈도우 — 슬롯 잠금 없이 pid 로만 나눈다
    fcntl = None

# 18800~18863 — 윈도우 동적 범위(49152~65535)와 커널 임시 범위(32768~60999)
# 양쪽 모두의 아래. 대시보드 기본 포트(9909)와 그 스캔 대역(9910~9950)도 피한다.
POOL_BASE = int(os.environ.get("S9_TEST_PORT_BASE", "18800"))
POOL_SIZE = int(os.environ.get("S9_TEST_PORT_SIZE", "64"))

# 스위트가 동시에 여러 개 돌 수 있다(무인 감사 세션 병렬) — 풀을 슬롯으로 갈라
# 프로세스마다 다른 구간을 쓰게 한다. 같은 포트를 동시에 노려 서로 밀어내는
# 사고(테스트가 서버를 띄우기 직전에 남이 채감)를 구조적으로 없앤다.
POOL_SLOTS = 4
SLOT_SIZE = POOL_SIZE // POOL_SLOTS
LOCK_DIR = os.path.join(tempfile.gettempdir(), "s9-portpool")

WIN_DYNAMIC_START = 49152          # 윈도우 기본 동적 포트 시작
EPHEMERAL_FALLBACK = (32768, 60999)  # /proc 을 못 읽을 때의 리눅스 기본값

_lock = threading.Lock()
_slot = None        # 이 프로세스가 잡은 슬롯 번호
_slot_fd = None     # 프로세스가 살아 있는 동안 유지되는 잠금 fd
_cursor = 0


def ephemeral_range():
    """커널 임시 포트 범위 (lo, hi). 읽을 수 없으면 리눅스 기본값."""
    try:
        with open("/proc/sys/net/ipv4/ip_local_port_range") as f:
            lo, hi = f.read().split()[:2]
        return int(lo), int(hi)
    except (OSError, ValueError):
        return EPHEMERAL_FALLBACK


def pool_ports(base=None, size=None):
    base = POOL_BASE if base is None else base
    size = POOL_SIZE if size is None else size
    return [base + i for i in range(size)]


def _claim_slot():
    """이 프로세스 몫의 슬롯을 잡는다 — 다른 스위트와 포트 구간이 겹치지 않게.

    슬롯 파일에 flock 을 걸고 프로세스가 끝날 때까지 들고 있는다. 슬롯이
    전부 차 있으면(스위트 5개 이상 동시 실행) pid 로 나눠 공유한다 — 그때도
    bind 확인이 있으니 실패가 아니라 경합만 조금 늘어난다.
    """
    global _slot, _slot_fd
    if _slot is not None:
        return _slot
    order = [(os.getpid() + i) % POOL_SLOTS for i in range(POOL_SLOTS)]
    if fcntl is not None:
        try:
            os.makedirs(LOCK_DIR, exist_ok=True)
            for cand in order:
                fd = os.open(os.path.join(LOCK_DIR, f"slot{cand}.lock"),
                             os.O_CREAT | os.O_RDWR, 0o644)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    os.close(fd)
                    continue
                _slot, _slot_fd = cand, fd
                return _slot
        except OSError:
            pass
    _slot = order[0]
    return _slot


def slot_ports():
    """이 프로세스가 쓸 포트 구간."""
    slot = _claim_slot()
    return [POOL_BASE + slot * SLOT_SIZE + i for i in range(SLOT_SIZE)]


def _try_bind(port):
    """실제로 잡을 수 있는 포트인지 확인 — 잡히면 bind+listen 된 소켓을 준다."""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        s.listen(8)
        return s
    except OSError:
        s.close()
        return None


def pool_socket(base=None, size=None):
    """풀에서 하나를 잡아 bind+listen 상태의 소켓으로 돌려준다.

    포트를 놓지 않고 그대로 넘겨야 하는 테스트(가짜 서버 등)용. 닫는 책임은
    호출자에게 있다.
    """
    global _cursor
    ports = slot_ports() if base is None and size is None else pool_ports(base, size)
    n = len(ports)
    with _lock:
        start = _cursor % n
        for i in range(n):
            s = _try_bind(ports[(start + i) % n])
            if s is not None:
                _cursor = (start + i + 1) % n
                return s
    raise RuntimeError(
        f"테스트 포트 풀 소진: {ports[0]}~{ports[-1]} {n}개가 모두 사용 중이다. "
        "고아 테스트 서버가 남아 있을 수 있다 — `s9 doctor --fix` 로 회수하라.")


def free_port(base=None, size=None):
    """풀에서 지금 비어 있는 포트 번호 하나. 곧 서버가 잡을 것이라고 가정한다."""
    s = pool_socket(base, size)
    try:
        return s.getsockname()[1]
    finally:
        s.close()


# 대기 파라미터 — 40초까지 기다리되 두드리는 횟수는 30회 이하로 (백오프).
WAIT_TIMEOUT = 40.0
WAIT_FIRST = 0.05
WAIT_MAX = 2.0
WAIT_GROWTH = 1.7


def wait_server(port, host="127.0.0.1", timeout=WAIT_TIMEOUT, _connect=None):
    """서버가 뜰 때까지 기다린다 — 지수 백오프로 **연결 시도 횟수**를 아낀다.

    왜 횟수가 비용인가: 실측(2026-08-26) 결과 WSL 안에서 localhost 로 여는 TCP
    커넥션 하나가 윈도우 중계(DllHost)의 동적 포트 하나를 잡는다 — 30개 연결에
    Bound +30 이 재현됐다. 반면 리스닝 포트를 새로 공개하는 것(+0~1)이나 윈도우
    브라우저에서 WSL 로 들어오는 요청(+0)은 거의 비용이 없었다. 즉 고갈을
    만드는 것은 포트 번호가 아니라 **우리가 여는 커넥션 수**다.

    예전 대기 루프는 0.1초 간격 400회였다. 평시엔 두세 번에 끝나지만, 호스트가
    말라 공개가 늦어지는 바로 그 순간에는 파일마다 400회씩 두드린다 — 스위트
    14개 파일이면 최대 5,600 커넥션이 고갈에 기름을 붓는다. 고장이 부하를 키우는
    되먹임을 끊으려고 백오프로 바꿨다(40초 대기 시 30회 이하).

    반환: 성공까지 걸린 시도 횟수. 실패하면 RuntimeError.
    """
    def _default():
        # **연결됨 ≠ 준비됨.** WSL virtioproxy 에서는 아무도 듣지 않는 포트에도
        # connect 가 성공한다 — 중계가 대신 받고 곧 RST 를 던진다. 그래서
        # connect 만으로 판정하면 서버가 뜨기 전에 루프를 빠져나가고, 뒤이은
        # 요청이 ConnectionReset 으로 깨진다(terminal_api·agent_relay·live_signal
        # 앞쪽 테스트가 그렇게 흔들렸다). 응답의 첫 바이트까지 봐야 진짜다.
        with socket.create_connection((host, port), 1.0) as c:
            c.sendall(f"GET / HTTP/1.0\r\nHost: {host}:{port}\r\n\r\n"
                      .encode())
            c.settimeout(2.0)
            head = c.recv(5)
        if not head.startswith(b"HTTP/"):
            raise OSError(f"{host}:{port} — 연결은 됐지만 HTTP 응답이 없다 "
                          f"(중계가 받아준 가짜 연결)")

    connect = _connect or _default
    deadline = time.monotonic() + timeout
    delay = WAIT_FIRST
    attempts = 0
    while True:
        attempts += 1
        try:
            connect()
            return attempts
        except OSError:
            left = deadline - time.monotonic()
            if left <= 0:
                raise RuntimeError(
                    f"server did not start on {host}:{port} — "
                    f"{timeout:.0f}초 동안 {attempts}회 시도")
            time.sleep(min(delay, left))
            delay = min(delay * WAIT_GROWTH, WAIT_MAX)
