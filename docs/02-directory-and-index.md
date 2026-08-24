# 02. Directory Structure & Index Design

## 디렉토리 구조

```
section9/
├── bin/s9                        # CLI
├── docs/                         # 이 설계 문서들
├── vault/                        # ★ source of truth — 모든 문서
│   ├── requests/YYYY/MM/*.md     # REQ-*
│   ├── knowledge/YYYY/MM/*.md    # DOC-*
│   ├── sessions/YYYY/MM/*.md     # SES-*
│   └── attachments/              # 첨부 파일 (refs_files가 가리킴)
├── index/                        # ★ 파생물 — 항상 재생성 가능
│   ├── catalog.jsonl             # 기계용 master index
│   ├── by-user/{user}.md
│   ├── by-status/{status}.md
│   ├── by-project/{project}.md
│   ├── by-tag/{tag}.md
│   └── by-date/{YYYY-MM}.md
└── .s9.lock                      # 쓰기 lock (일시적)
```

- vault 내 연/월 디렉토리는 물리적 파티셔닝(디렉토리당 파일 수 제한)이자
  기간별 1차 인덱스 역할.
- `S9_ROOT` 환경변수로 루트 변경 가능 (테스트, 프로젝트별 분리).

## 이중 인덱스

### catalog.jsonl — 기계/LLM용 master index

1 문서 = 1 line JSON. 필드: id, type, title, summary, status, size, user,
project, parent, tags, created, updated, path.

- LLM이 가장 적은 토큰으로 전체 상황을 파악하는 진입점.
  본문을 읽기 전에 catalog로 후보를 좁힌다.
- `s9 ls` / `s9 search` 는 catalog만 읽는다 (본문 검색은 `--body`일 때만).
- jq/grep으로도 직접 질의 가능: `jq -c 'select(.user=="user1")' index/catalog.jsonl`

### by-* md — 사람/LLM 브라우징용 복합 인덱스

같은 문서가 여러 축에 동시에 등장한다 (복합적·입체적 인덱싱):

| 축 | 파일 | 답하는 질문 |
|---|---|---|
| by-user | user1.md | "내(그) 문서 우선 검색" |
| by-status | in-progress.md | "지금 진행 중/방치된 요청은?" (모니터링) |
| by-project | section9.md | "이 프로젝트의 모든 작업" |
| by-tag | bug.md | "주제별 횡단 조회" |
| by-date | 2026-08.md | "기간별 조회" |

각 라인 형식 (한 줄 = 문서 하나, 경로 포함 → 바로 열 수 있음):

```
- [REQ-20260821-002] 문서 포맷 설계 — done · user1 · 2026-08-21 · section9 #design → vault/requests/2026/08/REQ-20260821-002.md
```

## Rebuild 의미론

- `s9 index rebuild` = vault 전체 스캔 → catalog.jsonl과 by-* 전부 삭제 후 재생성.
- 모든 쓰기 명령(new/status/link)은 끝에 자동 rebuild를 수행한다.
  Phase 1에서는 full rebuild(문서 수백 개까지는 충분히 빠름),
  문서가 수천 개가 되면 incremental update로 전환 (Phase 4).
- 인덱스가 의심되면 언제든 rebuild — 데이터 손실 위험 0.

## 동시성 (멀티 세션/멀티 유저, 같은 파일시스템)

- 쓰기 명령은 `.s9.lock` (O_CREAT|O_EXCL) 획득 후 진행, 종료 시 해제.
  ID 시퀀스 할당 충돌과 rebuild 중첩을 막는다.
- 읽기(ls/search/show)는 lock 불필요.
- 멀티 **머신** 간 공유는 Phase 1 범위 밖 — vault를 git/syncthing 등으로
  동기화하는 것을 전제로 하고, 충돌 단위가 "파일 하나 = 문서 하나"라서
  merge 충돌 면적이 최소화되도록 설계되어 있다 (ID에 날짜+시퀀스,
  History는 append-only).

## 우선 검색 (사용자별)

Phase 1: `--user` 필터를 명시적으로 사용 (`s9 ls --user $S9_USER` 먼저,
필요 시 필터 없이 확장). Phase 4에서 기본 정렬에 자기 문서 우선 가중치 도입.
