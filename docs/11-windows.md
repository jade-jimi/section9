# 11. 순수 Windows 지원 (WSL 아님)

전제: Python 3.9+ 와 Git for Windows 설치. section9 위치는 `%USERPROFILE%\section9`.

## 진입점

- 셔뱅(`#!`)은 Windows에서 동작하지 않으므로 **`.cmd` 래퍼**를 쓴다:
  `bin\s9.cmd`, `bin\s9-install.cmd`, `bin\s9-guard.cmd` (python → py -3 순 탐색).
- PATH에 `%USERPROFILE%\section9\bin` 추가하면 `s9 ...` 그대로 사용 가능.

## 플랫폼 분기 (s9-install이 자동 처리)

| 항목 | POSIX | Windows |
|---|---|---|
| Claude hook command | `{ROOT}/bin/... 2>/dev/null \|\| true` | `python "{ROOT}\bin\..."` (bash 문법 제거 — 스크립트가 자체 fail-safe) |
| skills/agents 배포 | symlink | symlink 시도 → 권한 없으면 **복사 fallback** (`.section9-copy` 마커로 소유 표시, 재설치 시 갱신) |
| git hooks | sh 스크립트 | 동일 — Git for Windows가 sh로 실행, python3→python 자동 탐색 내장 |
| 프롬프트 원문 전달 | stdin pipe | 동일 (`/dev/stdin` 미사용 — 제거됨) |

## 알려진 제약

1. **시간대 이름 해석**: `s9 user config <u> timezone Asia/Seoul` 은 Windows에서
   IANA tz 데이터가 없으면 무시되고 시스템 로컬로 동작한다.
   해결: `pip install tzdata` (선택 사항).
2. **symlink 없이 복사된 skills/agents** 는 리포 갱신이 실시간 반영되지 않는다 —
   `git pull` 후 post-merge hook의 s9-install 재실행이 복사본을 갱신한다.
3. **검증 상태**: 코드 수준 호환 처리는 완료했으나 **실제 Windows 머신 검증은
   아직 안 됐다.** 첫 Windows 사용자 셋업 시 발견되는 문제는 이 문서에 추가할 것.

## Windows 셋업 절차

```bat
git clone <repo-url> %USERPROFILE%\section9
%USERPROFILE%\section9\bin\s9-install.cmd
%USERPROFILE%\section9\bin\s9.cmd user add <이름>
```
