# 04. Search & CLI Reference

## 검색 전략 (토큰 효율 순서)

LLM이든 사람이든 넓은 것부터 좁혀 들어간다. 각 단계의 출력은 "한 줄 = 문서 하나".

1. **catalog 스캔** — `s9 ls [필터]` : 메타데이터만, 본문 안 읽음. 가장 저렴.
2. **메타데이터 검색** — `s9 search <terms> [필터]` : id/title/summary/tags/project
   에서 모든 term의 AND substring 매치 (대소문자 무시).
3. **본문 검색** — `s9 search <terms> --body [필터]` : 파일 본문까지 grep,
   매치 라인을 `id:line: 내용` 으로 출력 (라인당 120자 제한 → 토큰 절약).
4. **문서 조회** — `s9 show <id> --meta` (frontmatter만) → 필요할 때만 `s9 show <id>` 전체.

공통 필터: `--user --status --project --tag --type --since --until --limit`
→ "사용자 우선 검색"은 `--user` 로 1차 시도 후 필터를 풀어 확장하는 패턴.

CLI 없이도 동작하는 저수준 경로 (grep/jq 친화 설계의 이유):

```bash
jq -c 'select(.status=="in-progress")' index/catalog.jsonl
grep -rl "키워드" vault/requests/2026/08/
cat index/by-user/user1.md
```

## CLI Reference

### s9 new {request|knowledge|session}

```
s9 new request --title T [--summary S] [--goal G] [--size S|M|L]
   [--user U] [--project P] [--parent ID] [--derived-from ID]
   [--relates ID]... [--ref-doc ID]... [--ref-link URL]... [--ref-file PATH]...
   [--tag TAG]... [--status ST] [--body TEXT | --body-file F | stdin]
```

- 원문(body)은 `## Original` 섹션에 저장된다. stdin 파이프 지원:
  `echo "프롬프트 원문" | s9 new request --title ...`
- `--parent` 지정 시 부모 문서의 `children`에 자동 back-link.
- user/machine/session은 `--user`, `$S9_USER`, `$S9_MACHINE`, `$S9_SESSION`
  환경변수로 주입 (미지정 시 OS 계정명/hostname).
- 출력: `ID  상대경로` 한 줄.

### s9 show ID [--meta]
### s9 ls [필터]
### s9 search TERM... [--body] [필터]

### s9 status ID NEW_STATUS [--note TEXT] [--user U] [--force]

상태머신 검증 후 전이, History에 append, 인덱스 갱신.

### s9 link ID [--parent ID] [--derived-from ID] [--relates ID]... [--ref-doc]... [--ref-link]... [--ref-file]... [--tag]...

기존 문서에 관계/참조/태그 추가 (리스트는 중복 없이 append).

### s9 index rebuild

vault 전체 스캔 → catalog.jsonl + index/by-* 재생성. 모든 쓰기 명령이
자동 수행하므로 평소엔 불필요. 인덱스 의심 시 언제든 실행.

### s9 init

디렉토리 골격 생성 (새 머신 셋업용). `S9_ROOT` 로 루트 변경 가능.

### s9 doctor [--fix] [--recover] [--yes] [--json]

네트워크·자원 진단과 회수. 본체는 `bin/s9-doctor` — `s9` 가 못 뜨는 상황에서도
써야 하므로 독립 실행 가능한 별도 파일이다.

진단은 **새 리스닝 포트가 호스트에 공개되기까지의 지연을 초 단위로 잰다**.
WSL(virtioproxy)은 포트를 열자마자 접속 가능한 게 아니라 호스트에 공개하는
단계를 거치는데, 평소 1초 미만이던 이 지연이 늘어나면 서버 기동 대기가 짧은
코드부터 실패한다 — 증상이 "방화벽이 막았다"처럼 보여 OS 재시작으로 오대응하기 쉽다.

함께 보는 것이 **윈도우 동적 포트 소진도**(49152~65535, 16,384개)다.
WSL이 포트를 공개할 때마다 호스트의 동적 포트를 소비하는데, 중계 프로세스가
이를 반환하지 않고 쌓으면 범위가 마르고 윈도우 앱까지 WSAENOBUFS
(브라우저의 `ERR_NO_BUFFER_SPACE`)를 본다. 60% 에서 경고(△), 85% 부터
치명(✗)으로 표시한다 — 고갈된 뒤가 아니라 임계에서 먼저 알린다.

- `--fix` — 우리가 흘린 자원만 회수한다(고아 테스트 서버·좀비 헤드리스 브라우저). 비파괴.
- `--recover` — 동적 포트를 독차지한 **WSL 포트 중계 COM 대리 프로세스**를 종료해
  포트를 즉시 반환시킨다. 확인 후 실행하며 `--yes` 로 생략할 수 있다.
  대상은 (1) 범위의 30% 이상을 혼자 점유하고 (2) `dllhost.exe` 인 프로세스뿐 —
  사용자의 브라우저·앱은 아무리 많이 잡고 있어도 죽이지 않고 안내만 한다.
  중계는 필요할 때 자동으로 다시 뜨므로 `wsl --shutdown` 보다 훨씬 덜 파괴적이다
  (실행 중인 세션·에이전트가 살아남는다).

조치는 항상 **덜 파괴적인 순서**로 안내한다: `--fix` → 캡처·서버 기동 중단 →
대기 → `--recover` → 마지막에 `wsl --shutdown`. 단, 호스트 포트가 이미
고갈(85%↑)됐다면 리눅스 쪽 회수로는 풀리지 않으므로 `--recover` 를 첫 조치로 올린다.

실사례(2026-08-25): 캡처 40~60회로 `chrome.exe` 165개가 쌓이면서 중계
프로세스가 동적 포트 15,709개를 점유 → 새 포트 공개 실패로 테스트 29건
connection refused, 대시보드 접속 불가, 캡처 실패가 동시에 발생했다.

## 환경변수

| 변수 | 용도 | 기본값 |
|---|---|---|
| S9_ROOT | 저장소 루트 | ~/section9 |
| S9_USER | 문서 작성자 | OS 계정명 |
| S9_MACHINE | 머신 식별자 | hostname |
| S9_SESSION | 세션 식별자 | (빈 값) |

멀티 계정/머신/세션 audit의 핵심 — 각 Claude 세션 시작 시 이 변수들을
설정해두면 모든 문서에 출처가 찍힌다.
