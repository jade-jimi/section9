"""담당자 변경은 한 문을 지난다 (REQ-20260902-019).

`s9 assign <id> <user>` 와 `POST /api/assign` 이 do_assign 하나를 부른다 —
담당자(user) 갱신 + 생성자 불변 + History 한 줄 + 옛 자리의 클레임·리스 회수.

실행: python3 tests/ assign
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class Assign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s9assign-")
        cls.base = {**os.environ, "S9_ROOT": cls.root, "S9_MACHINE": "testbox"}
        for k in ("S9_SESSION", "S9_AUTO_RESUME", "S9_JOB_REQ", "S9_USER"):
            cls.base.pop(k, None)
        subprocess.run([S9, "init"], capture_output=True, env=cls.base)
        for u in ("alice", "bob", "carol", "root", "eve"):
            subprocess.run([S9, "user", "add", u], capture_output=True,
                           env=cls.base, stdin=subprocess.DEVNULL)
        subprocess.run([S9, "user", "role", "root", "admin"], capture_output=True,
                       env={**cls.base, "S9_USER": "root"}, stdin=subprocess.DEVNULL)
        subprocess.run([S9, "user", "role", "eve", "viewer"], capture_output=True,
                       env={**cls.base, "S9_USER": "root"}, stdin=subprocess.DEVNULL)
        os.environ["S9_ROOT"] = cls.root
        os.environ["S9_MACHINE"] = "testbox"
        spec = importlib.util.spec_from_loader(
            "s9_assign", importlib.machinery.SourceFileLoader("s9_assign", S9))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("S9_ROOT", None)
        os.environ.pop("S9_MACHINE", None)
        shutil.rmtree(cls.root, ignore_errors=True)

    def cli(self, *argv, user=None, expect=0):
        env = dict(self.base)
        if user:
            env["S9_USER"] = user
        r = subprocess.run([S9, *argv], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL)
        if expect is not None:
            self.assertEqual(r.returncode, expect, r.stdout + r.stderr)
        return r

    def new(self, user="alice"):
        r = self.cli("new", "request", "--title", "t", "--summary", "s", "--size", "S",
                     "--goal", "g", "--body", "b", "--origin", "human", "--user", user)
        return r.stdout.split()[0]

    def meta(self, rid):
        return self.m.read_doc(self.m.locate(rid))

    # A1. 정상
    def test_a1_assign_changes_user_keeps_creator_writes_history(self):
        rid = self.new("alice")
        r = self.cli("assign", rid, "bob", "--why", "휴가", user="alice")
        self.assertIn("alice → bob", r.stdout)
        meta, body = self.meta(rid)
        self.assertEqual(meta["user"], "bob")
        self.assertEqual(meta["creator"], "alice")
        self.assertIn("assignee: alice -> bob (by alice) — 휴가", body)
        row = [x for x in self.m.load_catalog() if x["id"] == rid][0]
        self.assertEqual(row["user"], "bob")

    # A2. 권한
    def test_a2_permission(self):
        rid = self.new("alice")
        r = self.cli("assign", rid, "bob", user="carol", expect=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("권한 없음", r.stdout + r.stderr)
        self.assertEqual(self.meta(rid)[0]["user"], "alice")
        self.cli("assign", rid, "bob", user="root")           # admin
        self.assertEqual(self.meta(rid)[0]["user"], "bob")
        self.cli("assign", rid, "carol", user="bob")          # 현 담당자
        self.assertEqual(self.meta(rid)[0]["user"], "carol")
        self.cli("assign", rid, "bob", user="alice")          # 생성자
        self.assertEqual(self.meta(rid)[0]["user"], "bob")

    # A3. 거부·no-op
    def test_a3_refusals_and_noop(self):
        rid = self.new("alice")
        for who, msg in (("nobody", "등록되지 않은"), ("eve", "관찰 계정")):
            r = self.cli("assign", rid, who, user="alice", expect=None)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(msg, r.stdout + r.stderr)
        r = self.cli("assign", rid, "alice", user="alice")
        self.assertIn("그대로", r.stdout)
        self.cli("status", rid, "cancelled", "--note", "x", "--force", user="alice")
        r = self.cli("assign", rid, "bob", user="alice", expect=None)
        self.assertNotEqual(r.returncode, 0)

    # A4. 옛 자리의 클레임·리스 회수
    def test_a4_claims_and_lease_are_released(self):
        rid = self.new("alice")
        self.cli("status", rid, "in-progress", "--note", "t", user="alice")
        os.makedirs(self.m.STATE, exist_ok=True)
        bp = os.path.join(self.m.STATE, "testbox__oldsess1.json")
        with open(bp, "w", encoding="utf-8") as f:
            json.dump({"machine": "testbox", "session": "oldsess1", "user": "alice",
                       "history": [], "active_reqs": [rid]}, f)
        path = self.m.locate(rid)
        meta, body = self.m.read_doc(path)
        meta["lease"] = {"user": "alice", "machine": "testbox", "session": "oldsess1"}
        self.m.write_doc(path, meta, body)
        self.m.do_assign(rid, "bob", actor="alice", why="넘김")
        meta, _ = self.meta(rid)
        self.assertNotIn("lease", meta)
        with open(bp, encoding="utf-8") as f:
            self.assertNotIn(rid, json.load(f).get("active_reqs") or [])

    # A5. 화면도 같은 문
    def test_a5_api_uses_the_same_door(self):
        with open(S9, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('parsed.path == "/api/assign"', src)
        self.assertIn('via="dashboard")', src.split('parsed.path == "/api/assign"', 1)[1][:600])
        rid = self.new("alice")
        res = self.m.do_assign(rid, "bob", actor="root", why="화면", via="dashboard")
        self.assertTrue(res["changed"])
        self.assertIn("(by root via dashboard) — 화면", self.meta(rid)[1])


if __name__ == "__main__":
    unittest.main()
