"""판정 큐가 계보를 화면에서 지키는가 (REQ-20260831-015 화면 몫, DOC-20260831-002 규칙2).

서버는 review 행에 세 값을 싣는다(`review_family`, tests/test_review_family.py 가
그 계약을 지킨다). 화면이 할 일은 셋이다:

  ① review 열을 `review_order` 로 세운다 — 그 값 하나로 오름차순 정렬하면
     같은 묶음이 붙어 서고 선행(created 이른 쪽)이 위에 온다.
  ② `review_prior` 가 있는 후행 카드에 "먼저 볼 것이 있다"를 한 줄로 말한다.
  ③ `review_stale` 이 있는 카드에 "판정 대상이 바뀌는 중"을 한 줄로 말한다.

**자리가 계약인 이유**: 이 두 줄은 승인·반려 버튼보다 **먼저** 읽혀야 한다.
버튼 아래에 서면 사용자는 판정을 내린 다음에 경고를 읽는다 — 경고가 아니라
사후 통지다. 그래서 판정 블록의 맨 위가 계약이다.

**한 줄이 계약인 이유**: s9-design 「카드 사실 줄」이 정한 밀도다 — 축마다 한 줄,
카드 최대 두 줄. 둘 다 관계 축이라 사다리로 하나만 세우고, 진 쪽은 이긴 줄의
꼬리로 붙는다.

픽셀이 아니라 이 구조 계약만 검사한다 (실렌더 확인은 browser-verify 몫).

실행: python3 tests/ review_queue
"""
import re
import unittest

from webasset import index_path

INDEX = index_path()


class ReviewQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding="utf-8") as f:
            cls.src = f.read()
        m = re.search(r"function judgeQueueHTML\(r\)\{(.+?)\n\}", cls.src, re.S)
        cls.jq = m.group(1) if m else ""
        m = re.search(r"function renderBoard\(rows\)\{(.+?)\n\}", cls.src, re.S)
        cls.board = m.group(1) if m else ""
        m = re.search(r"function cardHTML\(r\)\{(.+?)\n\}", cls.src, re.S)
        cls.card = m.group(1) if m else ""

    # --- S1/S2 정렬 ---

    def test_review_column_sorts_by_review_order(self):
        """review 열은 review_order 오름차순 — 묶음 인접 + 선행 우선."""
        self.assertTrue(self.board, "renderBoard 를 찾지 못했다")
        m = re.search(r'if \(st === "review"\)\s*\n\s*(grp = .+?;)', self.board, re.S)
        self.assertIsNotNone(m, "review 열 전용 정렬 분기가 없다")
        self.assertIn("reviewKey", m.group(1))

    def test_review_order_has_fallback_key(self):
        """필드가 없는 행(옛 카탈로그·구버전 서버)도 자기 자리를 얻는다.

        폴백은 서버가 짓는 키와 같은 꼴이어야 한다 — 단독 묶음의 값이
        `<created>|<id>|000` 이므로, 그 꼴로 떨어지면 섞여 있어도 한 자로 잰다.
        """
        m = re.search(r"function reviewKey\(r\)\{(.+?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "reviewKey 폴백 술어가 없다")
        body = m.group(1)
        self.assertIn("review_order", body)
        self.assertIn("created", body)
        self.assertIn("000", body)

    # --- S3/S4 두 줄 ---

    def test_prior_line_names_the_leader(self):
        """후행 카드는 먼저 볼 선행을 이름으로 가리킨다 — id 만으로는 무슨 건인지 모른다."""
        self.assertTrue(self.jq, "judgeQueueHTML 을 찾지 못했다")
        self.assertIn("review_prior", self.jq)
        self.assertIn("catFind", self.jq)

    def test_prior_line_counts_the_rest(self):
        """선행이 둘 이상이면 몇 건인지 말한다 — 첫 건만 보이면 나머지가 없는 셈이 된다."""
        self.assertIn("depmore", self.jq)

    def test_stale_line_exists(self):
        """판정 대상이 바뀌는 중이면 그 사실이 카드에 글자로 선다."""
        self.assertIn("review_stale", self.jq)

    def test_no_lock(self):
        """경고-only — 배지가 승인·반려 버튼을 잠그지 않는다 (DOC-20260831-002: A안 기각)."""
        for bad in ("disabled", "aria-disabled"):
            self.assertNotIn(bad, self.jq)

    # --- S5 사다리 ---

    def test_one_line_per_axis(self):
        """관계 축은 한 줄 — 낡음이 먼저 판정을 이기고, 진 쪽은 꼬리로 붙는다."""
        self.assertIn("factTail", self.jq)
        # 사다리는 **이긴 쪽에서 나간다**: 낡음 갈래가 서면 그 자리에서 return
        # 하므로 두 줄이 이어 붙어 나갈 길이 없다.
        self.assertRegex(self.jq, r"if \(churn\.length\)\s*\n\s*return",
                         "낡음 갈래가 그 자리에서 끝나지 않는다 — 사다리가 아니다")
        # 이긴 줄 뒤에 다른 줄을 덧대는 형태(두 div 를 한 템플릿에)도 금지.
        for chunk in self.jq.split("return")[1:]:
            self.assertLessEqual(len(re.findall(r'class="rvpt', chunk.split(";")[0])), 1,
                                 "한 번에 두 줄이 나간다")

    def test_dep_line_outranks_queue_line(self):
        """선행 대기(blocked_by)가 있으면 큐 줄은 서지 않는다 — 축에 두 줄을 주지 않는다."""
        m = re.search(r"const queue = (.+?);\n", self.card)
        self.assertIsNotNone(m, "cardHTML 이 큐 줄을 세우지 않는다")
        self.assertIn("bl.length", m.group(1))

    # --- S6 자리 ---

    def test_queue_line_precedes_the_buttons(self):
        """경고는 판정보다 먼저 읽혀야 한다 — 판정 블록 맨 위."""
        m = re.search(r'const acts = isReq && r\.status === "review"\s*\?(.+?)\n', self.card, re.S)
        self.assertIsNotNone(m, "판정 블록을 찾지 못했다")
        blk = m.group(1)
        self.assertIn("queue", blk, "판정 블록에 큐 줄이 없다")
        self.assertLess(blk.index("queue"), blk.index("acts"),
                        "큐 줄이 승인·반려 버튼보다 뒤에 있다")
        self.assertLess(blk.index("queue"), blk.index("r.review_point"),
                        "큐 줄이 확인 요청보다 뒤에 있다")

    # --- S7 잉크·금지 ---

    def test_reuses_the_one_line_grammar(self):
        """새 컴포넌트를 만들지 않는다 — 열 몇 벌의 스킨이 따라오려면 .rvpt 여야 한다."""
        for cls in (r"\.rvpt\.ahead", r"\.rvpt\.churn"):
            self.assertRegex(self.src, cls + r"[,{]")

    def test_ink_only_no_fill(self):
        """색은 글자에만 — 색면 하이라이트·좌측 세로 띠 금지."""
        for sel in ("ahead", "churn"):
            for m in re.finditer(r"\.rvpt\.%s(?: \.rvcap)?\{([^}]*)\}" % sel, self.src):
                css = m.group(1)
                self.assertNotIn("background", css, sel + " 줄이 면을 칠한다")
                self.assertNotIn("border-left", css, sel + " 줄에 좌측 띠가 있다")

    def test_caption_ink_is_not_faint(self):
        """faint(2.9:1)는 캡션 잉크로 이미 반려된 값이다 (REQ-20260825-081)."""
        for m in re.finditer(r"\.rvpt\.(?:ahead|churn) \.rvcap\{([^}]*)\}", self.src):
            self.assertNotIn("--faint", m.group(1))

    def test_skin_override_restores_the_ink(self):
        """판정 블록 캡션을 통째로 칠하는 스킨은 이 두 줄의 잉크를 되돌려야 한다.

        실사고(REQ-20260831-015 실브라우저 1차): calm 이
        `[data-skin="calm"] .judge .rvcap{color:var(--c-review)}` 로 판정 블록의
        캡션을 전부 칠하는데, 특이도가 베이스와 동급이고 나중에 실려 경고 줄이
        「확인 요청」과 같은 소리로 읽혔다 — s9-design 이 적어 둔 스킨 공통
        함정 그대로다. 스킨이 늘어도 같은 자리에서 다시 걸리지 않게 계약으로
        박는다: 덮은 스킨은 복원한다.
        """
        for skin in set(re.findall(r'\[data-skin="([\w-]+)"\][^{]*\.judge \.rvcap\{', self.src)):
            self.assertRegex(
                self.src,
                r'\[data-skin="%s"\][^{]*\.rvpt\.(?:ahead|churn) \.rvcap' % skin,
                "%s 스킨이 판정 큐 캡션 잉크를 덮고 되돌리지 않는다" % skin)

    def test_line_is_clipped_to_one_line(self):
        """카드 밀도 — 한 줄에서 자른다."""
        # 스킨 블록(.gate·calm 등)은 자기 언어대로 이 줄을 눕힐 수 있다 —
        # 계약이 보는 것은 베이스(카드)의 규칙이다.
        m = re.search(r"\n\.rvpt\.ahead,\.rvpt\.churn\{([^}]*)\}", self.src)
        self.assertIsNotNone(m, "베이스의 한 줄 규칙이 없다")
        self.assertIn("nowrap", m.group(1))
        self.assertIn("ellipsis", m.group(1))

    # --- S8 경계 ---

    def test_silent_without_fields(self):
        """필드가 없으면 아무 줄도 서지 않는다 — 빈 캡션만 남는 줄은 고장으로 읽힌다."""
        self.assertRegex(self.jq, r'return ""')

    # --- S9 문서 화면 ---

    def test_document_gate_says_the_same(self):
        """문서의 확인 요청 callout 도 같은 사실을 확인 포인트 위에 놓는다.

        카드에만 있으면 같은 요청이 두 자리에서 다른 말을 한다 —
        판정 단추가 세 번 반려된 그 결함(REQ-20260828-007)과 같은 모양이다.
        """
        m = re.search(r"gate = `<div class=\"gate\">(.+?)`;", self.src, re.S)
        self.assertIsNotNone(m, "gate callout 을 찾지 못했다")
        blk = m.group(1)
        self.assertIn("gq", blk, "문서 gate 에 판정 큐 줄이 없다")
        self.assertLess(blk.index("gq"), blk.index("gate-b"),
                        "큐 줄이 확인 포인트보다 뒤에 있다")

    def test_document_gate_shares_one_source(self):
        """두 화면이 같은 술어를 먹는다 — 갈라질 자리를 만들지 않는다."""
        m = re.search(r"const gq = (.+?);\n", self.src)
        self.assertIsNotNone(m, "문서 gate 가 큐 줄을 짓지 않는다")
        self.assertIn("judgeQueue", m.group(1))


if __name__ == "__main__":
    unittest.main()
