"""Docs 목록은 최근 수정 순 · 못 도는 명령은 미리 말한다
(REQ-20260827-051 · REQ-20260827-050).

**정렬** — Board 는 "무엇부터 집을까"를 묻는 화면이라 우선순위가 앞선다. Docs 는
"무슨 일이 있었나"를 훑는 화면이라 최근 수정이 앞서야 한다. 우선순위 50짜리 옛
문서가 방금 고친 문서 위에 앉아 있으면 훑는 일이 안 된다.

정렬 규칙은 `workOrder` 한 곳에 모여 있다는 것이 이 화면의 약속이다. 그래서
변형도 **그 옆에** 두고, 목록 만드는 자리에서 `.sort()` 를 새로 부르지 않는다.

**팔레트** — `/permissions` 처럼 대시보드에서 못 도는 CC 명령이 목록에 없으면,
사용자가 친 그 줄이 **그냥 채팅 메시지로 전송된다.** 그러면 리드가 "그건 터미널에서만
됩니다"라고 답하는 데서 끝난다 — 팔레트가 미리 말해 주는 편이 한 왕복 빠르다.
(이 세션에서 실제로 그렇게 한 왕복을 썼다.)

실행: python3 tests/ docs_recent_order
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "web", "index.html")


class DocsRecentOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()

    # N1. 최근순 정렬 규칙이 있다
    def test_n1_recent_order_exists(self):
        self.assertIn("const recentOrder", self.src)
        m = re.search(r"const recentOrder = rows =>(.*?);\n", self.src, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("updated", body)
        self.assertNotIn("prioOf", body,
                         "Docs 정렬에 우선순위가 섞였다 — 최근순이어야 한다")

    # N2. Docs 목록이 그것을 쓴다
    def test_n2_docs_uses_it(self):
        m = re.search(r"async function renderDocs\(rows\)\{(.*?)\n\}\n",
                      self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("recentOrder(rows)", m.group(1),
                      "Docs 목록이 최근순 정렬을 쓰지 않는다")

    # B1. Board 는 그대로 우선순위 순이다 — 두 화면의 물음이 다르다
    def test_b1_board_keeps_priority(self):
        m = re.search(r"const workOrder = rows =>(.*?);\n", self.src, re.S)
        self.assertIsNotNone(m)
        self.assertIn("prioOf", m.group(1))

    # R1. 정렬은 한 자리에 모여 있다 — 목록 만드는 곳에서 새로 sort 하지 않는다
    def test_r1_no_scattered_sort_in_docs(self):
        m = re.search(r"async function renderDocs\(rows\)\{(.*?)\n\}\n",
                      self.src, re.S)
        self.assertNotIn(".sort(", m.group(1),
                         "Docs 렌더 안에서 정렬을 새로 걸고 있다")

    # N3. 대시보드에서 못 도는 명령을 팔레트가 미리 말한다
    def test_n3_cli_only_commands_listed(self):
        m = re.search(r"const CC_BUILTINS = \[(.*?)\]\.map", self.src, re.S)
        self.assertIsNotNone(m)
        block = m.group(1)
        for name in ("permissions", "hooks"):
            self.assertIn(f'"{name}"', block,
                          f"/{name} 이 CLI 전용 목록에 없다 — 채팅으로 전송된다")


if __name__ == "__main__":
    unittest.main()
