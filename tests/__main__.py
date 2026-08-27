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
sys.path.insert(0, HERE)

import portpool  # noqa: E402  (경로를 세운 뒤에 부른다)


def _reap(label):
    """스위트가 사용자 대시보드 포트에 남긴 서버를 거둔다 (REQ-20260828-001).

    남으면 진짜 서버와 번갈아 응답해 화면이 404 를 내거나, 더 나쁘게는
    테스트 시작 시점의 옛 화면을 내줘 눈으로 하는 검증을 조용히 속인다.
    """
    reaped = portpool.reap_stray_dashboard_servers()
    for p in reaped:
        print(f"[포트 회수/{label}] {portpool.describe_stray(p)}",
              file=sys.stderr)
    return reaped


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
    _reap("시작 전")          # 지난 실행의 잔재는 이번 실행의 책임이 아니다
    try:
        res = unittest.TextTestRunner(verbosity=2).run(suite)
        ok = res.wasSuccessful()
    finally:
        leaked = _reap("끝난 뒤")
    if leaked:
        # 거뒀더라도 실패로 센다 — 조용히 치우면 다음에 또 생긴다.
        print(f"실패: 테스트가 사용자 대시보드 포트에 서버 {len(leaked)}개를 "
              f"남겼다(거뒀다). 세션 훅을 돌리는 테스트는 S9_PORT 로 격리하라.",
              file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
