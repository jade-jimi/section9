"""사용자 프로필 확장 테스트 (REQ-20260824-055 E1~E6).

회사 이메일 N개(emails)·개인/조직 GitHub 분리 저장 + 미기재 촉구(digest).
격리: S9_ROOT=mktemp. 실행: python3 tests/test_user_profile_ext.py
"""
import json
import os
import subprocess
import tempfile
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class TestProfileExt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9prof-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox"}
        cls.env.pop("S9_SESSION", None)

        def cli(*argv, expect=0):
            r = subprocess.run([S9, *argv], capture_output=True, text=True,
                               env=cls.env, timeout=15,
                               stdin=subprocess.DEVNULL)
            if expect is not None and r.returncode != expect:
                raise AssertionError(f"s9 {' '.join(argv)}: rc={r.returncode}\n"
                                     f"{r.stdout}{r.stderr}")
            return r
        cls.cli = staticmethod(cli)
        cli("init")

    def meta(self, name):
        import re
        with open(os.path.join(self.tmp, "users", name, "profile.md"),
                  encoding="utf-8") as f:
            txt = f.read()
        m = {}
        for line in txt.split("\n---\n")[0].splitlines():
            mm = re.match(r"(\w+): (.*)$", line)
            if mm:
                k, v = mm.group(1), mm.group(2)
                try:
                    m[k] = json.loads(v)
                except ValueError:
                    m[k] = v
        return m

    # E1. add: 이메일 복수 + github 2종 저장
    def test_e1_add_fields(self):
        self.cli("user", "add", "alice",
                 "--emails", "a@corp.com,a2@corp.com",
                 "--github", "@alice-gh", "--github-org", "corp-team")
        m = self.meta("alice")
        self.assertEqual(m["emails"], ["a@corp.com", "a2@corp.com"])
        self.assertEqual(m["github"], "alice-gh")     # @ 접두 제거 저장
        self.assertEqual(m["github_org"], "corp-team")

    # E2. update: emails 전체 교체·개별 갱신·형식 거부
    def test_e2_update(self):
        self.cli("user", "add", "bob", "--emails", "b@corp.com")
        r = self.cli("user", "update", "bob",
                     "--emails", "b@corp.com,b2@corp.com",
                     "--github", "bob-gh")
        self.assertIn("emails(2)", r.stdout)
        m = self.meta("bob")
        self.assertEqual(len(m["emails"]), 2)
        self.assertEqual(m["github"], "bob-gh")
        r = self.cli("user", "update", "bob", "--emails", "잘못된메일",
                     expect=None)
        self.assertNotEqual(r.returncode, 0)
        r = self.cli("user", "update", "bob", "--github", "no spaces!",
                     expect=None)
        self.assertNotEqual(r.returncode, 0)

    # E4. API: update 반영 + /api/users 노출
    def test_e4_api(self):
        import socket, time
        s = socket.socket(); s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(port)],
            env={**self.env, "S9_USER": "alice", "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", port), 0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/user/update",
                data=json.dumps({"name": "alice",
                                 "emails": ["x@corp.com"],
                                 "github_org": "new-org"}).encode(),
                method="POST",
                headers={"Content-Type": "application/json"})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=5) as r:
                        d = json.loads(r.read().decode())
                    break
                except (ConnectionError, urllib.error.URLError):
                    time.sleep(0.3)
            self.assertTrue(d.get("ok"), d)
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/users?scope=machine",
                    timeout=5) as r:
                users = json.loads(r.read().decode())["users"]
            al = next(u for u in users if u["name"] == "alice")
            self.assertEqual(al["emails"], ["x@corp.com"])
            self.assertEqual(al["github_org"], "new-org")
        finally:
            srv.terminate()
            srv.wait(timeout=5)

    # E5. 미기재 촉구: 필드 없는 사용자 digest에 ⚠ 프로필 미완성
    def test_e5_digest_nag(self):
        self.cli("user", "add", "carol")           # 아무 필드 없음
        r = self.cli("digest", "--user", "carol")
        self.assertIn("프로필 미완성", r.stdout)
        self.assertIn("GitHub", r.stdout)
        # 전부 채우면 촉구 사라짐
        self.cli("user", "update", "carol", "--emails", "c@corp.com",
                 "--github", "carol-gh", "--github-org", "corp-team")
        r = self.cli("digest", "--user", "carol")
        self.assertNotIn("프로필 미완성", r.stdout)

    # E6. 하위 호환: 기존 email 단수 필드만 있어도 이메일 촉구는 없음
    def test_e6_legacy_email(self):
        self.cli("user", "add", "dan", "--email", "d@corp.com")
        r = self.cli("digest", "--user", "dan")
        self.assertNotIn("회사 이메일", r.stdout)
        self.assertIn("GitHub", r.stdout)          # github은 여전히 촉구


if __name__ == "__main__":
    unittest.main(verbosity=2)
