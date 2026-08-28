"""미러 하나로 다른 머신에서 세션을 되살린다 (REQ-20260823-036 · DOC-20260823-002).

이 REQ 가 실증한 사실은 하나다 — `claude --resume <SID>` 는
`~/.claude/projects/<cwd-key>/<전체SID>.jsonl` **파일 하나만** 보고 맥락을
이어받는다. 그래서 section9 의 streams 미러를 그 이름 그대로, 그 자리에
갖다 놓으면 세션이 없는 머신에서도 대화가 이어진다. 실증은 손으로 했고,
구현(`s9 resume`)은 남았지만 그 경로를 지키는 테스트는 없었다.

지켜야 하는 것은 두 줄짜리 규칙인데, 둘 다 조용히 깨진다:

1. **cwd-key 는 `/` 만 `-` 로 바꾸고 점은 그대로 둔다.** 처음 문서에는
   `[/.]` 를 모두 치환한다고 적었다가 정정했다(DOC-20260823-002 정정 노트).
   점을 함께 바꾸면 `/tmp/tmp.ojW6` 같은 경로에서 없는 디렉토리를 만들고,
   claude 는 "그런 세션 없음"이라며 **맥락 없이 새로 시작한다** — 복원한
   줄 알았는데 아무것도 이어지지 않는 실패다.
2. **파일 이름은 8자 축약이 아니라 전체 SID.** (미러를 만드는 쪽은
   test_mirror_append 의 r1 이 지킨다. 여기서는 되살리는 쪽을 본다.)

보안 규율도 함께 못 박는다(DOC-20260823-003): 확인 없이 실행하지 않고,
있는 native transcript 를 덮지 않고, cwd 를 **파일 내용에서 취하지 않는다**.
vault 는 여러 머신이 함께 쓰므로, 스트림 파일에 적힌 cwd 를 믿으면 남이 적어
넣은 디렉토리에서 claude 가 돈다.

실행: python3 tests/ resume_restore
"""
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

SID = "18093278-22fa-413c-b6f4-f33d6924c8c1"


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9rr-")
        self.home = tempfile.mkdtemp(prefix="s9rr-home-")
        # 점이 든 cwd — 정정된 key 규칙이 깨지면 여기서 어긋난다
        self.cwd = tempfile.mkdtemp(prefix="s9rr-", suffix=".dot")
        self.bin = tempfile.mkdtemp(prefix="s9rr-bin-")
        self.argv_log = os.path.join(self.bin, "argv.json")
        fake = os.path.join(self.bin, "claude")
        with open(fake, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\n"
                    "import json, os, sys\n"
                    "json.dump({'argv': sys.argv[1:], 'cwd': os.getcwd()},\n"
                    "          open(os.environ['S9RR_ARGV'], 'w'))\n")
        os.chmod(fake, 0o755)
        self.env = {**os.environ, "S9_ROOT": self.root, "HOME": self.home,
                    "S9_MACHINE": "testbox", "S9_USER": "alice",
                    "S9_PORT": "1", "S9RR_ARGV": self.argv_log,
                    "PATH": self.bin + os.pathsep + os.environ["PATH"]}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=60)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def mirror(self, sid=SID, cwd_in_file="/opt/attacker"):
        """미러 한 벌 — 파일 안에는 남이 적어 넣었을 수 있는 cwd 도 둔다."""
        d = os.path.join(self.root, "users", "alice", "streams")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, sid + ".jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": sid, "cwd": cwd_in_file,
                                "type": "user"}) + "\n")
        return p

    @property
    def key(self):
        return self.cwd.replace("/", "-")

    @property
    def dst(self):
        return os.path.join(self.home, ".claude", "projects", self.key,
                            SID + ".jsonl")


class RestorePath(Base):
    """어디에 갖다 놓는가 — 이 REQ 가 실증한 그 경로 그대로여야 한다."""

    # N1. 복원 자리는 <HOME>/.claude/projects/<점 보존 key>/<전체SID>.jsonl
    def test_n1_key_keeps_dots(self):
        self.mirror()
        out = self.cli("resume", SID[:8], "--cwd", self.cwd, expect=1)
        self.assertIn(self.dst, out,
                      "복원 자리가 실증된 경로와 다르다 (점 치환 회귀 의심)")
        self.assertIn(".dot", self.key)          # 시험 자체가 무의미해지지 않게

    # N2. --yes 면 실제로 복원하고, 전체 SID 로 resume 을 부른다
    def test_n2_restores_and_execs(self):
        self.mirror()
        self.cli("resume", SID[:8], "--cwd", self.cwd, "--yes")
        self.assertTrue(os.path.exists(self.dst), "미러가 정규 위치에 없다")
        with open(self.dst, encoding="utf-8") as f:
            self.assertIn(SID, f.read())
        with open(self.argv_log, encoding="utf-8") as f:
            got = json.load(f)
        self.assertEqual(got["argv"], ["--resume", SID],
                         "8자 축약으로 resume 하면 claude 가 못 찾는다")
        self.assertEqual(os.path.realpath(got["cwd"]),
                         os.path.realpath(self.cwd))

    # N3. --cwd 를 안 주면 **같은 머신의 binding** 에서 가져온다
    def test_n3_cwd_from_binding(self):
        tp = os.path.join(self.home, SID + ".jsonl")
        open(tp, "w").close()
        b = os.path.join(self.root, "state", "sessions",
                         f"testbox__{SID}.json")
        os.makedirs(os.path.dirname(b), exist_ok=True)
        with open(b, "w", encoding="utf-8") as f:
            json.dump({"transcript_path": tp, "cwd": self.cwd}, f)
        self.mirror()
        out = self.cli("resume", SID[:8], expect=1)
        self.assertIn(self.dst, out)


class Guards(Base):
    """실행하기 전에 멈추는 자리들 — 없으면 조용히 큰 일이 난다."""

    # R1. 확인 없이는 아무것도 하지 않는다 (자동 exec 금지)
    def test_r1_no_yes_no_write(self):
        self.mirror()
        out = self.cli("resume", SID, "--cwd", self.cwd, expect=1)
        self.assertIn("--yes", out)
        self.assertFalse(os.path.exists(self.dst),
                         "확인 전에 이미 복원했다")
        self.assertFalse(os.path.exists(self.argv_log), "확인 전에 실행했다")

    # R2. 살아 있는 native transcript 는 덮지 않는다
    def test_r2_native_not_overwritten(self):
        self.mirror()
        os.makedirs(os.path.dirname(self.dst), exist_ok=True)
        with open(self.dst, "w", encoding="utf-8") as f:
            f.write("native\n")
        self.cli("resume", SID, "--cwd", self.cwd, "--yes", expect=1)
        with open(self.dst, encoding="utf-8") as f:
            self.assertEqual(f.read(), "native\n", "남의 세션을 덮어썼다")

    # R3. 파일 안의 cwd 는 믿지 않는다 — vault 는 여러 머신이 함께 쓴다
    def test_r3_cwd_in_file_ignored(self):
        self.mirror(cwd_in_file=self.cwd)
        out = self.cli("resume", SID, expect=1)
        self.assertNotIn(self.key, out,
                         "스트림 파일에 적힌 cwd 를 그대로 썼다")
        self.assertFalse(os.path.exists(self.argv_log))

    # R4. 미러를 껐으면 되살릴 것이 없다 — 이유를 말한다
    def test_r4_mirror_off(self):
        self.mirror()
        d = os.path.join(self.root, "users", "alice", "config")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"stream_mirror": "off"}, f)
        out = self.cli("resume", SID, "--cwd", self.cwd, "--yes", expect=1)
        self.assertIn("stream_mirror", out)
        self.assertFalse(os.path.exists(self.dst))

    # R5. 없는 세션은 있는 것처럼 굴지 않는다
    def test_r5_missing_stream(self):
        out = self.cli("resume", "deadbeef", "--cwd", self.cwd, "--yes",
                       expect=1)
        self.assertIn("스트림 없음", out)


if __name__ == "__main__":
    unittest.main()
