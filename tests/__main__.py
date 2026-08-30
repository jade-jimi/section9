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
import jobfile  # noqa: E402  — 긴 실행의 존재를 대시보드에 알린다 (REQ-20260830-022)


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


REPO = os.path.dirname(HERE)
# 스모크 계층 (REQ-20260830-029, quality-assurance 선정): 핵심 계약 12파일,
# 20초대 목표. --smoke 로 부른다. 목록을 고칠 때는 그 REQ 의 근거 노트를 함께.
SMOKE = ("test_state_truth.py", "test_catalog_atomic.py",
         "test_commit_gate.py", "test_note_guard.py", "test_relates_why.py",
         "test_review_point_len.py", "test_changed_select.py",
         "test_jobs_shard.py", "test_stall_trust.py", "test_wake.py",
         "test_closed_no_worker.py", "test_stdlib_only.py")
GREEN_STAMP = os.path.join(REPO, "state", "tests-last-green")
# 이 파일들이 바뀌면 어느 시험이 닿는지 셀 수 없다 — 전체로 물러난다.
COMMON = ("bin/s9", "tests/__main__.py", "tests/portpool.py",
          "tests/tmproot.py", "tests/jobfile.py", "tests/precious.py")


def _git(repo, *a):
    import subprocess
    try:
        r = subprocess.run(["git", *a], capture_output=True, text=True,
                           cwd=repo, timeout=30)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def changed_selection(repo=None, here=None, stamp=None):
    """--changed 의 선택 (REQ-20260830-027 1단계).

    마지막 전체 green 스탬프 이후 바뀐 파일에 닿는 시험만 고른다 — 같은 날
    전체 스위트를 다섯 번 돌린 낭비가 이 스위치의 존재 이유다.
    반환: None(전체 폴백) · [](돌 것 없음) · [디스커버리 패턴…].
    보수 쪽으로 기운다: 스탬프가 없거나 git 이 안 되면 전체, 미커밋 변경도
    변경으로 센다(더러운 트리에서 놓치는 것보다 다시 도는 게 낫다)."""
    repo = repo or REPO
    here = here or HERE
    stamp = stamp or GREEN_STAMP
    try:
        with open(stamp, encoding="utf-8") as f:
            base = f.read().strip()
    except OSError:
        return None
    if not base:
        return None
    diff = _git(repo, "diff", "--name-only", f"{base}..HEAD")
    porc = _git(repo, "status", "--porcelain")
    if diff is None or porc is None:
        return None      # git 이 안 되면 전체로 물러난다 — 좁게 틀리지 않는다
    files = {ln.strip() for ln in diff.splitlines() if ln.strip()}
    files |= {ln[3:].strip() for ln in porc.splitlines() if len(ln) > 3}
    files.discard("")
    # 문서·상태는 시험을 유발하지 않는다
    files = {f for f in files
             if not f.startswith(("vault/", "state/", "docs/", "projects/",
                                  "users/"))}
    if not files:
        return []
    for f in files:
        if f in COMMON or f.startswith("bin/s9-"):
            return None
    pats, code_basenames = set(), set()
    for f in files:
        b = os.path.basename(f)
        if f.startswith("tests/test_") and f.endswith(".py"):
            pats.add(b)
        else:
            code_basenames.add(b)
    if code_basenames:
        for fn in os.listdir(here):
            if not (fn.startswith("test_") and fn.endswith(".py")):
                continue
            try:
                body = open(os.path.join(here, fn), encoding="utf-8").read()
            except OSError:
                continue
            if any(b in body for b in code_basenames):
                pats.add(fn)
    return sorted(pats)


def write_green_stamp(repo=None, stamp=None):
    """전체 green 만 스탬프를 쓴다 — 부분·실패 실행이 쓰면 --changed 가 거짓말한다."""
    repo = repo or REPO
    stamp = stamp or GREEN_STAMP
    head = (_git(repo, "rev-parse", "HEAD") or "").strip()
    if not head:
        return
    try:
        os.makedirs(os.path.dirname(stamp), exist_ok=True)
        with open(stamp, "w", encoding="utf-8") as f:
            f.write(head + "\n")
    except OSError:
        pass


# 공유 상태(실제 repo state/·9909 포트·포트 슬롯 자체)를 만지는 시험 — 병렬
# 본대에 넣으면 서로(또는 자식들의 포트 슬롯을) 밟는다. 부모가 직렬로 돈다.
SERIAL = ("test_jobfile.py", "test_runner_patterns.py", "test_tmp_hygiene.py",
          "test_port_pool.py", "test_install_hooks_path.py",
          "test_doctor_system.py",
          # 계정 전환 live 시험 — 계정 전역 상태를 만져 병렬에서만 흔들린다
          # (2026-08-30 19:26 실측: 단독 4회 green, --jobs 에서 1회 red).
          "test_claude_usage.py")


def shard(files, n):
    """파일들을 무게(크기) 내림차순 greedy 로 N 빈에 — 느린 것부터 자리 잡아야
    꼬리가 짧다 (REQ-20260830-027 2단계). 반환: 빈 리스트들(빈 빈 제외)."""
    bins = [[0, []] for _ in range(max(1, n))]
    for f in sorted(files, key=lambda x: -os.path.getsize(
            os.path.join(HERE, x))):
        b = min(bins, key=lambda x: x[0])
        b[0] += os.path.getsize(os.path.join(HERE, f))
        b[1].append(f)
    return [b[1] for b in bins if b[1]]


def matched_files(pats):
    """디스커버리 패턴들이 고르는 시험 파일 목록 (파일 단위 샤딩용)."""
    import fnmatch
    out = []
    for fn in sorted(os.listdir(HERE)):
        if fn.startswith("test_") and fn.endswith(".py") and                 any(fnmatch.fnmatch(fn, p) for p in pats):
            out.append(fn)
    return out


def run_sharded(pats, jobs, bump=None):
    """병렬 본대 + 직렬 꼬리 (REQ-20260830-027 2단계).

    자식은 `python3 tests/ <파일…>` + S9_TESTS_NESTED=1 — reap·잡파일·바깥
    sweep 을 건드리지 않고 tmproot 는 pid 별로 저절로 격리된다. 실패한 자식의
    원출력은 그대로 재생한다 — 병렬 뒤에 실패가 숨으면 이 구조 전체가 거짓이
    된다. 반환: (ok, 돈 파일 수)."""
    import subprocess
    import tempfile
    files = matched_files(pats)
    body = [f for f in files if f not in SERIAL]
    tail = [f for f in files if f in SERIAL]
    procs = []
    env = {**os.environ, "S9_TESTS_NESTED": "1"}
    for group in shard(body, jobs):
        out = tempfile.NamedTemporaryFile(mode="w+", suffix=".shard",
                                          delete=False)
        pr = subprocess.Popen(
            [sys.executable, HERE, *group],
            stdout=out, stderr=subprocess.STDOUT, env=env)
        procs.append((pr, out, group))
    ok = True
    done_files = 0
    import time as _time
    pending = list(procs)
    while pending:
        _time.sleep(0.5)
        still = []
        for pr, out, group in pending:
            if pr.poll() is None:
                still.append((pr, out, group))
                continue
            done_files += len(group)
            if bump:
                bump(done_files)
            if pr.returncode != 0:
                ok = False
                out.flush()
                try:
                    sys.stderr.write(open(out.name, encoding="utf-8",
                                          errors="replace").read())
                except OSError:
                    pass
                print(f"실패한 샤드: {' '.join(group)}", file=sys.stderr)
        pending = still
    for pr, out, _g in procs:
        try:
            out.close()
            os.unlink(out.name)
        except OSError:
            pass
    for f in tail:      # 직렬 꼬리 — 부모 프로세스에서, 공유 상태를 독점하고
        r = subprocess.run([sys.executable, HERE, f], env=env)
        done_files += 1
        if bump:
            bump(done_files)
        if r.returncode != 0:
            ok = False
    return ok, done_files


def patterns(argv):
    """인자들을 discovery 패턴으로 바꾼다 (REQ-20260829-006).

    커밋 게이트는 담긴 테스트 이름을 **여럿** 넘긴다. 예전에는 sys.argv[1] 만
    써서 두 번째부터는 아무 말 없이 안 돌았고, 게이트는 그걸 통과로 읽었다.

    'x' · 'test_x' · 'tests/test_x.py' 세 형태를 모두 받는다.
    """
    out = []
    for a in argv:
        raw = (a or "").strip().removeprefix("tests/")
        # 정확한 파일명은 넓히지 않는다 (REQ-20260830-029): --smoke·--changed 가
        # 고른 test_wake.py 를 test_*wake*.py 로 넓히면 wake 계열 전부가
        # 끌려와 계층·선택의 뜻이 사라진다. 사람이 치는 조각(wake)만 넓힌다.
        if raw.startswith("test_") and raw.endswith(".py"):
            out.append(raw)
            continue
        frag = raw.removesuffix(".py").removeprefix("test_")
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
        raw = sys.argv[1:]
        jobs = 0
        if "--jobs" in raw:
            i = raw.index("--jobs")
            jobs = int(raw[i + 1]) if i + 1 < len(raw) else 4
            raw = raw[:i] + raw[i + 2:]
        # --smoke: 핵심 계약 12파일 · --gate: 스모크 ∪ --changed (커밋 게이트용,
        # QA 판정: --changed 단독은 bin/s9 변경이 전체 폴백이라 게이트로 부족)
        smoke = "--smoke" in raw or "--gate" in raw
        if "--gate" in raw and "--changed" not in raw:
            raw.append("--changed")
        argv = [a for a in raw
                if a not in ("--changed", "--smoke", "--gate")]
        full_requested = not argv and not smoke
        sel = None
        if "--changed" in raw:
            sel = changed_selection()
            if sel == [] and not smoke:
                print("변경 없음 — 마지막 전체 green 이후 시험에 닿는 파일이 "
                      "바뀌지 않았다. 아무것도 돌리지 않는다.", file=sys.stderr)
                return 0
            if sel is not None:
                argv = sel          # 파일명 자체가 부분일치 패턴으로 먹힌다
                full_requested = False
            elif smoke:
                argv = []           # --gate 에서 전체 폴백이면 스모크 ∪ 전체 = 전체
                smoke_full_fallback = True
            # None 이면 전체 폴백 — argv 그대로(비어 있음 = 전체)
        if smoke and not (sel is None and "--gate" in sys.argv[1:]):
            argv = sorted(set(argv) | set(SMOKE))
            full_requested = False
        pats = patterns(argv)
        if jobs > 1 and not nested:
            files = matched_files(pats)
            if not files:
                print(f"no tests matched: {', '.join(pats)}", file=sys.stderr)
                return 1
            bump, clear = jobfile.start(len(files),
                                        args=" ".join(sys.argv[1:4]))
            try:
                ok, _n = run_sharded(pats, jobs, bump=bump)
            finally:
                clear()
            if ok and full_requested:
                write_green_stamp()
            return 0 if ok else 1
        suite, empty = discover(pats)
        for p in empty:
            print(f"no tests matched: {p}", file=sys.stderr)
        if suite.countTestCases() == 0:
            return 1
        # 잡 파일 (REQ-20260830-022): 이 실행이 도는 동안 화면 헤더 칩과 카드가
        # "테스트 N분째 · M건" 을 그린다. 안쪽 실행(S9_TESTS_NESTED)은 안 쓴다.
        bump, clear = jobfile.start(suite.countTestCases(),
                                    args=" ".join(sys.argv[1:4]))

        class _Result(unittest.TextTestResult):
            def stopTest(self, test):
                super().stopTest(test)
                bump(self.testsRun)
        try:
            res = unittest.TextTestRunner(verbosity=2,
                                          resultclass=_Result).run(suite)
        finally:
            clear()
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
    if ok and full_requested and not nested:
        write_green_stamp()     # 전체 green 만 --changed 의 기준점이 된다
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
