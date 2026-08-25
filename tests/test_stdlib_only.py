"""의존성 0 정책 가드 (REQ-20260824-003, pyproject.toml 참조).

bin/의 실행 파일과 tests/의 테스트가 표준 라이브러리 밖 모듈을 import하면 실패한다.
서드파티 도입은 pyproject.toml dependencies에 선언하는 결정과 함께만 허용.
실행: python3 tests/test_stdlib_only.py
"""
import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def py_sources():
    out = []
    for name in os.listdir(os.path.join(ROOT, "bin")):
        p = os.path.join(ROOT, "bin", name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    head = f.readline()
                if "python" in head:
                    out.append(p)
            except (OSError, UnicodeDecodeError):
                pass
    for name in os.listdir(HERE):
        if name.endswith(".py"):
            out.append(os.path.join(HERE, name))
    return out


def local_helpers():
    """tests/ 안의 우리 헬퍼 모듈 — 설치가 필요 없으니 서드파티가 아니다.

    (REQ-20260825-100: portpool 처럼 여러 테스트가 공유하는 규율 모듈.)
    """
    return {n[:-3] for n in os.listdir(HERE)
            if n.endswith(".py") and not n.startswith("test_")
            and n != "__main__.py"}


class TestStdlibOnly(unittest.TestCase):
    def test_no_third_party_imports(self):
        allowed = set(sys.stdlib_module_names) | local_helpers()
        bad = []
        for path in py_sources():
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                        and node.module:
                    mods = [node.module.split(".")[0]]
                for m in mods:
                    if m not in allowed:
                        bad.append(f"{os.path.relpath(path, ROOT)}: import {m}")
        self.assertFalse(bad, "표준 라이브러리 밖 import 발견 — pyproject.toml에 "
                              "의존성 선언 + 정책 결정 없이 금지:\n" + "\n".join(bad))

    def test_sources_found(self):
        # 가드가 빈 목록을 검사하며 헛통과하지 않는지
        srcs = py_sources()
        self.assertGreaterEqual(len(srcs), 5, srcs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
