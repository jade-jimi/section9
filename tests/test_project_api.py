"""프로젝트 생성·설정 API 테스트 (REQ-20260831-027).

do_project_add/do_project_set 단일 경로 — CLI(project add/set)와 웹 서버
(POST /api/project/add, /api/project/set)가 공유한다 (do_member_set 전례).
actor 는 서버 파생 whoami — admin(boss) 서버에서 "as" 대리로 각 역할을 검증.

권한 (REQ-20260831-026 G0 확정):
- 생성: 등록 사용자 누구나 + 생성자 자동 owner + admin 우회(as 대리)
- 설정: manage(maintainer+), 단 status 변경만 own(owner) — 독스트링-구현
  불일치를 own 쪽으로 해소
- set 도 History 를 남긴다 (기존 CLI set 미기록 비대칭 교정)

격리: S9_ROOT=mktemp — 라이브 vault 를 건드리지 않는다.
실행: python3 tests/test_project_api.py
"""
import json
import os
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

from portpool import free_port, wait_server  # noqa: E402


class TestProjectApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9test-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp}
        cls.env.pop("S9_SESSION", None)

        def cli(*argv, expect=0):
            r = subprocess.run([S9, *argv], capture_output=True, text=True,
                               env=cls.env, timeout=15)
            if expect is not None and r.returncode != expect:
                raise AssertionError(f"s9 {' '.join(argv)}: rc={r.returncode}\n"
                                     f"{r.stdout}{r.stderr}")
            return r
        cls.cli = staticmethod(cli)

        cli("init")
        cli("user", "add", "boss", "--role", "admin")
        for u in ("alice", "bob", "carol", "vera"):
            cli("user", "add", u)
        # demo: alice=owner, bob=maintainer, carol=contributor, vera=viewer
        cli("project", "add", "demo", "--name", "Demo", "--user", "alice")
        cli("project", "member", "demo", "add", "bob",
            "--role", "maintainer", "--user", "alice")
        cli("project", "member", "demo", "add", "carol",
            "--role", "contributor", "--user", "alice")
        cli("project", "member", "demo", "add", "vera",
            "--role", "viewer", "--user", "alice")

        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env={**cls.env, "S9_USER": "boss"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_server(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    @classmethod
    def post(cls, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{cls.port}{path}",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode())
            except (ConnectionError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(0.3)

    @classmethod
    def projects(cls):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{cls.port}/api/projects", timeout=5) as r:
            return json.loads(r.read().decode())["projects"]

    @classmethod
    def proj(cls, slug):
        return next(p for p in cls.projects() if p["slug"] == slug)

    def doc_text(self, slug):
        with open(os.path.join(self.tmp, "vault", "projects", slug + ".md"),
                  encoding="utf-8") as f:
            return f.read()

    # ── 정상 ────────────────────────────────────────────────────────────

    # S1. 생성: 등록 사용자 → PRJ 생성 + 생성자 owner + 스캐폴드 + History
    def test_01_create_ok(self):
        code, res = self.post("/api/project/add",
                              {"as": "alice", "slug": "neo", "name": "Neo",
                               "summary": "새 프로젝트", "customer": "ACME"})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(str(res.get("id", "")).startswith("PRJ-"), res)
        p = self.proj("neo")
        self.assertEqual(p["title"], "Neo")
        self.assertEqual(p["customer"], "ACME")
        mem = {m["user"]: m for m in p["members"]}
        self.assertEqual(mem["alice"]["role"], "owner")
        self.assertIn("created by alice", self.doc_text("neo"))
        self.assertTrue(os.path.isfile(os.path.join(
            self.tmp, "projects", "neo", "CONTEXT.md")))
        # 같은 날 생성한 프로젝트끼리 id 충돌 금지 — next_id 가 slug 파일명을
        # 스캔해 PRJ 순번을 못 보던 기존 결함의 회귀 가드 (REQ-20260831-027)
        self.assertNotEqual(res["id"], self.proj("demo")["id"])

    # S2. 설정 8필드 (maintainer, status 제외) + History 기록 교정
    def test_02_set_fields_and_history(self):
        code, res = self.post("/api/project/set",
                              {"as": "bob", "slug": "demo",
                               "name": "Demo2", "summary": "요약",
                               "customer": "고객사",
                               "contact_name": "김담당",
                               "contact_email": "kim@x.co",
                               "contact_phone": "010-0000-0000",
                               "contact_org": "현업팀"})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get("ok"), res)
        p = self.proj("demo")
        self.assertEqual(p["title"], "Demo2")
        self.assertEqual(p["summary"], "요약")
        self.assertEqual(p["customer"], "고객사")
        self.assertEqual(p["contact_name"], "김담당")
        self.assertEqual(p["contact_email"], "kim@x.co")
        self.assertEqual(p["contact_phone"], "010-0000-0000")
        self.assertEqual(p["contact_org"], "현업팀")
        # set 이 History 를 남긴다 (비대칭 교정)
        txt = self.doc_text("demo")
        self.assertIn("set title=Demo2", txt)
        self.assertIn("by bob via dashboard", txt)

    # S3. status 는 own: owner 보관→복원, admin(비멤버) 우회
    def test_03_status_own_and_admin(self):
        code, res = self.post("/api/project/set",
                              {"as": "alice", "slug": "demo",
                               "status": "archived"})
        self.assertEqual(code, 200, res)
        self.assertEqual(self.proj("demo")["status"], "archived")
        # admin(boss)은 멤버가 아니어도 우회
        code, res = self.post("/api/project/set",
                              {"as": "boss", "slug": "demo",
                               "status": "active"})
        self.assertEqual(code, 200, res)
        self.assertEqual(self.proj("demo")["status"], "active")
        self.assertIn("set status=archived", self.doc_text("demo"))

    # S4. GET /api/projects 에 history_tail (additive, ≤10줄)
    def test_04_history_tail(self):
        p = self.proj("demo")
        self.assertIn("history_tail", p)
        tail = p["history_tail"]
        self.assertIsInstance(tail, list)
        self.assertLessEqual(len(tail), 10)
        self.assertTrue(any("created by alice" in ln or "set " in ln
                            for ln in tail), tail)

    # ── 경계 ────────────────────────────────────────────────────────────

    # E1. slug 중복 거부
    def test_05_duplicate_slug(self):
        code, res = self.post("/api/project/add",
                              {"as": "alice", "slug": "demo", "name": "X"})
        self.assertEqual(code, 400, res)
        self.assertIn("already", res.get("error", ""))

    # E2. slug 형식 거부
    def test_06_bad_slug(self):
        code, res = self.post("/api/project/add",
                              {"as": "alice", "slug": "bad slug!", "name": "X"})
        self.assertEqual(code, 400, res)

    # E3. 빈 요청 거부 + 빈 문자열은 '비우기'로 정상
    def test_07_empty_fields(self):
        code, res = self.post("/api/project/set", {"as": "bob", "slug": "demo"})
        self.assertEqual(code, 400, res)
        code, res = self.post("/api/project/set",
                              {"as": "bob", "slug": "demo", "summary": ""})
        self.assertEqual(code, 200, res)
        self.assertEqual(self.proj("demo")["summary"], "")

    # E4. 마지막 owner 가드 회귀 (기존 멤버 API 경유)
    def test_08_last_owner_guard(self):
        code, res = self.post("/api/project/member",
                              {"as": "alice", "slug": "demo",
                               "member": "alice", "role": "maintainer"})
        self.assertEqual(code, 400, res)

    # ── 실패(거부 4종 — 핸들러는 do_* 중계만, 옆문 없음) ────────────────

    # F1. 미등록 사용자 생성 거부: CLI(단일 경로 게이트) + API(as 대리)
    def test_09_unregistered_create_denied(self):
        r = self.cli("project", "add", "ghostp", "--user", "ghost",
                     expect=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(
            self.tmp, "vault", "projects", "ghostp.md")))
        code, res = self.post("/api/project/add",
                              {"as": "ghost", "slug": "ghostp2", "name": "G"})
        self.assertEqual(code, 400, res)

    # F2. viewer 설정 거부 (manage 미달)
    def test_10_viewer_set_denied(self):
        code, res = self.post("/api/project/set",
                              {"as": "vera", "slug": "demo", "name": "훼손"})
        self.assertEqual(code, 400, res)
        self.assertNotEqual(self.proj("demo")["title"], "훼손")

    # F3. contributor status 거부
    def test_11_contributor_status_denied(self):
        code, res = self.post("/api/project/set",
                              {"as": "carol", "slug": "demo",
                               "status": "archived"})
        self.assertEqual(code, 400, res)
        self.assertEqual(self.proj("demo")["status"], "active")

    # F4. 비 owner(maintainer) status 거부 — own 게이트
    def test_12_maintainer_status_denied(self):
        code, res = self.post("/api/project/set",
                              {"as": "bob", "slug": "demo",
                               "status": "archived"})
        self.assertEqual(code, 400, res)
        self.assertEqual(self.proj("demo")["status"], "active")

    # ── 회귀 ────────────────────────────────────────────────────────────

    # R1. CLI 경로 불변: add/set 이 do_* 를 지나 동작·거부 동일
    def test_13_cli_regression(self):
        r = self.cli("project", "add", "cliproj", "--name", "CLI",
                     "--user", "alice")
        self.assertIn("owner=alice", r.stdout)
        self.cli("project", "set", "cliproj", "--customer", "CLI고객",
                 "--user", "alice")
        self.assertEqual(self.proj("cliproj")["customer"], "CLI고객")
        self.assertIn("set customer=CLI고객", self.doc_text("cliproj"))
        # viewer 는 CLI 로도 거부 (단일 경로)
        r = self.cli("project", "set", "demo", "--name", "X",
                     "--user", "vera", expect=None)
        self.assertNotEqual(r.returncode, 0)
        # status 는 CLI 로도 own (maintainer 거부)
        r = self.cli("project", "set", "demo", "--status", "archived",
                     "--user", "bob", expect=None)
        self.assertNotEqual(r.returncode, 0)

    # R2. GET /api/projects 기존 필드 불변 (additive-only)
    def test_14_projects_schema_additive(self):
        p = self.proj("demo")
        for k in ("id", "slug", "title", "summary", "status", "customer",
                  "contact_name", "contact_email", "contact_phone",
                  "contact_org", "members", "member_active", "member_total"):
            self.assertIn(k, p)
        self.assertIsInstance(p["member_active"], int)
        m = p["members"][0]
        self.assertIn("active", m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
