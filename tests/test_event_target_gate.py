"""조각 하나가 통째로 죽는다 (REQ-20260830-010-62x6).

사용자가 대시보드에서 이 알림을 받았다:

    화면 조각 1개가 이 브라우저에서 죽었습니다.
    app/events.js:5 — TypeError: e.target.closest is not a function

`e.target` 은 **요소라는 보장이 없다.** 판 위의 글자를 끌면 dragstart 의
target 이 텍스트 노드이고, 텍스트 노드에는 `closest` 가 없다. 그 한 줄이 던진
예외가 `events.js` 를 통째로 죽이면 그 조각이 맡은 자리 — 판의 거의 모든 버튼 —
이 한꺼번에 멎는다. 화면을 조각으로 가른 뒤로(REQ-20260829-027) **죽는 단위가
곧 조각 하나**이기 때문이다.

같은 오류가 처음이 아니다. REQ-20260830-006 에서 `tidy.js` 가 똑같이 죽었고,
그때는 그 조각 안에 방어를 하나 세워 막았다. 조각마다 자기 방어를 두면 조각
수만큼 구멍이 남고, 실제로 남은 구멍에서 다시 터졌다.

그래서 여기서 잠그는 계약은 "지켰나"가 아니라 **문이 하나인가**다:
이벤트 대상을 요소로 바꾸는 자리는 `evEl` 한 곳이고, 조각들은 거기만 지난다.

실행: python3 tests/ event_target_gate
"""
import glob
import os
import re
import unittest

import webasset

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "web", "app")

# 문을 거치지 않고 대상을 직접 캐묻는 자리. `closest` 는 이번에 터진 것이고,
# 나머지 셋도 텍스트 노드에는 없거나 다른 것을 뜻한다 — 같은 사고의 다른 얼굴.
RAW = re.compile(r"\b\w+\.target\.(closest|matches|classList|dataset)\b")


class EventTargetGate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = {os.path.basename(p): open(p, encoding="utf-8").read()
                     for p in sorted(glob.glob(os.path.join(APP, "*.js")))}

    # ----------------------------------------------------------------- G1
    def test_g1_the_gate_exists_and_climbs_to_an_element(self):
        """문이 있고, 요소가 아닌 대상은 **감싼 요소**로 올라간다.

        null 로 떨어뜨리는 것보다 한 걸음 낫다: 단추 안 글자를 누르면 target 이
        그 텍스트 노드인데, null 이면 단추를 못 찾고 클릭이 통째로 무시된다.
        """
        src = self.files["state.js"]
        self.assertIn("function evEl(", src, "공용 문(evEl)이 없다")
        body = src[src.index("function evEl("):]
        self.assertIn("nodeType === 1", body,
                      "요소인지를 nodeType 으로 묻지 않는다")
        self.assertIn("parentElement", body,
                      "텍스트 노드를 감싼 요소로 올리지 않는다 — "
                      "글자를 눌렀을 때 단추를 못 찾는다")

    # ----------------------------------------------------------------- G2
    def test_g2_no_piece_asks_the_target_directly(self):
        """어느 조각도 대상에게 직접 묻지 않는다.

        이것이 이 시험의 본체다. 한 자리라도 문을 비껴가면 그 자리가 다음
        사고다 — `tidy.js` 를 고친 뒤 `events.js` 에서 그대로 다시 났다.
        """
        bad = []
        for name, src in self.files.items():
            if name == "oops.js":
                continue          # 지킴이는 ES5 홀로 서는 조각이다 (아래 G4)
            for m in RAW.finditer(src):
                line = src[:m.start()].count("\n") + 1
                bad.append(f"{name}:{line} — {m.group(0)}")
        self.assertEqual(bad, [],
                         "이벤트 대상에게 직접 물었다. `evEl(e.target)?.…` 로 "
                         "바꿔라 — 텍스트 노드가 오면 그 조각이 통째로 죽는다:\n"
                         + "\n".join(bad))

    # ----------------------------------------------------------------- G3
    def test_g3_the_places_that_broke_go_through_the_gate(self):
        """실제로 터진 두 자리가 문을 지난다 — 드래그(이번)와 치우기(지난번)."""
        ev = self.files["events.js"]
        self.assertIn('evEl(e.target)?.closest(\'.card[draggable="true"]\')', ev,
                      "글자를 끌면 죽던 그 줄이 문을 안 지난다")
        self.assertIn('evEl(e.target)?.closest(".col[data-colstatus]")', ev,
                      "끌어 놓는 자리도 같은 위험을 진다")
        self.assertIn("evEl(e.target)", self.files["tidy.js"],
                      "지난번에 고친 자리가 자기 문을 따로 쓰고 있다")

    # ----------------------------------------------------------------- G4
    def test_g4_the_gate_stands_before_the_pieces_that_use_it(self):
        """문이 그것을 쓰는 조각보다 **먼저** 온다.

        브라우저가 받는 한 장에서 순서가 뒤집히면, 조각이 실행되는 시점이
        아니라 클릭 시점에 부르므로 대개는 그냥 돈다. 그래도 못 박아 둔다 —
        `evEl` 을 최상위가 아닌 자리로 옮기면 그때는 진짜로 깨진다.
        """
        page = open(webasset.index_path(), encoding="utf-8").read()
        gate = page.index("function evEl(")
        first = min(page.index(m) for m in
                    ('evEl(e.target)?.closest(\'.card[draggable="true"]\')',))
        self.assertLess(gate, first, "문이 쓰는 자리보다 뒤에 선다")

    # ----------------------------------------------------------------- G5
    def test_g5_the_guardian_still_stands_alone(self):
        """지킴이(oops.js)는 여전히 남에게 기대지 않는다.

        조각이 죽은 것을 알리는 조각이 남의 함수를 부르면, 하필 그 조각이
        없어진 날 아무도 알리지 못한다 (oops.js 스스로 적어 둔 계약).
        """
        self.assertNotIn("evEl(", self.files["oops.js"],
                         "지킴이가 남의 함수를 부른다")


if __name__ == "__main__":
    unittest.main()
