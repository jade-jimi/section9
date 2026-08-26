"""서버 keep-alive 테스트 (REQ-20260824-039).

HTTP/1.1 + Content-Length 로 동일 커넥션 연속 요청이 정상 동작해야 한다
(HTTP/1.0 시절 대시보드 폴링의 간헐 ERR_CONNECTION_RESET 회귀 방지).

격리: S9_ROOT=mktemp. 실행: python3 tests/test_server_keepalive.py
"""
import http.client
import os
import socket
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

# 임시 포트를 뽑지 않는다 — 고정 풀에서 돌려쓴다 (REQ-20260825-100, portpool 참조)
from portpool import free_port, wait_server  # noqa: E402


class TestKeepAlive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9ka-")
        env = {**os.environ, "S9_ROOT": cls.tmp, "S9_REWORK_WATCH": "off"}
        env.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], capture_output=True, env=env, timeout=15)
        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_server(cls.port)   # WSL 포트 공개 지연 대비 (REQ-099) — 백오프 대기

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    # K1. HTTP/1.1 + Content-Length + 동일 커넥션 연속 요청 (keep-alive 재사용)
    def test_k1_keepalive_reuse(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            for i in range(5):
                conn.request("GET", "/api/chat/target")
                r = conn.getresponse()
                self.assertEqual(r.version, 11, "HTTP/1.1 이어야 한다")
                self.assertIsNotNone(r.getheader("Content-Length"))
                body = r.read()  # 커넥션 재사용 전 소진 필수
                self.assertTrue(body)
                self.assertNotEqual(r.getheader("Connection", ""), "close")
        finally:
            conn.close()

    # K2. 404 등 에러 응답도 keep-alive 유지 (Content-Length 존재)
    def test_k2_error_response_keepalive(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/api/doc?id=REQ-00000000-000")
            r = conn.getresponse()
            self.assertIsNotNone(r.getheader("Content-Length"))
            r.read()
            conn.request("GET", "/api/chat/target")  # 같은 커넥션 재사용
            r2 = conn.getresponse()
            self.assertEqual(r2.status, 200)
            r2.read()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
