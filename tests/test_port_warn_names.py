"""포트 경고가 범인을 말하는가 (REQ-20260827-020-62x6).

사용자가 터미널 로그를 붙여 왔다 — "동적 포트 12956/16384 (79%) … 우리 것이
아닌 점유자를 의심하라". 실측하니 정말 우리 것이 아니었다: Windows COM 대리
프로세스(`dllhost.exe`) 하나가 13,392개를 쥐고 있었고 **우리 것은 0개**였다.

문제는 수치가 아니라 문구다. "의심하라"까지만 말하고 누구인지는 말하지 않는데,
그 답은 방금 `doctor` 가 이미 준 값 안에 있다(`top_name`·`top_pid`·`top_count`).
사람에게 다시 조사를 시키는 것이고, 실제로 사용자가 이 줄만 보고 우리 결함으로
읽었다.

한 줄에 **경보 + 범인 + 우리 몫**이 함께 있어야 그 자리에서 판단이 끝난다.
우리 것이 0개인데 82%라면 우리가 할 일이 없다는 뜻이고, 그 사실이야말로 이
줄이 전해야 할 것이다.

실행: python3 tests/ port_warn_names
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class PortWarnNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(S9, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r'elif ratio >= PORT_GUARD_WARN:(.*?)\n    return verdict',
                      cls.src, re.S)
        cls.warn = m.group(1) if m else ""

    def test_p1_the_warning_names_the_holder(self):
        """P1. 가장 많이 쥔 프로세스를 이름과 pid 로 말한다."""
        self.assertTrue(self.warn, "경고 분기를 찾지 못했다")
        for f in ("top_name", "top_pid", "top_count"):
            self.assertIn(f, self.warn, f"{f} 를 쓰지 않는다")

    def test_p2_it_says_how_many_are_ours(self):
        """P2. **우리 몫**을 함께 말한다.

        이게 판단의 핵심이다 — 82% 라도 우리 것이 0개면 우리가 할 일이 없다.
        그 사실을 말하지 않으면 사람은 우리 결함으로 읽는다(실제로 그랬다).
        """
        self.assertIn('win.get("sample")', self.warn,
                      "우리 것이 몇 개인지 말하지 않는다")
        self.assertIn("우리 것은", self.warn)

    def test_p3_it_survives_missing_fields(self):
        """P3. doctor 가 그 값을 안 주면 조용히 예전처럼 말한다.

        경고가 예외로 죽으면 감시자 틱이 함께 멈춘다 — 알리려던 것이 알림을
        죽이면 안 된다.
        """
        self.assertIn('if win.get("top_name") and win.get("top_count")',
                      self.warn, "필드가 없을 때의 갈래가 없다")

    def test_p4_auto_recovery_threshold_is_untouched(self):
        """P4. 자동 회수 문턱과 동작은 건드리지 않았다.

        우리 것이 0개인 상황에서도 자동 회수는 옳다 — 남의 프로세스를 죽이지
        않고 우리 쪽 누수를 줄여 여유를 만드는 마지막 안전망이다. 문구를
        고치다 안전망을 흔들면 고침이 새 위험이 된다.
        """
        self.assertIn("if ratio >= PORT_GUARD_AUTO:", self.src)
        self.assertIn('_doctor("--recover", "--yes")', self.src)


if __name__ == "__main__":
    unittest.main()
