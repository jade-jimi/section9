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

**반려 이후 (2026-08-27 00:19)**: 고친 뒤에도 같은 일이 또 났다 —
"이거 시킨대로 하는건데 이렇게 하는거 맞아?" + 캡처 → REQ-20260827-006-62x6.
디스크 코드는 이미 옳았다. 그 메시지를 받은 것은 **22:43 에 뜬 서버**였고, 고침은
23:53 에 들어갔다. 서버는 기동 시점 코드를 메모리에 들고 돈다(REQ-20260826-011).
그래서 여기 두 층을 나눠 못 박는다:

  - E 계열: 순수 판정 함수 — 그날 반려를 부른 발화까지 포함해 회귀로 고정한다.
  - C 계열: **채팅 입구 전체**(`chat_audit`) — 함수만 옳고 입구가 옛날이면
    사용자에게는 아무것도 고쳐지지 않은 것과 같다. 입구를 직접 통과시켜 본다.
  - X: `[File: …]`(이미지가 아닌 첨부)도 걷힌다 — 워커가 구멍을 테스트로
    남기고 리드가 닫았다.
    대시보드는 확장자로 `[Image:]` 와 `[File:]` 을 가른다(web/index.html sendChat).
    로그·PDF 를 붙여 물으면 같은 함정을 그대로 밟는다. 고침 자리는 bin/ 이라
    이 세션의 수정 범위 밖 — `expectedFailure` 로 명시해 두었다가 수리와 함께
    회귀 테스트가 된다(test_question_intake.py 가 쓴 방식과 같다).

실행: python3 tests/ attachment_classify
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PHOOK = os.path.join(HERE, "..", "bin", "s9-audit-prompt")
S9 = os.path.join(HERE, "..", "bin", "s9")

# 반려를 부른 그 메시지 — 대시보드 수신함(inbox-8e60e4af.jsonl, 00:18:23)의 원문
REJECTED_MSG = (
    "이거 시킨대로 하는건데 이렇게 하는거 맞아?\n"
    "[Image: /home/sjpark1/section9/state/terminal/uploads/sjpark1/"
    "20260827T001811-image.png]")


def _load(name=None, path=None):
    name = name or "s9att"
    path = path or PHOOK
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
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

    # ---------------------------------------------------------------- E7
    def test_e7_the_utterance_that_caused_the_rejection(self):
        """E7. 반려를 부른 그 발화 — 원문 그대로.

        T1 의 두 발화는 물음표가 **문장 중간**에 있거나 의문사로 시작해 다른
        갈래로도 잡힐 수 있었다. 이 발화는 물음표가 마지막 글자라 첨부 한 줄에
        정확히 가려진다 — 이 결함의 가장 순수한 모양이다.
        """
        self.assertEqual(self.h.classify(REJECTED_MSG), "question")
        self.assertTrue(self.h.is_durable_question(REJECTED_MSG),
                        "남을 질문인데 문서가 되지 않는다")

    # ---------------------------------------------------------------- X
    def test_x_non_image_attachment_is_stripped_too(self):
        """X. 이미지가 아닌 첨부(`[File: …]`)도 걷힌다.

        대시보드는 확장자로 마크를 가른다 — png/jpg 류는 `[Image:]`, 나머지는
        `[File:]`(web/index.html sendChat). 걷어내는 규칙(ATTACH_LINE)은
        image·screenshot·attachment·파일·이미지·첨부만 알고 **File 은 모른다.**
        로그나 PDF 를 붙여 물으면 캡처와 똑같이 물음표가 밀려난다.

        재작업 워커가 봉투 밖(bin/)이라 못 고치고 `expectedFailure` 로 못 박아
        두었고, 리드가 닫았다(ATTACH_LINE 에 `file` 추가). 그 방식이 옳았다 —
        고칠 수 없는 자리의 구멍은 **말로 넘기지 말고 테스트로 넘겨야** 다음
        사람이 지나치지 않는다.
        """
        self.assertEqual(
            self.h.classify("이 로그 보고 판단한 게 맞나?\n"
                            "[File: /home/u/section9/state/serve.log]"),
            "question")


class ChatEntranceWithAttachment(unittest.TestCase):
    """C 계열 — 함수가 아니라 **입구**를 통과시킨다.

    반려의 형태가 그랬다. 판정 함수는 옳았는데 사용자는 여전히 요청 카드를 봤다.
    사용자가 만나는 것은 함수가 아니라 입구다(대시보드 채팅 → `chat_audit`).
    그래서 여기서는 chat_audit 을 격리된 S9_ROOT 에서 직접 부르고, 카탈로그에
    무엇이 생겼는지로 판정한다 (test_question_intake.py 와 같은 방식).
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9attchat-")
        cls._prev = {k: os.environ.get(k)
                     for k in ("S9_ROOT", "S9_MACHINE", "S9_USER",
                               "S9_SESSION", "S9_REWORK_WATCH")}
        os.environ["S9_ROOT"] = cls.tmp
        os.environ["S9_MACHINE"] = "testbox"
        os.environ["S9_USER"] = "tester"
        os.environ["S9_REWORK_WATCH"] = "off"   # 무인 스폰 차단 (격리)
        os.environ.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")
        cls.s9 = _load("s9_mod_att", S9)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def cli(cls, *args):
        return subprocess.run([S9, *args], capture_output=True, text=True,
                              timeout=20, stdin=subprocess.DEVNULL)

    def catalog(self):
        p = os.path.join(self.tmp, "index", "catalog.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def types(self):
        return [r["type"] for r in self.catalog()]

    # ---------------------------------------------------------------- C1
    def test_c1_captured_question_makes_no_request_card(self):
        """C1. 캡처를 붙여 물으면 요청 카드가 생기지 않는다.

        반환값이 곧 사용자가 보는 것이다 — chat_audit 은 REQ 를 만들었을 때만
        id 를 돌려준다. None 이어야 한다.
        """
        before = self.types().count("request")
        self.assertIsNone(
            self.s9.chat_audit(REJECTED_MSG, "tester", "attsess"),
            "캡처 붙은 질문이 여전히 요청 카드가 된다 — 반려 사유 그대로다")
        self.cli("index", "rebuild")
        self.assertEqual(self.types().count("request"), before,
                         "요청 카드가 늘었다")

    # ---------------------------------------------------------------- C2
    def test_c2_captured_question_is_kept_as_a_question(self):
        """C2. 그리고 질문으로 남는다 — 카드가 안 생기는 것만으로는 부족하다.

        조용히 흘려보내면 '질문이 한 장뿐'인 상태(REQ-20260826-033)로 되돌아간다.
        """
        self.assertIn("question", self.types(),
                      "캡처 붙은 질문이 문서로 남지 않았다")

    # ---------------------------------------------------------------- C3
    def test_c3_captured_request_still_makes_a_card(self):
        """C3. 경계 — 캡처 붙은 **요청**은 여전히 요청 카드다.

        고침이 반대 방향의 유실을 만들면, 화면을 찍어 고쳐 달라는 말이
        기록 없이 사라진다. 그쪽이 더 아프다.
        """
        doc_id = self.s9.chat_audit(
            "보드 카드 글자가 너무 작다. 한 단계 키워 달라.\n"
            "[Image: /home/u/section9/state/terminal/uploads/t/x.png]",
            "tester", "attsess")
        self.assertTrue(doc_id and doc_id.startswith("REQ-"),
                        f"캡처 붙은 요청이 기록되지 않았다: {doc_id!r}")


if __name__ == "__main__":
    unittest.main()
