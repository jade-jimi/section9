"""s9 code 실행 인자 전달 테스트 (REQ-20260824-036).

s9 code 뒤의 인자는 claude에 그대로 전달되고(REMAINDER), 계정 설정
s9code_args가 기본 인자로 앞에 붙는다(명령행이 우선). S9_CODE_DRYRUN=1 이면
exec 대신 최종 명령을 JSON으로 출력한다(테스트 시임).

격리: S9_ROOT=mktemp, S9_PORT=유효 포트에 미리 접속 가능해야 서버 스폰이
없다 — 여기서는 더미 리스너를 띄워 대시보드 보장 단계를 스킵시킨다.
실행: python3 tests/test_s9_code_args.py
"""
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class TestCodeArgs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9code-")
        # 더미 리스너: cmd_code의 포트 체크를 통과시켜 실서버 스폰 방지
        cls.lsock = socket.socket()
        cls.lsock.bind(("127.0.0.1", 0))
        cls.lsock.listen(8)
        cls.port = cls.lsock.getsockname()[1]
        t = threading.Thread(target=cls._accept_loop, daemon=True)
        t.start()
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_PORT": str(cls.port),
                   "S9_CODE_DRYRUN": "1", "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], capture_output=True, env=cls.env, timeout=15)
        subprocess.run([S9, "user", "add", "tester"], capture_output=True,
                       env=cls.env, timeout=15)

    @classmethod
    def _accept_loop(cls):
        while True:
            try:
                c, _ = cls.lsock.accept()
                c.close()
            except OSError:
                return

    @classmethod
    def tearDownClass(cls):
        cls.lsock.close()

    def run_code(self, *argv):
        r = subprocess.run([S9, "code", *argv], capture_output=True, text=True,
                           env=self.env, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        return last

    # G1. 인자 전달: 뒤따르는 인자가 claude 명령에 그대로 포함
    def test_g1_args_passthrough(self):
        out = self.run_code("--permission-mode", "acceptEdits")
        cmd = json.loads(out)
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--permission-mode", cmd)
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "acceptEdits")

    # G2. 계정 기본값: s9code_args 설정이 실행 인자에 포함
    def test_g2_config_default(self):
        subprocess.run([S9, "user", "config", "tester", "s9code_args",
                        "--permission-mode acceptEdits"],
                       capture_output=True, env=self.env, timeout=15)
        try:
            cmd = json.loads(self.run_code())
            self.assertIn("--permission-mode", cmd)
            self.assertIn("acceptEdits", cmd)
        finally:
            subprocess.run([S9, "user", "config", "tester", "s9code_args", ""],
                           capture_output=True, env=self.env, timeout=15)

    # G3. 병합 순서: 계정 기본값이 앞, 명령행이 뒤(명령행 우선)
    def test_g3_merge_order(self):
        subprocess.run([S9, "user", "config", "tester", "s9code_args", "--model opus"],
                       capture_output=True, env=self.env, timeout=15)
        try:
            cmd = json.loads(self.run_code("--model", "sonnet"))
            self.assertEqual(cmd.index("--model"), 1)          # 기본값이 먼저
            self.assertEqual(cmd[1:3], ["--model", "opus"])
            self.assertEqual(cmd[3:5], ["--model", "sonnet"])  # 명령행이 뒤
        finally:
            subprocess.run([S9, "user", "config", "tester", "s9code_args", ""],
                           capture_output=True, env=self.env, timeout=15)

    # G5. auto 모드(REQ-20260824-036 반려 반영): s9code_args '--permission-mode
    # auto' 설정 시 claude가 auto 모드로 실행 — 사람이 다시 승인할 필요가 없다
    def test_g5_auto_mode_config(self):
        subprocess.run([S9, "user", "config", "tester", "s9code_args",
                        "--permission-mode auto"],
                       capture_output=True, env=self.env, timeout=15)
        try:
            cmd = json.loads(self.run_code())
            self.assertEqual(cmd[1:3], ["--permission-mode", "auto"])
        finally:
            subprocess.run([S9, "user", "config", "tester", "s9code_args", ""],
                           capture_output=True, env=self.env, timeout=15)

    # G4. 회귀: --no-claude 는 대시보드만 — dry-run 출력(JSON exec 라인) 없음
    def test_g4_no_claude(self):
        r = subprocess.run([S9, "code", "--no-claude"], capture_output=True,
                           text=True, env=self.env, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('["claude"', r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
