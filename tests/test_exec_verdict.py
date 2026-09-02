"""실행 귀속은 한 함수가 판정한다 (REQ-20260902-016).

가드가 세 곳·세 기준(워처=만든 머신, next=user, 훅 목록=없음)이라 공유 리포에서
남의 반려 REQ 가 내 리드에게 "지금 이어서 하라"로 주입됐다. `exec_verdict` 하나가
담당자(user)·잠정 머신·역할·종결을 보고, 아홉 자리가 그것을 부른다.

실행: python3 tests/ exec_verdict
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class Verdict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s9verdict-")
        env = {**os.environ, "S9_ROOT": cls.root, "S9_MACHINE": "here"}
        env.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], capture_output=True, env=env)
        for u in ("me", "other", "watcher"):
            subprocess.run([S9, "user", "add", u], capture_output=True, env=env,
                           stdin=subprocess.DEVNULL)
        subprocess.run([S9, "user", "role", "watcher", "viewer"],
                       capture_output=True, env={**env, "S9_USER": "me"},
                       stdin=subprocess.DEVNULL)
        os.environ["S9_ROOT"] = cls.root
        os.environ["S9_MACHINE"] = "here"
        spec = importlib.util.spec_from_loader(
            "s9_verdict", importlib.machinery.SourceFileLoader("s9_verdict", S9))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("S9_ROOT", None)
        os.environ.pop("S9_MACHINE", None)
        shutil.rmtree(cls.root, ignore_errors=True)

    def local(self, user="me", machine="here", role="member"):
        return {"user": user, "machine": machine, "role": role}

    def doc(self, **kv):
        d = {"type": "request", "status": "in-progress", "user": "me",
             "machine": "here"}
        d.update(kv)
        return d

    # V1. 내 문서 → free
    def test_v1_mine_is_free(self):
        self.assertEqual(self.m.exec_verdict(self.doc(), self.local()),
                         (True, "free", ""))

    # V2. 담당 타인 → not-mine (이름 포함)
    def test_v2_others_doc_is_not_mine(self):
        ok, code, why = self.m.exec_verdict(self.doc(user="other"), self.local())
        self.assertFalse(ok)
        self.assertEqual(code, "not-mine")
        self.assertIn("other", why)

    # V3. 같은 사용자·다른 머신 → elsewhere (list/spawn), claim 은 통과
    def test_v3_same_user_other_machine(self):
        d = self.doc(machine="there")
        self.assertEqual(self.m.exec_verdict(d, self.local())[1], "elsewhere")
        self.assertEqual(self.m.exec_verdict(d, self.local(), want="spawn")[1],
                         "elsewhere")
        self.assertTrue(self.m.exec_verdict(d, self.local(), want="claim")[0])

    # V3b. 워처(spawn)는 담당자를 대신하는 자리 — 서버 계정과 담당자가 달라도
    # 이 머신의 문서면 띄운다 (잠정, 020 이 리스로 바꾼다)
    def test_v3b_spawn_is_on_behalf_of_owner(self):
        d = self.doc(user="other", machine="here")
        self.assertTrue(self.m.exec_verdict(d, self.local(), want="spawn")[0])
        self.assertEqual(self.m.exec_verdict(d, self.local(), want="list")[1],
                         "not-mine")

    # V4. 종결 → closed
    def test_v4_closed(self):
        for st in ("done", "cancelled"):
            ok, code, _ = self.m.exec_verdict(self.doc(status=st), self.local())
            self.assertEqual((ok, code), (False, "closed"))

    # V5. 관찰 계정 → observer
    def test_v5_viewer_is_observer(self):
        ok, code, _ = self.m.exec_verdict(self.doc(), self.local(role="viewer"))
        self.assertEqual((ok, code), (False, "observer"))
        # local_facts 가 profile 의 role 을 읽는다
        self.assertEqual(self.m.local_facts("watcher")["role"], "viewer")

    # V7. request 가 아니면 통과
    def test_v7_non_request_passes(self):
        self.assertTrue(self.m.exec_verdict(self.doc(type="knowledge",
                                                     user="other"), self.local())[0])

    # V8. user 없는 옛 문서는 not-mine 이 아니다
    def test_v8_legacy_without_user(self):
        self.assertTrue(self.m.exec_verdict(self.doc(user="", machine=""),
                                            self.local())[0])
        # assignee 가 있으면 그것이 담당자다
        self.assertEqual(self.m.doc_owner({"user": "me", "assignee": "other"}),
                         "other")

    # W1. 스폰 게이트가 판정 함수를 쓰고 spawn.log 에 사유가 남는다
    def test_w1_spawn_gate_uses_verdict_and_logs(self):
        m = self.m
        env = {**os.environ, "S9_ROOT": self.root, "S9_MACHINE": "there",
               "S9_USER": "other"}
        env.pop("S9_SESSION", None)
        out = subprocess.run([S9, "new", "request", "--title", "남의 일",
                              "--summary", "s", "--size", "S", "--goal", "g",
                              "--body", "b", "--user", "other"],
                             capture_output=True, text=True, env=env,
                             stdin=subprocess.DEVNULL)
        rid = out.stdout.split()[0]
        subprocess.run([S9, "status", rid, "in-progress", "--note", "t"],
                       capture_output=True, env=env, stdin=subprocess.DEVNULL)
        subprocess.run([S9, "user", "config", "other", "auto_resume", "on"],
                       capture_output=True, env=env, stdin=subprocess.DEVNULL)
        meta, _ = m.read_doc(m.locate(rid))
        logs, out = [], {}
        with mock.patch.object(m, "resolve_user", lambda *a, **k: "me"), \
                mock.patch.object(m, "_auto_log", lambda s: logs.append(s)), \
                mock.patch.object(m, "doc_status_live", lambda d: "in-progress"), \
                mock.patch.object(m, "doc_commit_drift", lambda d: False):
            r = m._spawn_worker(rid, meta, "p", "rework", out=out)
        self.assertFalse(r)
        self.assertEqual(out.get("blocked"), "elsewhere")
        self.assertTrue(any("SKIP(elsewhere)" in l for l in logs), logs)

    # W4. 드래그 착수 통지는 담당자의 세션에만
    def test_w4_chat_target_by_user(self):
        m = self.m
        os.makedirs(m.STATE, exist_ok=True)
        for sid, u in (("aaaa0001", "me"), ("bbbb0002", "other")):
            with open(os.path.join(m.STATE, f"here__{sid}.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"machine": "here", "session": sid, "user": u,
                           "history": [], "attach_pid": os.getpid()}, f)
        with mock.patch.object(m, "chat_live", lambda b, **k: True):
            self.assertEqual(m.chat_target(None, user="other")["session"], "bbbb0002")
            self.assertEqual(m.chat_target(None, user="me")["session"], "aaaa0001")
            self.assertIsNone(m.chat_target(None, user="nobody"))


if __name__ == "__main__":
    unittest.main()
