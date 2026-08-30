"""--changed 선택 실행 — 같은 시험을 두 번 돌리지 않는다 (REQ-20260830-027 1단계).

사용자: "중복, 반복되는 테스트를 피하고 … 실행건마다의 진행시간 자체를 줄여야
한다." 실측: 2026-08-30 하루에 전체 스위트(523초)가 5회 돌았다 — 그중 몇 번은
코드가 안 바뀐 재확인이었다.

계약: 마지막 **전체 green** 커밋을 기준으로, 그 뒤 바뀐 파일에 닿는 시험만
고른다. 보수 쪽으로 기운다 — 스탬프 없음·git 실패·공용 파일 변경은 전부
전체 폴백(None), 좁게 틀리는 일이 없어야 이 스위치를 믿고 쓴다.

실행: python3 tests/ changed_select
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "__main__.py")


def _load():
    spec = importlib.util.spec_from_loader(
        "s9runner_t", importlib.machinery.SourceFileLoader(
            "s9runner_t", RUNNER))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _git(cwd, *a):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for k in list(env):
        if k.startswith("GIT_DIR") or k.startswith("GIT_WORK"):
            env.pop(k)
    r = subprocess.run(["git", *a], cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(a)}: {r.stderr}")
    return r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="s9chg-")
        self.tests = os.path.join(self.repo, "tests")
        os.makedirs(self.tests)
        _git(self.repo, "init", "-q", "-b", "main")
        self.put("tests/test_alpha.py", "import alpha_mod  # alpha.js 를 본다\n")
        self.put("tests/test_beta.py", "x = 1  # beta.py 만 본다\n")
        self.put("web/alpha.js", "// a\n")
        self.put("bin/s9", "#!x\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "base")
        self.head = _git(self.repo, "rev-parse", "HEAD").strip()
        self.stamp = os.path.join(self.repo, "state", "tests-last-green")
        os.makedirs(os.path.dirname(self.stamp))
        with open(self.stamp, "w") as f:
            f.write(self.head)
        self.m = _load()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def put(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def sel(self):
        return self.m.changed_selection(repo=self.repo, here=self.tests,
                                        stamp=self.stamp)


class TheSelection(Base):
    def test_g1_no_stamp_means_full(self):
        os.unlink(self.stamp)
        self.assertIsNone(self.sel(), "스탬프가 없는데 전체로 안 물러났다")

    def test_g2_no_change_means_nothing(self):
        self.assertEqual(self.sel(), [], "변경이 없는데 돌 것이 있다고 한다")

    def test_g3_changed_test_file_selects_itself(self):
        self.put("tests/test_beta.py", "x = 2\n")
        self.assertEqual(self.sel(), ["test_beta.py"])

    def test_g4_changed_code_selects_mentioning_tests(self):
        self.put("web/alpha.js", "// b\n")
        self.assertEqual(self.sel(), ["test_alpha.py"],
                         "alpha.js 를 본문에 언급한 시험이 안 골라졌다")

    def test_g5_common_file_falls_back_to_full(self):
        self.put("bin/s9", "#!y\n")
        self.assertIsNone(self.sel(), "공용 파일 변경인데 전체로 안 물러났다")

    def test_g7_vault_docs_are_ignored(self):
        self.put("vault/requests/x.md", "메모\n")
        self.put("state/sessions/y.json", "{}\n")
        self.assertEqual(self.sel(), [],
                         "문서·상태 변경이 시험을 유발했다")

    def test_g8_uncommitted_changes_count(self):
        self.put("tests/test_alpha.py", "import alpha_mod  # v2\n")
        # 커밋하지 않는다 — porcelain 경로
        self.assertEqual(self.sel(), ["test_alpha.py"],
                         "미커밋 변경이 안 잡혔다")

    def test_g6_green_stamp_written_and_used(self):
        self.put("tests/test_beta.py", "x = 3\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "beta")
        self.assertEqual(self.sel(), ["test_beta.py"])
        self.m.write_green_stamp(repo=self.repo, stamp=self.stamp)
        self.assertEqual(self.sel(), [],
                         "green 스탬프 갱신 뒤에도 변경이 남아 보인다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
