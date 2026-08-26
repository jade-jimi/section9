"""첨부가 질문을 가리는가 (REQ-20260826-034-62x6).

분류는 질문 표지(물음표·종결어미)를 **마지막 줄**에서 찾는다. 그런데 화면을
캡처해 붙이면 원문의 마지막 줄이 `[Image: /경로]` 가 되어 물음표가 밀려난다.
그래서 명백한 질문이 request 카드가 됐다. 실사고 둘, 같은 날:

  - "이 요청은 붉은색 점은 무슨 의미야? 녹색점멸도 아니고" → REQ-20260826-032
  - "idle인 이유가 뭐라고?"                              → REQ-20260826-031

이게 특히 나쁜 이유는 **가장 물어보고 싶을 때 정확히 이 경로를 밟기 때문**이다.
사람은 화면이 이상할 때 캡처해서 묻는다. 질문 타입을 만들어 놓고 캡처가 붙은
질문만 골라 놓치면, 그 타입이 가장 필요한 자리에서 비어 있게 된다.

고침은 분류 전에 첨부 참조 줄을 걷어내는 것이다 — 첨부는 분류의 재료가 아니다.
첨부뿐인 메시지는 원문 그대로 두어 기존 동작을 보존한다.

실행: python3 tests/ attachment_classify
"""
import importlib.machinery
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PHOOK = os.path.join(HERE, "..", "bin", "s9-audit-prompt")


def _load():
    spec = importlib.util.spec_from_loader(
        "s9att", importlib.machinery.SourceFileLoader("s9att", PHOOK))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class AttachmentClassify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = _load()

    def test_t1_the_two_real_incidents(self):
        """T1. 그날 실제로 오분류된 두 발화가 이제 질문으로 잡힌다."""
        for text in (
            "이 요청은 붉은색 점은 무슨 의미야? 녹색점멸도 아니고\n"
            "[Image: /home/u/state/terminal/uploads/x/a.png]",
            "idle인 이유가 뭐라고?\n[Image: assets/REQ-x/b.png]",
        ):
            self.assertEqual(self.h.classify(text), "question",
                             f"질문이 request 로 분류됐다: {text.splitlines()[0]}")

    def test_t2_same_text_without_attachment_is_unchanged(self):
        """T2. 첨부가 없을 때의 판정과 같아야 한다 — 첨부는 뜻을 바꾸지 않는다."""
        bare = "이 요청은 붉은색 점은 무슨 의미야? 녹색점멸도 아니고"
        self.assertEqual(self.h.classify(bare),
                         self.h.classify(bare + "\n[Image: /x/a.png]"))

    def test_t3_paste_form_is_also_stripped(self):
        """T3. 터미널 붙여넣기 형태(`[Image #1]`)도 같은 함정이다."""
        self.assertEqual(
            self.h.classify("이 화면이 왜 이렇게 나오나?\n[Image #1]"),
            "question")

    def test_t4_request_with_attachment_stays_request(self):
        """T4. 첨부 붙은 **요청**은 그대로 요청이다.

        걷어내기가 거칠면 반대로 요청이 질문이 되어 카드가 안 생긴다 —
        고침이 반대 방향의 유실을 만들면 안 된다.
        """
        self.assertEqual(
            self.h.classify("보드 카드 글자가 너무 작다. 한 단계 키워 달라.\n"
                            "[Image: /x/c.png]"),
            "request")

    def test_t5_attachment_only_keeps_old_behavior(self):
        """T5. 첨부뿐인 메시지는 원문 그대로 본다 — 걷어내고 나면 빈 문자열이
        되는데, 빈 문자열을 분류하면 엉뚱한 갈래로 떨어진다."""
        only = "[Image: /x/d.png]"
        self.assertEqual(self.h.strip_attachment_refs(only), only)

    def test_t6_length_is_measured_without_attachments(self):
        """T6. '남을 질문인가'의 길이 판정도 첨부를 빼고 센다.

        경로 한 줄이 짧은 확인 발화를 20자 문턱 위로 밀어 올리면, 남길 값어치가
        없는 발화가 문서가 된다.
        """
        self.assertFalse(self.h.is_durable_question(
            "이거 맞아?\n[Image: /home/user/section9/state/terminal/uploads/"
            "sjpark1/20260826T224537-image.png]"))


if __name__ == "__main__":
    unittest.main()
