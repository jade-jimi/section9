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
import tmproot  # noqa: E402  — portpool 다음에: 포트 락은 /tmp 공용이어야 한다


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


def patterns(argv):
    """인자들을 discovery 패턴으로 바꾼다 (REQ-20260829-006).

    커밋 게이트는 담긴 테스트 이름을 **여럿** 넘긴다. 예전에는 sys.argv[1] 만
    써서 두 번째부터는 아무 말 없이 안 돌았고, 게이트는 그걸 통과로 읽었다.

    'x' · 'test_x' · 'tests/test_x.py' 세 형태를 모두 받는다.
    """
    out = []
    for a in argv:
        frag = (a or "").strip().removeprefix("tests/").removesuffix(".py")
        frag = frag.removeprefix("test_")
        if frag:
            out.append(f"test_*{frag}*.py")
    return out or ["test_*.py"]


def flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from flatten(t)
        else:
            yield t


def discover(pats):
    """패턴마다 모아 합친다. 반환: (스위트, 아무것도 못 고른 패턴들).

    같은 파일이 두 패턴에 걸리면 테스트 id 로 한 번만 담는다 — 두 번 도는 것은
    낭비이고, 상태를 쓰는 테스트에서는 두 번째가 첫 번째의 잔재를 본다.
    """
    seen, cases, empty = set(), [], []
    for pat in pats:
        picked = 0
        for t in flatten(unittest.defaultTestLoader.discover(HERE,
                                                             pattern=pat)):
            picked += 1
            tid = t.id()
            if tid in seen:
                continue
            seen.add(tid)
            cases.append(t)
        if picked == 0:
            empty.append(pat)
    return unittest.TestSuite(cases), empty


def main():
    # 스위트 안에서 러너를 또 띄우는 시험이 있다(test_runner_patterns·
    # test_tmp_hygiene). 그 안쪽 실행이 바깥 실행의 세계를 청소하면 안 된다 —
    # 포트 회수는 '임시 작업공간에서 뜬 대시보드 서버'를 죽이는데, 그게 바로
    # 바깥 스위트가 지금 쓰고 있는 서버일 수 있다. 안쪽은 제 임시 루트만 챙긴다.
    nested = os.environ.get("S9_TESTS_NESTED") == "1"
    if not nested:
        _reap("시작 전")      # 지난 실행의 잔재는 이번 실행의 책임이 아니다
        stale = tmproot.sweep_stale()
        if stale:
            print(f"[임시자리 회수/시작 전] 지난 실행 잔재 {len(stale)}개",
                  file=sys.stderr)
    # 이 실행이 만드는 임시 자리는 전부 여기 안에 생기고 끝나면 함께 사라진다
    # (REQ-20260829-003). 84개 파일에 tearDown 을 심는 대신 문을 여기서 닫는다.
    #
    # **discovery 보다 먼저** 세운다. discovery 는 테스트 모듈을 import 하는데,
    # 여럿이 모듈 수준에서 `TMP = tempfile.mkdtemp(...)` 를 부른다(test_tags,
    # test_session_wake, test_link_integrity, …). 루트를 나중에 세우면 그것들이
    # 문 밖에 생겨 그대로 남는다 — 전체 스위트 1회에 22개가 그렇게 샜다.
    tmp_root, prev_tmpdir = tmproot.make_run_root()
    ok, empty, leaked = False, [], []
    try:
        pats = patterns(sys.argv[1:])
        suite, empty = discover(pats)
        for p in empty:
            print(f"no tests matched: {p}", file=sys.stderr)
        if suite.countTestCases() == 0:
            return 1
        res = unittest.TextTestRunner(verbosity=2).run(suite)
        ok = res.wasSuccessful()
    finally:
        left = tmproot.drop_run_root(tmp_root, prev_tmpdir)
        if left:
            # 거두되 조용히 치우지 않는다 — 접두어가 범인을 가리킨다.
            head = ", ".join(left[:8]) + (" …" if len(left) > 8 else "")
            print(f"[임시자리 회수/끝난 뒤] 테스트가 남긴 {len(left)}개를 "
                  f"거뒀다: {head}", file=sys.stderr)
        leaked = [] if nested else _reap("끝난 뒤")
    if leaked:
        # 거뒀더라도 실패로 센다 — 조용히 치우면 다음에 또 생긴다.
        print(f"실패: 테스트가 사용자 대시보드 포트에 서버 {len(leaked)}개를 "
              f"남겼다(거뒀다). 세션 훅을 돌리는 테스트는 S9_PORT 로 격리하라.",
              file=sys.stderr)
        return 1
    if empty:
        # 고른 것이 다 통과해도 실패다 — 커밋 게이트는 "담긴 테스트가
        # 통과했다"고 판정하는데, 안 돈 것이 통과로 보이면 그 판정이 거짓이 된다.
        print(f"실패: 고르지 못한 패턴 {len(empty)}개 — {', '.join(empty)}",
              file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
