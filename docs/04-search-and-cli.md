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

## 환경변수

| 변수 | 용도 | 기본값 |
|---|---|---|
| S9_ROOT | 저장소 루트 | ~/section9 |
| S9_USER | 문서 작성자 | OS 계정명 |
| S9_MACHINE | 머신 식별자 | hostname |
| S9_SESSION | 세션 식별자 | (빈 값) |

멀티 계정/머신/세션 audit의 핵심 — 각 Claude 세션 시작 시 이 변수들을
설정해두면 모든 문서에 출처가 찍힌다.
