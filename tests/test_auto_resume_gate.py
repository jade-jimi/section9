"""반려 자동진행 재설계 테스트 (REQ-20260823-081 → 083 클레임 기반 워처).

전이 시점에는 스폰하지 않는다(PENDING). serve 워처(rework_watch_tick)가 유예 후
미클레임 반려를 무인 스폰: 담당 세션 조용 → --resume, 활성인데 안 집음 → 새 세션.
격리: S9_ROOT=mktemp, subprocess.Popen 모킹(실스폰 방지).
실행: python3 tests/test_auto_resume_gate.py
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess as real_subprocess
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
FULLSID = "eeee5555-aaaa-bbbb-cccc-dddddddddddd"


class TestReworkWatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9auto-")
        os.environ["S9_ROOT"] = cls.tmp        # 모듈 import 전에 고정
        os.environ["S9_MACHINE"] = "testbox"
        os.environ.pop("S9_SESSION", None)
        os.environ.pop("S9_AUTO_RESUME", None)
        os.environ.pop("S9_AUTO_RESUME_DISABLE", None)
        spec = importlib.util.spec_from_loader(
            "s9mod", importlib.machinery.SourceFileLoader("s9mod", S9))
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

        cls.env = {**os.environ}

        def cli(sess, *argv):
            env = dict(cls.env)
            if sess:
                env["S9_SESSION"] = sess
            r = real_subprocess.run([S9, *argv], capture_output=True, text=True,
                                    env=env, timeout=15)
            if r.returncode != 0:
                raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
            return r.stdout
        cls.cli = staticmethod(cli)

        cli(None, "init")
        cli(None, "user", "add", "alice")
        cli(None, "user", "add", "bob")
        cli(None, "user", "config", "alice", "auto_resume", "on")
        cli(None, "user", "config", "alice", "auto_resume_cooldown_sec", "0")
        cli(None, "user", "config", "alice", "auto_resume_global_per_hour", "50")
        cli(None, "user", "config", "alice", "auto_resume_global_per_day", "100")
        # 담당 세션 바인딩 (transcript = 전체 SID 파일명 + cwd)
        cls.transcript = os.path.join(cls.tmp, FULLSID + ".jsonl")
        with open(cls.transcript, "w") as f:
            f.write("{}\n")
        cli("eeee5555", "bind", "transcript_path", cls.transcript)
        cli("eeee5555", "bind", "cwd", cls.tmp)

        def rejected(title, user="alice"):
            doc = cli("eeee5555", "new", "request", "--title", title, "--summary",
                      "t", "--goal", "t", "--size", "S", "--user", user, "--body", "x").split()[0]
            cli("eeee5555", "status", doc, "in-progress", "--note", "t")
            cli("eeee5555", "note", doc, "- [x] S1. 검증됨\n- [x] S2. 재검증됨",
                "--label", "tdd")
            cli("eeee5555", "status", doc, "review", "--note", "t")
            cli(None, "status", doc, "in-progress", "--note", "반려 사유")
            return doc
        cls.rejected = staticmethod(rejected)

    def spawn_log(self):
        try:
            with open(os.path.join(self.tmp, "state", "auto_resume",
                                   "spawn.log")) as f:
                return f.read()
        except OSError:
            return ""

    def tick(self, grace):
        calls = []

        def fake_popen(argv, **kw):
            calls.append(argv)
            return mock.Mock()
        with mock.patch("subprocess.Popen", side_effect=fake_popen):
            spawned = self.mod.rework_watch_tick(grace=grace)
        return spawned, calls

    def test_watcher_flow(self):
        # W6. 반려 전이 시점: 스폰 없이 PENDING만
        R = self.rejected("pending-case")
        # W8 (REQ-20260824-009). 반려는 검증 무효화 — 체크된 TDD가 초기화된다
        import glob
        doc = glob.glob(os.path.join(self.tmp, "vault", "requests", "**",
                                     R + ".md"), recursive=True)[0]
        with open(doc) as f:
            body = f.read()
        self.assertNotIn("- [x]", body, body)
        self.assertIn("- [ ] S1. 검증됨", body)
        log = self.spawn_log()
        self.assertIn(f"PENDING {R}", log, log)
        self.assertNotIn(f"SPAWN", log.split(f"PENDING {R}")[-1][:1], log)

        # W2. 유예 이내 → 스폰 안 함
        spawned, calls = self.tick(grace=3600)
        self.assertNotIn(R, spawned, (spawned, calls))

        # W4. 유예 경과 + 미클레임 + 담당 세션 조용 → --resume 스폰
        old = time.time() - 600
        os.utime(self.transcript, (old, old))
        spawned, calls = self.tick(grace=0)
        self.assertIn(R, spawned, (spawned, self.spawn_log()))
        argv = [a for a in calls if R in " ".join(map(str, a))]
        self.assertTrue(argv and "--resume" in argv[0] and FULLSID in argv[0], calls)
        self.assertIn(f"SPAWN(resume) {R}", self.spawn_log())
        # 스폰 프롬프트가 클레임 지시를 포함해야 한다 — 훅의 sid 주입(test_audit_prompt
        # S7)과 맞물려 "작업자가 클레임 가능"이라는 프로세스 간 이음새를 닫는다
        # (REQ-20260824-004: 이 이음새가 무검증이라 중복 스폰 결함이 통과했었다)
        prompt_arg = [s for s in argv[0] if isinstance(s, str) and R in s][0]
        self.assertIn(f"last {R}", prompt_arg)
        # A1/A2 (REQ-20260824-005): allowlist 봉투 + 패치 전달 지시
        self.assertIn("--allowedTools", argv[0], argv[0])
        self.assertTrue(any(isinstance(s, str) and s.startswith("Bash(")
                            and s.endswith("/bin/s9:*)") for s in argv[0]), argv[0])
        self.assertIn("--label patch", prompt_arg)

        # W3. 클레임된 REQ → 스폰 안 함 (신선한 세션의 active_reqs 등록)
        os.utime(self.transcript, None)  # 세션 활성화
        self.cli("eeee5555", "last", R, "--add")
        spawned, calls = self.tick(grace=0)
        self.assertNotIn(R, spawned, spawned)

        # W5. 유예 경과 + 미클레임 + 담당 세션 활성 → 새 세션(-p, no --resume)
        R2 = self.rejected("live-unclaimed")
        os.utime(self.transcript, None)
        spawned, calls = self.tick(grace=0)
        self.assertIn(R2, spawned, (spawned, self.spawn_log()))
        argv = [a for a in calls if R2 in " ".join(map(str, a))]
        self.assertTrue(argv and "--resume" not in argv[0], calls)
        self.assertIn(f"SPAWN(fresh) {R2}", self.spawn_log())
        self.cli("eeee5555", "last", R2, "--add")

        # W9 (REQ-20260824-010). TDD 미완료 request는 review 진입 거부, --force 예외
        g = self.cli("eeee5555", "new", "request", "--title", "guard", "--summary",
                     "t", "--goal", "t", "--size", "S", "--user", "alice", "--body", "x").split()[0]
        self.cli("eeee5555", "status", g, "in-progress", "--note", "t")
        self.cli("eeee5555", "note", g, "- [ ] S1. 미검증", "--label", "tdd")
        env = dict(self.env); env["S9_SESSION"] = "eeee5555"
        r = real_subprocess.run([S9, "status", g, "review", "--note", "t"],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TDD 미완료 0/1", r.stdout + r.stderr)
        self.cli("eeee5555", "status", g, "review", "--note", "사용자 판정만 남음",
                 "--force")

        # W10 (REQ-20260824-028). 승인 메모 → 후속 무인 스폰(1회), 소비 후 재스폰 없음
        ap = self.cli("eeee5555", "new", "request", "--title", "approve-case",
                      "--summary", "t", "--goal", "t", "--size", "S",
                      "--user", "alice", "--body", "x").split()[0]
        self.cli("eeee5555", "status", ap, "in-progress", "--note", "t")
        self.cli("eeee5555", "note", ap, "- [x] S1. ok", "--label", "tdd")
        self.cli("eeee5555", "status", ap, "review", "--note", "t")
        self.cli(None, "status", ap, "done", "--note", "승인: 후속으로 구현까지 진행해줘")
        spawned, calls = self.tick(grace=0)
        self.assertIn(ap, spawned, (spawned, self.spawn_log()))
        argv = [a for a in calls if ap in " ".join(map(str, a))][0]
        p = [s for s in argv if isinstance(s, str) and ap in s][0]
        self.assertIn("승인 후속", p)
        self.assertIn("구현까지 진행해줘", p)
        self.assertIn("<<메모>>", p)
        spawned, _ = self.tick(grace=0)
        self.assertNotIn(ap, spawned, spawned)  # 소비됨 — 재스폰 없음

        # W1. 반려 아닌 in-progress(open→in-progress)는 워처 대상 아님
        plain = self.cli("eeee5555", "new", "request", "--title", "plain",
                         "--summary", "t", "--size", "S", "--user", "alice",
                         "--body", "x").split()[0]
        self.cli(None, "status", plain, "in-progress", "--note", "t")
        spawned, _ = self.tick(grace=0)
        self.assertNotIn(plain, spawned, spawned)

        # W11 (REQ-20260824-030). goal 미기재 request는 done 거부, 기재 후 허용
        ng = self.cli("eeee5555", "new", "request", "--title", "goalless",
                      "--summary", "t", "--size", "S", "--user", "alice",
                      "--body", "x").split()[0]
        self.cli("eeee5555", "status", ng, "in-progress", "--note", "t")
        env = dict(self.env); env["S9_SESSION"] = "eeee5555"
        r = real_subprocess.run([S9, "status", ng, "done", "--note", "t"],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("goal 미기재", r.stdout + r.stderr)
        self.cli(None, "set", ng, "--goal", "충족 기준")
        self.cli("eeee5555", "status", ng, "done", "--note", "goal 충족: 기준 만족")

        # W7. opt-in off(bob) → 스폰 안 함
        R3 = self.rejected("optout-case", user="bob")
        spawned, _ = self.tick(grace=0)
        self.assertNotIn(R3, spawned, spawned)

        # F1/F3 (REQ-20260824-012). auto_resume_apply=on → 상향 봉투 + 완결 지시
        self.cli(None, "user", "config", "alice", "auto_resume_apply", "on")
        R4 = self.rejected("apply-case")
        spawned, calls = self.tick(grace=0)
        self.assertIn(R4, spawned, (spawned, self.spawn_log()))
        argv = [a for a in calls if R4 in " ".join(map(str, a))][0]
        self.assertIn("--permission-mode", argv)
        self.assertIn("acceptEdits", argv)
        self.assertTrue(any(isinstance(s, str) and s.startswith("Bash(python3 tests/")
                            for s in argv), argv)
        p = [s for s in argv if isinstance(s, str) and R4 in s][0]
        self.assertIn("무인 적용 모드", p)
        self.assertIn("web/·vault/·tests/", p)
        self.assertIn("<<참고>>", p)  # F3: 노트 격리 프레이밍 유지
        self.cli("eeee5555", "last", R4, "--add")
        # F2: off 오너(bob 대상 아님 — alice off 복원 후 제한 봉투 회귀 확인)
        self.cli(None, "user", "config", "alice", "auto_resume_apply", "")
        R5 = self.rejected("restricted-again")
        spawned, calls = self.tick(grace=0)
        self.assertIn(R5, spawned, spawned)
        argv = [a for a in calls if R5 in " ".join(map(str, a))][0]
        self.assertNotIn("--permission-mode", argv)
        p = [s for s in argv if isinstance(s, str) and R5 in s][0]
        self.assertIn("제한 권한", p)

    # D1 (REQ-20260825-039): 대시보드 드래그 착수(open→in-progress [via
    # dashboard])도 워처 후보 — 유예 후 미클레임이면 스폰. CLI 착수는 제외.
    def test_drag_start_spawns(self):
        def new_open(title):
            return self.cli("eeee5555", "new", "request", "--title", title,
                            "--summary", "t", "--goal", "t", "--size", "S",
                            "--user", "alice", "--body", "x").split()[0]
        old = time.time() - 600
        os.utime(self.transcript, (old, old))
        # 드래그 착수(via dashboard 마커) → 스폰 대상
        D = new_open("drag-start")
        self.cli(None, "status", D, "in-progress", "--note", "drag 이동 [via dashboard]")
        spawned, calls = self.tick(grace=0)
        self.assertIn(D, spawned, (spawned, self.spawn_log()))
        # CLI 착수(마커 없음) → 그 세션이 작업 중 — 스폰 제외
        C = new_open("cli-start")
        self.cli("eeee5555", "status", C, "in-progress", "--note", "착수")
        spawned, calls = self.tick(grace=0)
        self.assertNotIn(C, spawned, spawned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
