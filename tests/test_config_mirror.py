"""설정은 옮기되 권한은 싣지 않는다 (REQ-20260827-045-62x6).

사용자 제안: "permission도 하네스 내부에서 미러를 뜨고 있다가 다른 머신에 가서도
덮어쓸 수 있게 하는건 어때?"

**막아야 할 곳은 적용이 아니라 적재다.** 처음 판단은 "미러는 하되 적용만 수동"
이었는데 그건 부족하다 — 이 리포는 공개다(REQ-20260827-036). 적용을 늦춰도
**싣는 순간** "어느 머신이 무엇을 확인 없이 실행하는가"가 공개 기록이 된다.
그건 설정이 아니라 공격 표면 지도다.

그래서 세 층으로 가른다.

    자동 복원   model · theme · UI 취향       리포로 흐른다
    수동 반출   permissions                   리포 밖으로만, 사람이 손으로 옮긴다
    안 옮김     자격증명·토큰                  REQ-20260827-035 자리

env 는 통째로 싣지 않는다 — 거기 API 키가 흔히 들어앉는다. 이름을 적어 넣는 것이
사람의 행위여야 한다(기본 허용목록은 비어 있다).

실행: python3 tests/ config_mirror
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class ConfigMirror(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9cfg-")
        self.home = tempfile.mkdtemp(prefix="s9cfghome-")
        self.cfgdir = os.path.join(self.home, ".claude")
        os.makedirs(self.cfgdir, exist_ok=True)
        self.settings = os.path.join(self.cfgdir, "settings.json")
        self.write_settings({
            "model": "claude-opus-5",
            "theme": "dark",
            "remoteControlAtStartup": True,
            "env": {"XDG_RUNTIME_DIR": "/run/x", "MY_API_KEY": "sk-secret-123"},
            "permissions": {"allow": ["Bash(git push:*)"]},
            "hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": "x"}]}]},
        })
        self.env = {**os.environ, "S9_ROOT": self.root, "HOME": self.home,
                    "S9_MACHINE": "testbox", "S9_USER": "alice",
                    "CLAUDE_CONFIG_DIR": self.cfgdir}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")

    def write_settings(self, d):
        with open(self.settings, "w", encoding="utf-8") as f:
            json.dump(d, f)

    def read_settings(self):
        with open(self.settings, encoding="utf-8") as f:
            return json.load(f)

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    @property
    def mirror(self):
        return os.path.join(self.root, "users", "alice", "config", "harness",
                            "claude.json")

    # 1. export 기본 출력에 permissions 가 들어가지 않는다
    def test_1_export_excludes_permissions(self):
        self.cli("config", "export")
        with open(self.mirror, encoding="utf-8") as f:
            d = json.load(f)
        self.assertNotIn("permissions", d, d)
        self.assertEqual(d.get("model"), "claude-opus-5")
        self.assertEqual(d.get("theme"), "dark")

    # 2. env 는 허용목록 밖 키를 떨어뜨린다 — 값도 남지 않는다
    def test_2_export_drops_unlisted_env(self):
        self.cli("config", "export")
        raw = open(self.mirror, encoding="utf-8").read()
        self.assertNotIn("MY_API_KEY", raw)
        self.assertNotIn("sk-secret-123", raw)

    # 3. apply --dry-run 은 고치지 않고 diff 만 찍는다
    def test_3_dry_run_changes_nothing(self):
        self.cli("config", "export")
        before = self.read_settings()
        self.write_settings({**before, "theme": "light"})
        out = self.cli("config", "apply", "--dry-run")
        self.assertIn("theme", out)
        self.assertEqual(self.read_settings().get("theme"), "light",
                         "--dry-run 인데 파일을 고쳤다")

    # 4. permissions 가 든 파일은 --yes 없이 적용되지 않는다
    def test_4_permissions_need_yes(self):
        p = os.path.join(self.root, "hand-carried.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"permissions": {"allow": ["Bash(rm:*)"]}}, f)
        out = self.cli("config", "apply", p, expect=1)
        self.assertIn("확인 없이", out, out)
        self.assertNotIn("Bash(rm:*)",
                         json.dumps(self.read_settings(), ensure_ascii=False))

    # 5. hooks 는 건드리지 않는다 — s9-install 재생성 소관이다
    def test_5_hooks_untouched(self):
        self.cli("config", "export")
        self.write_settings({**self.read_settings(), "theme": "light"})
        self.cli("config", "apply", "--yes")
        self.assertIn("Stop", self.read_settings().get("hooks", {}),
                      "apply 가 hooks 를 지웠다")

    # 6. 커밋 가드: 미러 파일에 permissions 가 있으면 막는다
    #    이게 없으면 손으로 한 번 붙여 넣는 것만으로 경계가 조용히 사라진다
    def test_6_guard_blocks_permissions_in_mirror(self):
        from importlib import machinery, util
        spec = util.spec_from_loader(
            "s9_cfgguard", machinery.SourceFileLoader(
                "s9_cfgguard", os.path.join(HERE, "..", "bin", "s9")))
        m = util.module_from_spec(spec)
        spec.loader.exec_module(m)
        blob = ('+++ b/users/alice/config/harness/claude.json\n'
                '+  "permissions": {"allow": ["Bash(rm:*)"]}\n')
        hits = m.config_leak(["users/alice/config/harness/claude.json"], blob)
        self.assertTrue(hits, "권한이 실린 미러가 커밋을 통과한다")

    # 6b. 엉뚱하게 걸리지 않는다 — permissions 를 다루는 *코드*를 미러와 함께
    #     커밋해도 통과해야 한다. 실제로 이 기능의 첫 커밋이 자기 자신에게 걸렸다.
    #     우회를 가르치는 가드는 없느니만 못하다.
    def test_6b_guard_scopes_to_the_mirror_file(self):
        from importlib import machinery, util
        spec = util.spec_from_loader(
            "s9_cfgguard2", machinery.SourceFileLoader(
                "s9_cfgguard2", os.path.join(HERE, "..", "bin", "s9")))
        m = util.module_from_spec(spec)
        spec.loader.exec_module(m)
        blob = ('diff --git a/bin/s9 b/bin/s9\n'
                '--- a/bin/s9\n+++ b/bin/s9\n'
                '+CONFIG_SKIP_KEYS = {"hooks", "permissions"}\n'
                'diff --git a/users/alice/config/harness/claude.json b/x\n'
                '--- /dev/null\n'
                '+++ b/users/alice/config/harness/claude.json\n'
                '+{"model": "claude-opus-5", "theme": "dark"}\n')
        hits = m.config_leak(
            ["bin/s9", "users/alice/config/harness/claude.json"], blob)
        self.assertFalse(hits, hits)

    # 7. CLAUDE_CONFIG_DIR 을 따른다 — 프로필 세션에서도 맞는 파일을 읽는다
    def test_7_honors_config_dir(self):
        prof = os.path.join(self.home, ".claude-profiles", "second")
        os.makedirs(prof, exist_ok=True)
        with open(os.path.join(prof, "settings.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"model": "profile-model", "theme": "light"}, f)
        env = {**self.env, "CLAUDE_CONFIG_DIR": prof}
        subprocess.run([S9, "config", "export"], capture_output=True,
                       env=env, timeout=30)
        with open(self.mirror, encoding="utf-8") as f:
            self.assertEqual(json.load(f).get("model"), "profile-model")

    # 8. --with-permissions 는 리포 밖으로만 쓰고 권한을 좁힌다
    def test_8_permissions_export_outside_repo(self):
        out = os.path.join(self.home, "perm.json")
        self.cli("config", "export", "--with-permissions", "--out", out)
        self.assertTrue(os.path.exists(out))
        with open(out, encoding="utf-8") as f:
            self.assertIn("permissions", json.load(f))
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)
        # 리포 쪽 미러에는 여전히 없다
        with open(self.mirror, encoding="utf-8") as f:
            self.assertNotIn("permissions", json.load(f))


if __name__ == "__main__":
    unittest.main()
