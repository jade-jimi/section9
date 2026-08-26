"""커밋이 남의 작업을 삼키는 것을 막는가 (REQ-20260826-021-62x6).

2026-08-26 21:42. 리드가 `git add web/index.html` 로 커밋하면서 같은 파일을
고치던 무인 워커의 진행 중 편집을 함께 담았다. 나쁜 것은 충돌이 아니라 **조용한
성공**이다 — 두 변경 모두 문법적으로 멀쩡해 커밋도 되고 서버도 떴다. 그런데
합쳐진 상태는 버튼이 한 이름을 내고 핸들러가 다른 이름을 읽는 반쪽이라, 원래
고치려던 결함이 그대로 남았다. **같은 커밋에 들어 있던 테스트조차 통과하지
못했다 — 돌리기만 했으면 잡혔다.**

그래서 커밋 훅(s9-guard)에 게이트 둘을 둔다.
  ① 무인 워커가 도는데 '방금 만져진' 파일을 담으려 하면 막는다. `git add <경로>`
     는 "내 변경"이 아니라 "그 파일의 지금 상태"를 담기 때문이다.
  ② 커밋에 테스트 파일이 있으면 그것만이라도 돌린다. 전체 스위트는 2분이라 매
     커밋에 물리면 규율이 먼저 죽는다 — 담긴 것으로 좁힌다.

둘 다 사람의 기억이 아니라 훅이 강제한다. 규율만으로 될 일이었으면 오늘 넷이
나지 않았다.

실행: python3 tests/ commit_gate
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "..", "bin", "s9-guard")


def _load():
    spec = importlib.util.spec_from_loader(
        "s9guard", importlib.machinery.SourceFileLoader("s9guard", GUARD))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CommitGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.tmp = tempfile.mkdtemp(prefix="s9gate-")

    def _fresh_file(self, name="web/index.html"):
        p = os.path.join(self.m.ROOT, name)
        return name if os.path.exists(p) else None

    def test_g1_worker_plus_fresh_file_blocks(self):
        """G1. 워커가 도는데 방금 바뀐 파일을 담으면 막는다 (21:42 실사고)."""
        import time
        rel = "tests/test_commit_gate.py"          # 방금 쓴 이 파일
        os.utime(os.path.join(self.m.ROOT, rel), None)
        with mock.patch.object(self.m, "live_workers",
                               return_value=["- REQ-x (무인 작업자 pid 1, 1분째)"]):
            with self.assertRaises(SystemExit) as cm:
                self.m.concurrent_gate([rel])
        self.assertEqual(cm.exception.code, 1)

    def test_g2_no_worker_no_block(self):
        """G2. 워커가 없으면 막지 않는다 — 혼자 일할 때까지 느리게 만들면
        규율이 미움받고 곧 꺼진다."""
        rel = "tests/test_commit_gate.py"
        with mock.patch.object(self.m, "live_workers", return_value=[]):
            self.m.concurrent_gate([rel])          # 예외 없이 통과

    def test_g3_stale_file_is_not_in_flight(self):
        """G3. 워커가 돌아도 오래된 파일은 진행 중이 아니다.

        모든 커밋을 막으면 우회가 습관이 되고, 습관이 되면 게이트가 없는 것과
        같다.
        """
        rel = "tests/test_commit_gate.py"
        p = os.path.join(self.m.ROOT, rel)
        import time
        old = time.time() - (self.m.FRESH_SEC + 120)
        os.utime(p, (old, old))
        try:
            with mock.patch.object(self.m, "live_workers",
                                   return_value=["- REQ-x (pid 1)"]):
                self.m.concurrent_gate([rel])
        finally:
            os.utime(p, None)

    def test_g4_override_passes(self):
        """G4. 사람이 담기는 내용을 실제로 읽었으면 지나갈 길이 있다.

        빠져나갈 문이 없는 게이트는 우회당하지, 지켜지지 않는다.
        """
        rel = "tests/test_commit_gate.py"
        os.utime(os.path.join(self.m.ROOT, rel), None)
        with mock.patch.dict(os.environ, {self.m.OVERRIDE: "1"}), \
             mock.patch.object(self.m, "live_workers",
                               return_value=["- REQ-x (pid 1)"]):
            self.m.concurrent_gate([rel])

    def test_g5_failing_staged_test_blocks(self):
        """G5. 커밋에 담긴 테스트가 실패하면 커밋이 멈춘다 (21:42 의 안전망)."""
        def fake_run(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, "FAILED (failures=1)", "")
        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            with self.assertRaises(SystemExit) as cm:
                self.m.staged_tests_gate(["tests/test_anything.py"])
        self.assertEqual(cm.exception.code, 1)

    def test_g6_no_staged_test_runs_nothing(self):
        """G6. 테스트가 안 담겼으면 아무것도 돌리지 않는다 — 매 커밋마다 2분을
        물리면 그 무게가 규율을 먼저 죽인다."""
        called = []
        with mock.patch.object(subprocess, "run",
                               side_effect=lambda *a, **k: called.append(a)):
            self.m.staged_tests_gate(["bin/s9", "docs/x.md"])
        self.assertEqual(called, [])

    def test_g7_hook_is_actually_installed(self):
        """G7. pre-commit 이 s9-guard 를 부른다 — 안 걸려 있으면 위 여섯이
        전부 장식이다."""
        hook = os.path.join(self.m.ROOT, ".git", "hooks", "pre-commit")
        if not os.path.exists(hook):
            self.skipTest("git repo 아님")
        with open(hook, encoding="utf-8") as f:
            self.assertIn("s9-guard", f.read())


if __name__ == "__main__":
    unittest.main()
