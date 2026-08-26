"""첨부 본문이 열람 권한을 우회하는가 (REQ-20260827-005-62x6, 서버측).

REQ-20260826-020 으로 첨부에서 뽑은 본문이 사이드카에 남고 `s9 search --body`
가 그 글자를 찾게 됐다. 그런데 **화면에서는 읽을 수가 없었다** — 라우트가 없다.

라우트 하나를 더하는 일인데, backend 가 020 을 끝내며 경고를 남겼다: 그 라우트에
`doc_visible` 게이트를 `/api/asset` 과 **동일하게** 걸지 않으면, **PDF 원본은 못
보는 사람이 그 안의 글자는 다 읽는다.** 접근 제어에 구멍을 내는 종류라 "라우트를
먼저 만들고 게이트는 나중에" 순서를 쓰지 않았다.

이 파일이 지키는 것은 기능이 아니라 **그 게이트**다. 기능은 눈에 보여서 깨지면
알지만, 게이트는 깨져도 화면이 더 잘 도는 것처럼 보인다.

실행: python3 tests/ asset_text_api
"""
import importlib.machinery
import importlib.util
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


def _route(src, path):
    """서버 소스에서 그 라우트의 본문만 잘라낸다."""
    m = re.search(rf'parsed\.path == "{re.escape(path)}"(.*?)\n            elif ',
                  src, re.S)
    return m.group(1) if m else ""


class AssetTextApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(S9, encoding="utf-8") as f:
            cls.src = f.read()
        cls.asset = _route(cls.src, "/api/asset")
        cls.text = _route(cls.src, "/api/asset-text")

    def test_a1_the_route_exists(self):
        """A1. 라우트가 있다 — 없으면 화면이 영영 404 를 받는다."""
        self.assertTrue(self.text, "/api/asset-text 라우트를 찾지 못했다")

    def test_a2_the_gate_is_the_same_one(self):
        """A2. 게이트가 `/api/asset` 과 **같은 함수**다.

        비슷한 것을 새로 쓰면 둘이 갈리고, 갈린 쪽이 느슨하면 그게 구멍이다.
        이 저장소가 오늘만 세 번 밟은 실패다.
        """
        for frag in ("me = viewer_of(qs)", "doc_visible(meta_a, me)"):
            self.assertIn(frag, self.asset, f"기준 라우트가 바뀌었다: {frag}")
            self.assertIn(frag, self.text, f"본문 라우트에 게이트가 없다: {frag}")

    def test_a3_filename_cannot_escape_the_directory(self):
        """A3. 파일명이 디렉토리를 벗어나지 못한다.

        `f=../../etc/passwd` 같은 것을 막는 정규화가 원본 서빙과 같아야 한다 —
        본문 쪽만 느슨하면 **원본은 못 가져가는 파일의 내용을 텍스트로 가져간다.**
        """
        norm = "safe_name(os.path.basename(qs.get(\"f\", [\"\"])[0]))"
        self.assertIn(norm, self.asset)
        self.assertIn(norm, self.text)

    def test_a4_absence_and_denial_look_the_same(self):
        """A4. 없는 것과 못 보는 것이 **같은 404** 다.

        갈라 놓으면 응답 차이가 "그 문서는 존재한다"를 흘린다 — 내용을 막아도
        존재가 새면 막은 것이 아니다.
        """
        self.assertIn('self._send(404, "text/plain", b"not found")', self.text)
        # 거부 경로에서 본문을 실어 보내지 않는다
        self.assertNotIn("403", self.text)

    def test_a5_it_reads_the_one_sidecar_path(self):
        """A5. 사이드카 경로를 스스로 조립하지 않고 020 이 만든 함수를 쓴다.

        경로 규칙이 둘로 갈라지면 `s9 assets reindex` 가 만든 파일과 화면이
        읽는 파일이 달라진다 — 검색은 찾는데 화면은 못 여는 상태가 된다.
        """
        self.assertIn("asset_text_path(doc_asset_dir(doc_id), fn)", self.text)

    def test_a6_module_still_loads(self):
        """A6. 문법이 성립한다(서버 전체가 한 파일이라 값싼 보험)."""
        spec = importlib.util.spec_from_loader(
            "s9atapi", importlib.machinery.SourceFileLoader("s9atapi", S9))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertTrue(callable(m.asset_text_path))


if __name__ == "__main__":
    unittest.main()
