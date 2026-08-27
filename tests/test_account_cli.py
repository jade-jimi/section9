"""계정을 사람이 이름 지어 만들지 않는다 (REQ-20260827-033-62x6).

사용자 지적: "CLAUDE_CONFIG_DIR=~/.claude-profiles/<이름> claude — 이 내용이 이해가
잘 가지 않는다. 저건 알아서 해주지 않는건가? 프로필을 왜 만드는거지? … <이름>은
아무거나라고 하는데 아무 클로드 계정인건가 하네스의 계정인건가 내 개인 이메일인건가
내 이름인건가 별명인건가 무슨 의미로 사용하는건가?"

전부 맞는 지적이다. 그 이름은 **아무 의미도 없었다** — 그냥 폴더 이름이고, 뜻 없는
것을 사람에게 지어내라고 시켰다.

확인한 사실: `CLAUDE_CONFIG_DIR` 을 주면 `.claude.json` 도 그 안으로 들어간다(빈
디렉토리에 `claude config ls` 를 돌려 직접 봤다). 그 파일에 `oauthAccount.
emailAddress` 가 있다. **로그인만 하면 그 프로필이 어느 계정인지 시스템이 스스로
안다.** 그러니 사람이 이름을 지을 이유가 없다.

그래서 `s9 account` 가 이름을 짓는다 — 로그인이 끝나면 그 계정 이메일로.

실행: python3 tests/ account_cli
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


def _load(name, path):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_account(cfg_dir, email):
    """그 설정 디렉토리에 로그인된 계정을 심는다 (실제 파일 모양과 같게)."""
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, ".claude.json"), "w",
              encoding="utf-8") as f:
        json.dump({"oauthAccount": {"emailAddress": email,
                                    "accountUuid": "u-1"}}, f)


class AccountList(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="s9acc-")
        self.root = tempfile.mkdtemp(prefix="s9accroot-")
        self.env = {**os.environ, "HOME": self.home, "S9_ROOT": self.root,
                    "S9_MACHINE": "testbox"}
        self.env.pop("S9_SESSION", None)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        subprocess.run([S9, "init"], capture_output=True, env=self.env,
                       timeout=20)
        # 기본 설정 디렉토리는 `.claude.json` 이 **바깥**(~/.claude.json)에 있다 —
        # CLAUDE_CONFIG_DIR 을 줄 때만 안으로 들어간다 (실환경에서 확인).
        with open(os.path.join(self.home, ".claude.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"oauthAccount": {"emailAddress": "now@example.com"}}, f)
        os.makedirs(os.path.join(self.home, ".claude"), exist_ok=True)

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    # N1. 지금 쓰는 계정이 이메일로 보이고, 지금 쓴다고 표시된다
    def test_n1_current_account_listed(self):
        out = self.cli("account", "ls")
        self.assertIn("now@example.com", out)
        self.assertIn("지금", out, out)

    # N2. 프로필도 그 안의 계정 이메일로 보인다 — 폴더 이름이 아니라
    def test_n2_profiles_listed_by_email(self):
        write_account(os.path.join(self.home, ".claude-profiles", "aaa"),
                      "other@example.com")
        out = self.cli("account", "ls")
        self.assertIn("other@example.com", out)

    # B1. 로그인 전 프로필은 그렇게 말한다 — 빈칸으로 두지 않는다
    def test_b1_unlogged_profile_says_so(self):
        os.makedirs(os.path.join(self.home, ".claude-profiles", "empty"),
                    exist_ok=True)
        out = self.cli("account", "ls")
        self.assertIn("로그인 전", out, out)


class AccountAdd(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="s9accadd-")
        self.root = tempfile.mkdtemp(prefix="s9accaddroot-")
        self.env = {**os.environ, "HOME": self.home, "S9_ROOT": self.root,
                    "S9_MACHINE": "testbox", "S9_ACCOUNT_DRYRUN": "1"}
        self.env.pop("S9_SESSION", None)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        subprocess.run([S9, "init"], capture_output=True, env=self.env,
                       timeout=20)

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    # N3. 이름을 안 줘도 된다 — 디렉토리를 만들고 그 환경으로 claude 를 띄운다
    def test_n3_add_without_label(self):
        out = self.cli("account", "add")
        self.assertIn("CLAUDE_CONFIG_DIR", out, out)
        base = os.path.join(self.home, ".claude-profiles")
        self.assertTrue(os.path.isdir(base), out)
        self.assertTrue(os.listdir(base), "프로필 디렉토리가 안 만들어졌다")

    # F1. 이미 있는 이름으로 만들려 하면 덮지 않는다
    def test_f1_existing_label_refused(self):
        os.makedirs(os.path.join(self.home, ".claude-profiles", "work"),
                    exist_ok=True)
        out = self.cli("account", "add", "work", expect=1)
        self.assertIn("work", out)


class AccountRename(unittest.TestCase):
    """N4 — 로그인이 끝나면 그 계정 이메일로 이름이 정해진다.

    사람이 이름을 지어낼 필요가 없다는 것이 이 요청의 전부다.
    """

    def setUp(self):
        self.old = os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.m = _load("s9_acc_mod", S9)

    def tearDown(self):
        if self.old is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = self.old

    def test_n4_renamed_to_account(self):
        base = tempfile.mkdtemp(prefix="s9accren-")
        prof = os.path.join(base, "새-계정")
        write_account(prof, "Second.User@Example.com")
        final = self.m.account_settle(prof)
        self.assertTrue(os.path.isdir(final), final)
        self.assertIn("second.user", os.path.basename(final).lower(), final)
        self.assertFalse(os.path.isdir(prof), "옛 이름이 남았다")

    # B2. 로그인을 안 하고 나갔으면 이름을 바꾸지 않는다 — 지어낼 근거가 없다
    def test_b2_no_login_keeps_placeholder(self):
        base = tempfile.mkdtemp(prefix="s9accren2-")
        prof = os.path.join(base, "새-계정")
        os.makedirs(prof, exist_ok=True)
        self.assertEqual(self.m.account_settle(prof), prof)

    # B3. 같은 계정으로 또 만들면 기존 자리를 그대로 쓴다 — 중복을 만들지 않는다
    def test_b3_same_account_reuses(self):
        base = tempfile.mkdtemp(prefix="s9accren3-")
        write_account(os.path.join(base, "dup@example.com"), "dup@example.com")
        prof = os.path.join(base, "새-계정")
        write_account(prof, "dup@example.com")
        final = self.m.account_settle(prof)
        self.assertEqual(os.path.basename(final), "dup@example.com", final)


if __name__ == "__main__":
    unittest.main()
