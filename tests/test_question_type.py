"""질문 문서 타입(QST) 테스트 (REQ-20260826-017, 설계 DOC-20260826-011-62x6).

질문과 답이 세션 로그로만 남아 사라지던 공백을 문서 타입으로 메운다. 이 스위트가
잡는 것은 두 층이다.

- vault 층: type=question 문서가 카탈로그·조회·노트·관계에 그대로 얹힌다. 발번과
  `s9 new question` 은 bin/s9 의 TYPES 소유라 여기서 만들지 않고, **타입 등록 전에도
  vault 문서 자체는 깨지지 않는다**는 것과 **기존 네 타입이 그대로다**는 회귀를 본다.
- 화면 층: 대시보드가 새 타입을 모르면 사용자에겐 없는 것이다. 타입바·타입색·그래프
  타입 집합·id 링크화·미답 판정이 index.html 에 실제로 들어있는지 계약으로 잡는다.

미답 판정은 status 가 아니라 **파생**이다(ADR 결정 3): 진실은 본문의 answer 노트
하나. 그래서 화면의 정규식과 CLI 가 실제로 쓰는 노트 헤더 형식이 어긋나면 미답이
영원히 미답으로 남는다 — V7 이 그 이음매를 붙잡는다.

실행: python3 tests/ question_type
"""
import json
import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
INDEX_HTML = os.path.join(HERE, "..", "web", "index.html")

QUESTION_DOC = """---
id: QST-20260826-001-tst0
type: question
title: cron·systemd 사용 여부
summary: 외부 스케줄러를 쓰는가
status: published
user: tester
machine: testbox
project: ""
tags: ["question"]
created: 2026-08-26T13:02:55+09:00
updated: 2026-08-26T13:02:55+09:00
priority: 50
---

## Original

이 하네스에서 systemd, cron을 사용 중인건가?

## Notes

## History
- 2026-08-26T13:02:55+09:00 created by tester (status: published)
"""


def _web():
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


class TestQuestionInVault(unittest.TestCase):
    """vault 층 — 타입이 CLI에 등록되기 전에도 문서·인덱스·노트가 성립한다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9qst-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)         # 무인 세션 환경 누수 차단
        cls.env.pop("S9_AUTO_RESUME", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")
        # 기존 네 타입 중 CLI로 만들 수 있는 셋을 먼저 깔아 회귀 기준선을 만든다
        cls.req = cls.cli("new", "request", "--title", "기준선 요청",
                          "--summary", "s", "--size", "S").stdout.split()[0]
        cls.doc = cls.cli("new", "knowledge", "--title", "기준선 지식",
                          "--summary", "s").stdout.split()[0]
        cls.ses = cls.cli("new", "session", "--title", "기준선 세션",
                          "--summary", "s").stdout.split()[0]
        # 질문 문서는 손으로 놓는다 (발번·TYPES는 bin/s9 소유)
        d = os.path.join(cls.tmp, "vault", "questions", "2026", "08")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "QST-20260826-001-tst0.md"), "w",
                  encoding="utf-8") as f:
            f.write(QUESTION_DOC)
        cls.cli("index", "rebuild")

    @classmethod
    def cli(cls, *args):
        r = subprocess.run([S9, *args], env=cls.env, capture_output=True,
                           text=True)
        assert r.returncode == 0, f"s9 {' '.join(args)} → {r.stderr}"
        return r

    def catalog(self):
        p = os.path.join(self.tmp, "index", "catalog.jsonl")
        with open(p, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    # V1. question 문서가 카탈로그에 제 타입으로 잡힌다
    def test_v1_catalog_row(self):
        rows = [r for r in self.catalog() if r["type"] == "question"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "QST-20260826-001-tst0")
        self.assertEqual(rows[0]["title"], "cron·systemd 사용 여부")
        self.assertTrue(rows[0]["path"].replace("\\", "/")
                        .startswith("vault/questions/"))

    # V2. 기존 네 타입 조회·인덱스가 그대로다 (회귀)
    def test_v2_existing_types_intact(self):
        types = {r["type"] for r in self.catalog()}
        for t in ("request", "knowledge", "session"):
            self.assertIn(t, types)
        for doc_id in (self.req, self.doc, self.ses):
            self.assertEqual(
                self.cli("show", doc_id, "--meta").returncode, 0)
        # 타입 필터도 그대로 — question은 아직 TYPES 밖이라 여기서 묻지 않는다
        out = self.cli("ls", "--type", "request").stdout
        self.assertIn(self.req, out)

    # V3. show/note/link 가 question 문서 위에서 그대로 동작한다
    def test_v3_show_note_link(self):
        qid = "QST-20260826-001-tst0"
        self.assertIn("cron", self.cli("show", qid).stdout)
        self.cli("note", qid, "crontab/systemctl 호출 0건이다.",
                 "--label", "answer")
        self.cli("link", qid, "--relates", self.req)
        body = self.cli("show", qid).stdout
        self.assertIn("crontab/systemctl 호출 0건", body)
        self.assertIn(self.req, self.cli("show", qid, "--meta").stdout)
        # relates 는 양방향 — 상대 쪽에도 기록된다
        self.assertIn(qid, self.cli("show", self.req, "--meta").stdout)

    # V7. 화면의 answer 노트 정규식이 CLI가 실제로 쓰는 헤더 형식과 맞는다.
    #     여기가 어긋나면 답을 달아도 화면은 영원히 '미답'으로 읽는다.
    def test_v7_answer_note_regex_matches_cli_format(self):
        qid = "QST-20260826-001-tst0"
        self.cli("note", qid, "답이다.", "--label", "answer")
        body = self.cli("show", qid).stdout
        m = re.search(r"const ANSWER_NOTE_RE = /(.+)/([a-z]*);", _web())
        self.assertIsNotNone(m, "index.html에 ANSWER_NOTE_RE가 없다")
        flags = re.M if "m" in m.group(2) else 0
        flags |= re.I if "i" in m.group(2) else 0
        self.assertRegex(body, re.compile(m.group(1), flags))
        # 답이 없는 문서는 걸리지 않아야 한다 (거짓 '답함' 금지)
        plain = self.cli("show", self.req).stdout
        self.assertNotRegex(plain, re.compile(m.group(1), flags))


class TestQuestionOnScreen(unittest.TestCase):
    """화면 층 — 코드가 타입을 만들어도 대시보드가 모르면 사용자에겐 없는 것이다."""

    @classmethod
    def setUpClass(cls):
        cls.web = _web()

    # V4. Docs 타입바가 question을 잡고, 순서가 session보다 앞이다
    def test_v4_type_order(self):
        m = re.search(r"const TYPE_ORDER = \[([^\]]+)\]", self.web)
        self.assertIsNotNone(m)
        order = re.findall(r'"([a-z]+)"', m.group(1))
        self.assertIn("question", order)
        self.assertLess(order.index("question"), order.index("session"))
        # 목록 그룹에도 자리가 있어야 타입바 숫자와 목록이 갈리지 않는다
        self.assertIn("question:[]", self.web.replace(" ", ""))
        # 헤더 타입 필터에서도 고를 수 있다
        self.assertIn("<option>question</option>", self.web)

    # V5. 타입색 토큰이 모든 테마에 있다 — 한 테마라도 빠지면 그 테마에서만
    #     질문 노드가 무색이 된다
    def test_v5_type_color_every_theme(self):
        themes = len(re.findall(r"--t-request:", self.web))
        questions = len(re.findall(r"--t-question:", self.web))
        self.assertEqual(themes, questions,
                         f"--t-request {themes}개 테마 중 --t-question은 {questions}개")
        self.assertIn('question:"var(--t-question)"', self.web.replace(" ", ""))
        # 그래프 타입 집합은 배열 하나가 소유한다 (범례·색 해석이 갈리지 않게)
        m = re.search(r"const GRAPH_TYPES = \[([^\]]+)\]", self.web)
        self.assertIsNotNone(m)
        self.assertIn("question", re.findall(r'"([a-z]+)"', m.group(1)))

    # V6. 본문 속 QST id 가 링크가 된다 — 흩어진 정규식 리터럴이 남아 있으면
    #     한 곳만 새 타입을 모르는 상태로 조용히 갈라진다
    def test_v6_id_prefix_single_source(self):
        m = re.search(r'const DOC_ID_PREFIX = "([^"]+)"', self.web)
        self.assertIsNotNone(m)
        self.assertIn("QST", m.group(1).split("|"))
        self.assertNotIn("REQ|DOC|SES)", self.web,
                         "id 접두 리터럴이 아직 흩어져 있다 — DOC_ID_PREFIX로 모아라")

    # V8. 미답은 status가 아니라 파생이다 (ADR 결정 3).
    #     status 문자열로 판정하면 전이를 잊는 순간 진실이 둘이 된다.
    def test_v8_unanswered_is_derived(self):
        m = re.search(r"function isAnswered\(r, body\)\{(.+?)\n\}",
                      self.web, re.S)
        self.assertIsNotNone(m, "isAnswered 판정 함수가 없다")
        self.assertIn("answered", m.group(1))
        self.assertIn("ANSWER_NOTE_RE", m.group(1))
        label = re.search(r"function statusLabel\(r, body\)\{(.+?)\n\}",
                          self.web, re.S)
        self.assertIsNotNone(label)
        self.assertIn("미답", label.group(1))
        self.assertIn("답함", label.group(1))
        # 질문 상태를 status 값으로 갈라 읽으면 안 된다
        self.assertNotIn('r.status === "published"', label.group(1))

    # V10. 목록 행이 상태어를 그대로 찍지 않고 판정 함수를 거친다. 여기가 풀리면
    #      질문 행에 'published' 가 뜬다 — 질문에 없는 흐름을 읽게 만드는 표기다.
    #      (헤드리스 캡처에서 Docs 목록 높이가 눌려 픽셀로 못 잡는 자리라 계약으로 잡는다)
    def test_v10_list_row_uses_label(self):
        row = re.search(r'style="--sc:\$\{sc\}">\s*\n?\s*'
                        r'<span class="st">\$\{esc\((.+?)\)\}</span>', self.web)
        self.assertIsNotNone(row, "Docs 목록 행의 상태 칩을 찾지 못했다")
        self.assertEqual(row.group(1), "statusLabel(r)")
        # 행 색도 상태색이 아니라 "답이 남았는가"에서 온다
        sc = re.search(r'const sc = r\.type === "question"\s*\n?\s*\?([^;]+);', self.web)
        self.assertIsNotNone(sc, "질문 행의 색 분기가 없다")
        self.assertIn("--t-question", sc.group(1))
        self.assertIn("isAnswered(r)", sc.group(1))

    # V9. 파생 필드가 아직 없을 때는 판정하지 않는다(3상). 모르는 것을 '미답'이라
    #     단정하면 답이 붙은 문서를 목록은 미답, 뷰어는 답함으로 읽는다.
    def test_v9_unknown_is_not_unanswered(self):
        m = re.search(r"function isAnswered\(r, body\)\{(.+?)\n\}",
                      self.web, re.S)
        self.assertIn("undefined", m.group(1),
                      "카탈로그 파생 필드 부재를 구분하지 않는다")
        label = re.search(r"function statusLabel\(r, body\)\{(.+?)\n\}",
                          self.web, re.S)
        self.assertIn("null", label.group(1),
                      "모름(null)을 미답과 갈라 쓰지 않는다")


if __name__ == "__main__":
    unittest.main()
