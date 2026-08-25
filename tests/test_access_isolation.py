"""대시보드 열람 격리 테스트 (REQ-20260824-017, 신원 모델은 REQ-20260824-027).

가드레일 격리: 서버 파생 신원(whoami) 기준으로 GET API 응답에서 비가시 문서를
제거한다. 구모델의 ?me= 자기신고는 폐기 — 시점 통제는 서버 프로세스의 S9_USER
(whoami)와 admin 전용 ?as= 로 한다. 검증 의미(비멤버 비가시/멤버 가시/admin
전부/무소속 작성자만/audit 스코프)는 구모델 테스트와 동일하게 보존.
- /api/users?scope=machine → 이 머신(registered_on) 등록 계정만
- doc_visible: admin=전부, 프로젝트 문서=활성 멤버만, 무소속=작성자만

격리: S9_ROOT=mktemp + S9_MACHINE 고정 — 라이브 vault를 건드리지 않는다.
실행: python3 tests/test_access_isolation.py
"""
import json
import os
import re
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
MACHINE = "TESTMACH"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestAccessIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9iso-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": MACHINE,
                   "S9_REWORK_WATCH": "off"}
        cls.env.pop("S9_SESSION", None)
        cls.env.pop("S9_USER", None)

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
        cli("user", "add", "alice")
        cli("user", "add", "bob")
        # 다른 머신에서 등록된 계정 — me 셀렉터 후보에서 빠져야 한다 (V1)
        cli("user", "add", "remote", "--machine", "OTHERMACH")

        cli("project", "add", "px", "--name", "PX", "--user", "alice")
        r = cli("new", "request", "--title", "px doc", "--summary", "px",
                "--goal", "t", "--project", "px", "--user", "alice",
                "--body", "zebra-token-px")
        cls.px_doc = re.search(r"REQ-\d{8}-\d{3,}(?:-[0-9a-z]{4})?", r.stdout).group(0)
        # 무소속 문서 — bob은 프로젝트가 없어 auto-assign이 안 걸린다 (V5)
        r = cli("new", "request", "--title", "solo doc", "--summary", "solo",
                "--goal", "t", "--user", "bob", "--body", "zebra-token-solo")
        cls.solo_doc = re.search(r"REQ-\d{8}-\d{3,}(?:-[0-9a-z]{4})?", r.stdout).group(0)
        # alice의 세션 audit 문서 (V7) — SES 문서는 project 없음 → 작성자만
        cli("log", "alice-private-event", "--session", "aaaa1111",
            "--user", "alice")

        # 신원은 서버 파생(whoami) — admin(boss) 서버에서 ?as= 로 시점을
        # 전환해 격리를 검증하고, 비admin 직접 시점은 bob 서버로 본다.
        cls.port = free_port()        # S9_USER=boss (admin)
        cls.port_bob = free_port()    # S9_USER=bob (비admin)
        cls.srvs = []
        for port, s9user in ((cls.port, "boss"), (cls.port_bob, "bob")):
            env = {**cls.env, "S9_USER": s9user}
            cls.srvs.append(subprocess.Popen(
                [S9, "serve", "--host", "127.0.0.1", "--port", str(port)],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for port in (cls.port, cls.port_bob):
            for _ in range(50):
                try:
                    socket.create_connection(("127.0.0.1", port), 0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("server did not start")

    @classmethod
    def tearDownClass(cls):
        for p in cls.srvs:
            p.terminate()
        for p in cls.srvs:
            p.wait(timeout=5)

    @classmethod
    def get(cls, path, port=None, **params):
        qs = urllib.parse.urlencode(params)
        url = f"http://127.0.0.1:{port or cls.port}{path}" \
              + (f"?{qs}" if qs else "")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    return r.status, json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode())
            except (ConnectionError, urllib.error.URLError):
                # 기동 직후 loopback RST 플레이크 (WSL2) — 짧게 재시도
                if attempt == 2:
                    raise
                time.sleep(0.3)

    def catalog_ids(self, viewer):
        # admin(boss) whoami 서버에서 ?as=<viewer> 로 시점 전환 (admin 본인은 무지정)
        params = {} if viewer == "boss" else {"as": viewer}
        code, rows = self.get("/api/catalog", **params)
        self.assertEqual(code, 200)
        return {r["id"] for r in rows}

    # V1. me 셀렉터 후보 = 이 머신 등록 계정만
    def test_v1_users_machine_scope(self):
        code, d = self.get("/api/users", scope="machine")
        self.assertEqual(code, 200)
        names = {u["name"] for u in d["users"]}
        self.assertEqual(names, {"boss", "alice", "bob"})
        self.assertEqual(d.get("machine"), MACHINE)
        # scope 미지정(Settings 사용자 관리)은 전체 유지
        code, d = self.get("/api/users")
        self.assertIn("remote", {u["name"] for u in d["users"]})

    # V2. 비멤버에게 프로젝트 문서 비가시
    def test_v2_nonmember_hidden(self):
        self.assertNotIn(self.px_doc, self.catalog_ids("bob"))
        code, g = self.get("/api/graph", **{"as": "bob"})
        self.assertEqual(code, 200)
        self.assertNotIn(self.px_doc, {n["id"] for n in g["nodes"]})
        for e in g["edges"]:
            self.assertNotIn(self.px_doc, (e["from"], e["to"]))
        code, s = self.get("/api/search", q="zebra-token-px", **{"as": "bob"})
        self.assertEqual([r["id"] for r in s["results"]], [])
        code, _ = self.get("/api/doc", id=self.px_doc, **{"as": "bob"})
        self.assertEqual(code, 404)
        code, _ = self.get("/api/reqstream", id=self.px_doc, **{"as": "bob"})
        self.assertEqual(code, 404)
        code, p = self.get("/api/projects", **{"as": "bob"})
        self.assertNotIn("px", {x["slug"] for x in p["projects"]})

    # V2b. 비admin whoami 서버의 기본 시점 = 자기 자신 (as 없이도 격리 동작,
    #      비admin의 as 는 무시되어 상승 불가)
    def test_v2b_nonadmin_direct_view(self):
        code, rows = self.get("/api/catalog", port=self.port_bob)
        self.assertEqual(code, 200)
        ids = {r["id"] for r in rows}
        self.assertNotIn(self.px_doc, ids)
        self.assertIn(self.solo_doc, ids)
        code, rows = self.get("/api/catalog", port=self.port_bob,
                              **{"as": "boss"})
        self.assertNotIn(self.px_doc, {r["id"] for r in rows})

    # V3. 활성 멤버는 보인다
    def test_v3_member_visible(self):
        self.assertIn(self.px_doc, self.catalog_ids("alice"))
        code, _ = self.get("/api/doc", id=self.px_doc, **{"as": "alice"})
        self.assertEqual(code, 200)
        code, s = self.get("/api/search", q="zebra-token-px", **{"as": "alice"})
        self.assertIn(self.px_doc, {r["id"] for r in s["results"]})
        code, p = self.get("/api/projects", **{"as": "alice"})
        self.assertIn("px", {x["slug"] for x in p["projects"]})

    # V4. 시스템 admin 은 전부
    def test_v4_admin_sees_all(self):
        ids = self.catalog_ids("boss")
        self.assertIn(self.px_doc, ids)
        self.assertIn(self.solo_doc, ids)
        code, p = self.get("/api/projects")
        self.assertIn("px", {x["slug"] for x in p["projects"]})

    # V5. 무소속 문서 = 작성자만
    def test_v5_unassigned_author_only(self):
        self.assertIn(self.solo_doc, self.catalog_ids("bob"))
        self.assertNotIn(self.solo_doc, self.catalog_ids("alice"))
        code, _ = self.get("/api/doc", id=self.solo_doc, **{"as": "alice"})
        self.assertEqual(code, 404)

    # V7. audit 이벤트는 해당 SES 문서 가시성 기준
    def test_v7_audit_scoped(self):
        code, d = self.get("/api/audit", **{"as": "alice"})
        self.assertEqual(code, 200)
        self.assertTrue(any("alice-private-event" in e["text"]
                            for e in d["events"]))
        code, d = self.get("/api/audit", **{"as": "bob"})
        self.assertFalse(any("alice-private-event" in e["text"]
                             for e in d["events"]))
        code, d = self.get("/api/audit")
        self.assertTrue(any("alice-private-event" in e["text"]
                            for e in d["events"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
