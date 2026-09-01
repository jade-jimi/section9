"""규율은 지켜지지 않을 때를 대비하지 못한다 — 기계 게이트가 대비한다
(REQ-20260901-010).

2026-09-01 위임 에이전트의 `git stash` 순환이 남의 미커밋 전이·노트 113건을
작업 트리에서 걷어 갔다(REQ-20260901-004). pre-commit 훅은 커밋만 보고 작업
트리 되돌림은 못 본다 — 그래서 명령 실행 **전**의 PreToolUse(Bash) 훅이
이 저장소를 향한 파괴 명령을 거부한다. 이 파일이 지키는 성질:

  ① 파괴 명령은 exit 2 + 사유(실사고·안전 대안·의식적 우회)로 거부된다.
  ② 읽기·기록 명령과 저장소 밖 명령, `S9_GIT_OK=1` 접두는 지나간다.
  ③ 게이트 고장(비JSON 입력)은 통과다 — 게이트가 모든 Bash 를 막으면
     그날로 게이트가 뽑힌다.
  ④ 원천(hooks.json)에 배선이 있고, 역할 봉투 29종에 보조 문구가 선다.

실행: python3 tests/ git_gate
"""
import glob
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE = os.path.join(ROOT, "bin", "s9-git-gate")


def run(cmd, cwd=None, raw=None):
    payload = raw if raw is not None else json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd},
         "cwd": cwd or ROOT})
    return subprocess.run([GATE], input=payload, capture_output=True,
                          text=True, timeout=30)


class TheGateStands(unittest.TestCase):
    def test_g1_destructive_commands_are_refused(self):
        """① 파괴 명령 일곱 얼굴이 전부 걸린다 — 체인 속에서도."""
        for cmd in ("git stash",
                    "git stash pop",
                    "git stash drop stash@{0}",
                    "cd sub && git stash push -m wip",
                    "git reset --hard HEAD~1",
                    "git checkout -- web/app/card.js",
                    "git checkout .",
                    "git restore web/",
                    "git clean -fd"):
            r = run(cmd)
            self.assertEqual(2, r.returncode, "안 막혔다: %s" % cmd)
            self.assertIn("113건", r.stderr, "사유에 실사고 근거가 없다")
            self.assertIn("git show", r.stderr, "안전 대안이 없다")
            self.assertIn("S9_GIT_OK=1", r.stderr, "우회 안내가 없다")

    def test_g2_reads_and_records_pass(self):
        """② 읽기·기록은 게이트의 일이 아니다."""
        for cmd in ("git status --short",
                    "git log --oneline -5",
                    "git diff --cached",
                    "git show 0042d6dd:vault/x.md",
                    "git stash list",
                    "git stash show -p stash@{0}",
                    "git restore --staged web/app/card.js",
                    "git add -A && git commit -m x",
                    "git push origin main"):
            r = run(cmd)
            self.assertEqual(0, r.returncode,
                             "막을 것이 아닌데 막았다: %s\n%s" % (cmd, r.stderr))

    def test_g3_other_repos_are_none_of_our_business(self):
        """② 저장소 밖의 stash 는 남의 일이다 — cwd 와 -C 둘 다."""
        with tempfile.TemporaryDirectory(prefix="s9gate-") as td:
            self.assertEqual(0, run("git stash", cwd=td).returncode)
            self.assertEqual(
                0, run(f"git -C {td} stash", cwd=td).returncode)
            # -C 로 이 저장소를 겨누면 밖에 있어도 걸린다
            self.assertEqual(
                2, run(f"git -C {ROOT} stash", cwd=td).returncode)

    def test_g4_the_conscious_override_passes(self):
        """② 사람이 명령 앞에 직접 붙인 한 줄만 지나간다."""
        self.assertEqual(0, run("S9_GIT_OK=1 git stash pop").returncode)

    def test_g5_a_broken_payload_does_not_block_the_world(self):
        """③ 판정 불가는 통과 — 게이트 고장이 Bash 전체를 볼모로 잡지 않는다."""
        self.assertEqual(0, run("", raw="this is not json").returncode)
        self.assertEqual(0, run("", raw=json.dumps(
            {"tool_name": "Read", "tool_input": {}})).returncode)

    def test_g6_the_wiring_is_in_the_source(self):
        """④ 원천 배선 — hooks.json 의 PreToolUse Bash 가 게이트를 부른다."""
        with open(os.path.join(ROOT, "harness", "claude", "hooks.json"),
                  encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        pre = hooks.get("PreToolUse") or []
        rows = [h for grp in pre if grp.get("matcher") == "Bash"
                for h in grp.get("hooks", [])]
        self.assertTrue(any("s9-git-gate" in h.get("command", "")
                            for h in rows), "PreToolUse Bash 배선이 없다")

    def test_g7_every_envelope_carries_the_words(self):
        """④ 보조 방어 — 역할 봉투 29종 전부에 금지 문구가 선다."""
        ags = [p for p in glob.glob(os.path.join(
            ROOT, "harness", "claude", "agents", "*.md"))
            if not p.endswith("README.md")]
        self.assertGreaterEqual(len(ags), 29)
        for p in ags:
            with open(p, encoding="utf-8") as f:
                self.assertIn("작업 트리를 되돌리는 git 명령 금지", f.read(),
                              "봉투에 금지 문구가 없다: %s" % p)


if __name__ == "__main__":
    unittest.main()
