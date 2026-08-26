"""사용자의 말이 답할 수 없는 창구로 가는가 (REQ-20260826-031-62x6).

실사고 2026-08-26 22:27·22:36. 사용자가 대시보드 터미널에 말을 걸었는데 대상이
`d3d60fdc` 였다 — REQ-20260826-019 를 처리하던 **무인 워커** 세션이다. 워커는
`-p` 로 한 턴 돌고 끝나므로 수신함을 듣지 않고, SessionEnd 도 남기지 않아
바인딩이 오래 '아직 안 끝난 세션'으로 남는다. 그래서 대상 고르기가 워커를
사람 세션보다 앞세워 뽑았고, 보낸 말은 아무도 열지 않는 수신함에 쌓였다.

화면은 그 상태를 `idle` 이라고 정직하게 말했다. 사용자가 물은 것은 그 단어의
뜻이 아니라 **"왜 하필 저 세션이냐"** 였다.

고침은 순위에 축을 하나 더 두는 것이다 — 0순위는 "사람과 대화할 수 있는가".
제외가 아니라 최하위로 둔다: 정말 다른 후보가 없을 때 갈 곳까지 없애면
메시지가 기록조차 되지 않는다.

실행: python3 tests/ chat_target_worker
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class ChatTargetWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9tgt-")
        os.environ["S9_ROOT"] = cls.tmp
        spec = importlib.util.spec_from_loader(
            "s9tgtmod", importlib.machinery.SourceFileLoader("s9tgtmod", S9))
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        os.makedirs(cls.mod.STATE, exist_ok=True)

    def setUp(self):
        for fn in os.listdir(self.mod.STATE):
            os.remove(os.path.join(self.mod.STATE, fn))

    def _bind(self, sid, **kw):
        b = {"machine": "testbox", "session": sid, "entry": "code"}
        b.update(kw)
        with open(os.path.join(self.mod.STATE, f"testbox__{sid}.json"),
                  "w", encoding="utf-8") as f:
            json.dump(b, f)

    def _target(self, listening=()):
        m = self.mod
        with mock.patch.object(m, "chat_live", return_value=True), \
             mock.patch.object(m, "_inbox_watch_alive",
                               side_effect=lambda s: s in listening), \
             mock.patch.object(m, "_binding_activity_paths", return_value=[]):
            b = m.chat_target()
        return (b or {}).get("session")

    def test_w1_worker_loses_to_a_person_session(self):
        """W1. 워커와 사람 세션이 함께 살아 있으면 사람 세션이 대상이다.

        이게 이 실사고다 — 워커가 활동 신선도로 앞서 대상을 가져갔다.
        """
        self._bind("d3d60fdc", worker="1")
        self._bind("dc4f4d76")
        self.assertEqual(self._target(), "dc4f4d76")

    def test_w2_worker_is_last_resort_not_excluded(self):
        """W2. 다른 후보가 없으면 워커라도 고른다.

        갈 곳을 아예 없애면 메시지가 기록조차 되지 않는다 — 답이 늦는 것과
        말이 사라지는 것은 다른 손해다.
        """
        self._bind("d3d60fdc", worker="1")
        self.assertEqual(self._target(), "d3d60fdc")

    def test_w3_listening_still_wins_among_people(self):
        """W3. 사람 세션끼리는 예전 규칙 그대로 — 듣고 있는 쪽이 이긴다
        (REQ-20260825-015 가 세운 순위를 이 고침이 뒤집지 않는다)."""
        self._bind("aaaaaaaa")
        self._bind("bbbbbbbb")
        self.assertEqual(self._target(listening=("bbbbbbbb",)), "bbbbbbbb")

    def test_w4_listening_worker_still_loses(self):
        """W4. 워커가 어쩌다 듣고 있어도 사람 세션에 진다.

        축의 순서가 뒤집히면 이 고침은 아무것도 아니다.
        """
        self._bind("d3d60fdc", worker="1")
        self._bind("dc4f4d76")
        self.assertEqual(self._target(listening=("d3d60fdc",)), "dc4f4d76")

    def test_w5_spawned_worker_marks_itself(self):
        """W5. 워커가 자기를 워커라고 표시한다 — 이 표시가 없으면 위 넷이
        전부 무의미하다. 표시는 프롬프트 훅의 auto-resume 분기에서 한다."""
        with open(os.path.join(HERE, "..", "bin", "s9-audit-prompt"),
                  encoding="utf-8") as f:
            hook = f.read()
        self.assertIn('run(env, "bind", "worker", "1")', hook)


if __name__ == "__main__":
    unittest.main()
