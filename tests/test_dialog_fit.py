"""창의 키는 위 모서리에서 시작해 바닥 여유까지 잰다 (REQ-20260901-015).

실사고 2026-09-01: 계정 창이 4줄이 되자 하단 단추(닫기·다시 시작)가 화면
밖으로 잘렸다. `.dlgbox` 의 max-height 가 100vh-96px 인데 top 은 최대
180px 라 — 시작점과 최대 키가 서로 다른 자를 썼다. 스크롤은 내용이
max-height 를 넘을 때만 생기므로 잘린 바닥에는 아무 손잡이도 없었다.

고정할 성질 하나: 시작점(top)과 최대 키(max-height)가 **같은 값**을 나눠
쓴다 — 그래야 top 이 얼마로 굳든 바닥 여유가 남는다.

실행: python3 tests/ dialog_fit
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(HERE, "..", "web", "css", "overlay.css")


class DialogFits(unittest.TestCase):
    def test_top_and_max_height_share_one_ruler(self):
        with open(CSS, encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"\.dlgbox\{[\s\S]*?\}", src)
        self.assertTrue(m, ".dlgbox 규칙이 없다")
        box = m.group(0)
        self.assertIn("--dlgtop:", box, "시작점 값이 이름을 잃었다")
        self.assertIn("top:var(--dlgtop)", box.replace(" ", ""),
                      "top 이 공용 자를 안 쓴다")
        self.assertRegex(
            box.replace(" ", ""),
            r"max-height:calc\(100vh-var\(--dlgtop\)-\d+px\)",
            "max-height 가 시작점을 빼지 않는다 — 바닥이 다시 잘린다")


if __name__ == "__main__":
    unittest.main()
