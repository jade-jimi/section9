"""비밀을 화면에서 다룬다 — 값은 절대 나가지 않는다 (REQ-20260828-012-62x6).

사용자(08:36): "세션을 껐다켜거나 시크릿 관련 기능들이 다 완료된걸로 아는데 왜
볼 수가 없지?"

볼 수 없던 이유는 단순하다 — **화면이 없었다.** REQ-20260827-035 는 CLI 만
만들고 `done` 이 됐고, `web/index.html` 에 "secret" 이라는 낱말은 한 번도 나오지
않았다. 이 사람은 대시보드로 일한다. 거기서 보이지 않으면 없는 기능이다.

**경계**: 이 API 의 뜻은 "모델이 값을 안 본다"가 아니다 — 그건 이 하네스에서
보장할 수 없다(REQ-20260827-035 에 적어 둔 한계). 뜻은 **실수로 새는 길을
닫는다**는 것이다. 값이 응답·로그·오류 문구에 섞이면 브라우저 기록·캡처·스트림
어디로든 따라간다.

경로도 주지 않는다 — 어느 쪽(internal/external)에 있는지만.

실행: python3 tests/ secret_api
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class SecretApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = open(S9, encoding="utf-8").read()
        i = cls.src.index('parsed.path == "/api/secrets"')
        cls.listing = cls.src[i:i + 1200]
        j = cls.src.index('parsed.path == "/api/secret/set"')
        cls.setter = cls.src[j:cls.src.index('parsed.path == "/api/secret/rm"')]

    # N1. 목록은 키만 준다
    def test_n1_keys_only(self):
        self.assertIn('"key": k', self.listing)
        self.assertNotIn("secret_value", self.listing,
                         "목록이 값을 읽고 있다")

    # B1. 경로도 주지 않는다 — 값이 아니어도 필요 없는 것은 흘리지 않는다
    def test_b1_no_paths(self):
        self.assertIn('"where"', self.listing)
        self.assertNotIn("os.path.relpath(p0", self.listing)
        self.assertNotIn('"path"', self.listing)

    # N2. 넣을 때 값을 응답에 담지 않는다
    def test_n2_set_echoes_key_only(self):
        m = re.search(r'self\._json\(\{"ok": True, "key": key\}\)', self.setter)
        self.assertIsNotNone(m, "set 응답이 키만 담지 않는다")
        self.assertNotIn("val}", self.setter)
        self.assertNotIn('"value"', self.setter.split("self._json")[-1])

    # B2. 파일 권한을 좁힌다 — 같은 머신의 다른 계정이 읽으면 안 된다
    def test_b2_permissions(self):
        self.assertIn("0o700", self.setter)
        self.assertIn("0o600", self.setter)

    # B3. 키 형식을 가린다 — 경로를 벗어나는 이름을 받지 않는다
    def test_b3_key_validated(self):
        self.assertIn("SECRET_KEY_RE.fullmatch", self.setter)
        import importlib.machinery, importlib.util
        spec = importlib.util.spec_from_loader(
            "s9_sec", importlib.machinery.SourceFileLoader("s9_sec", S9))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for bad in ("../x", "a/b", "", "a b"):
            self.assertIsNone(m.SECRET_KEY_RE.fullmatch(bad), bad)
        self.assertIsNotNone(m.SECRET_KEY_RE.fullmatch("API_TOKEN"))

    # F1. 빈 값은 넣지 않는다 — 빈 비밀은 "지워졌나 안 넣었나"를 흐린다
    def test_f1_empty_refused(self):
        self.assertIn("빈 값은 넣지 않는다", self.setter)


if __name__ == "__main__":
    unittest.main()
