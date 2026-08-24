"""tests 패키지 실행기 — `python3 tests/ [패턴]` 으로 스위트 실행.

무인(auto-resume) 봉투의 allowlist `Bash(python3 tests/:*)` 는 word-boundary
매칭이라 `python3 tests/test_x.py` 형태를 허용하지 못한다 — 디렉토리 실행
형태(`python3 tests/` + 인자)는 허용되므로 이 러너가 그 진입점이다.

usage:
  python3 tests/                # 전체 (test_*.py discovery)
  python3 tests/ project_assets # 파일명 부분일치 필터
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    pattern = "test_*.py"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        frag = sys.argv[1].strip().removeprefix("tests/").removesuffix(".py")
        frag = frag.removeprefix("test_")
        pattern = f"test_*{frag}*.py"
    suite = unittest.defaultTestLoader.discover(HERE, pattern=pattern)
    if suite.countTestCases() == 0:
        print(f"no tests matched: {pattern}", file=sys.stderr)
        return 1
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
