"""요청도 질문도 아닌 글 — 아티클 (REQ-20260827-073-62x6).

사용자: "문서 종류로, 아티클이라는 종류가 추가되었으면 좋겠다. 이건 그냥 요청도
아니고 질문도 아닌 특정 주제에 대해서 프롬프팅을 하면 그걸 원문과 함께 정리된
내용으로 말 그대로 아티클을 작성하는 용도이다."

세 종류의 경계:

    질문(QST)   사건이다 — 그때 무엇을 묻고 무엇이라 답했나. 시점에 고정, 개정 안 함
    지식(DOC)   규칙이다 — 앞으로의 작업을 구속한다
    아티클(ART) 둘 다 아니다 — 읽히려고 쓰는 글이고, 고쳐 쓴다

**원문과 정리된 글을 한 문서에 둔다.** 무엇을 물어 시작한 글인지 잃으면 나중에
고쳐 쓸 근거가 사라진다.

**분류로 알아맞히지 않는다.** 요청도 질문도 아니라서 기존 분류기 어디에도 들어맞지
않는데, 알아맞히다 틀리면 사용자가 고칠 방법이 없다. 사람이 대놓고 지목한다.

상태는 published 고정이다 — 초안/발행을 나누면 상태머신이 하나 더 생기는데, 이
문서의 진짜 상태는 "얼마나 다듬었나"이지 두 칸으로 나뉘지 않는다.

실행: python3 tests/ article_type
"""
import importlib.machinery
import importlib.util
import datetime
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class ArticleType(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="s9art-")
        os.environ["S9_ROOT"] = cls.root
        os.environ["S9_MACHINE"] = "boxA"
        os.environ["S9_USER"] = "alice"
        cls.env = {**os.environ}
        cls.env.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "alice")
        spec = importlib.util.spec_from_loader(
            "s9_art", importlib.machinery.SourceFileLoader("s9_art", S9))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    @classmethod
    def cli(cls, *argv, inp=None, expect=0):
        r = subprocess.run([S9, *argv], input=inp, capture_output=True,
                           text=True, env=cls.env, timeout=30)
        if expect is not None and r.returncode != expect:
            raise AssertionError(f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def mk(self, title="어떤 주제", body="원문 그대로"):
        return self.cli("new", "article", "--title", title, "--summary", "s",
                        "--user", "alice", "--body", body).split()[0]

    # N1. ART- 로 발번되고 articles/ 아래 놓인다
    def test_n1_created(self):
        aid = self.mk()
        self.assertTrue(aid.startswith("ART-"), aid)
        self.assertIn("type: article", self.cli("show", aid, "--meta"))
        self.assertTrue(os.path.isfile(os.path.join(
            self.root, "vault", "articles",
            "%04d" % datetime.date.today().year,
            "%02d" % datetime.date.today().month, aid + ".md")))

    # N2. 원문과 글 자리가 한 문서에 있다
    def test_n2_original_and_article(self):
        t = self.cli("show", self.mk(body="내가 물은 말"))
        self.assertIn("## Original", t)
        self.assertIn("내가 물은 말", t)
        self.assertIn("## Article", t)

    # N3. 상태는 published 고정 — 상태머신을 하나 더 만들지 않는다
    def test_n3_published(self):
        self.assertIn("status: published", self.cli("show", self.mk(), "--meta"))

    # B1. 다른 타입에는 Article 절이 생기지 않는다
    def test_b1_other_types_unchanged(self):
        rid = self.cli("new", "request", "--title", "요청", "--summary", "s",
                       "--goal", "g", "--size", "S", "--user", "alice",
                       "--body", "x").split()[0]
        self.assertNotIn("## Article", self.cli("show", rid))

    # N4. 채팅에서 대놓고 지목하면 시작된다 — 알아맞히지 않는다
    def test_n4_chat_prefix(self):
        for txt in ("아티클: WSL 루프백 벼랑에 대해",
                    "article: 같은 주제 영문 표기"):
            self.assertTrue(self.m.CHAT_ARTICLE_PREFIX.match(txt), txt)

    # B2. 평범한 말은 아티클로 새지 않는다
    def test_b2_plain_not_article(self):
        for txt in ("아티클이 있으면 좋겠다", "이 글은 article 이다", "그냥 요청"):
            self.assertIsNone(self.m.CHAT_ARTICLE_PREFIX.match(txt), txt)

    # B3. 지목만 있고 주제가 없으면 만들지 않는다
    def test_b3_prefix_only(self):
        src = open(S9, encoding="utf-8").read()
        i = src.index("CHAT_ARTICLE_PREFIX.match(t)")
        self.assertIn("if rest.strip():", src[i:i + 400],
                      "주제 없이 빈 아티클이 생긴다")

    # N5. API 가 명시 지정을 받는다 — 화면의 종류 선택이 붙을 자리
    def test_n5_api_as_type(self):
        src = open(S9, encoding="utf-8").read()
        i = src.index('parsed.path == "/api/chat"')
        self.assertIn('req.get("as_type")', src[i:i + 3200])

    # R1. 기존 타입 목록이 줄지 않았다
    def test_r1_types_kept(self):
        for t in ("request", "knowledge", "session", "project", "question"):
            self.assertIn(t, self.m.TYPES)


if __name__ == "__main__":
    unittest.main()
