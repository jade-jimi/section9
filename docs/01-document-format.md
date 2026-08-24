# 01. Document Format

모든 문서는 **frontmatter(YAML subset) + markdown body**. 파일 인코딩 UTF-8.

## 문서 타입과 ID 체계

| type | prefix | 저장 위치 | 용도 | 기본 status |
|---|---|---|---|---|
| request | REQ | vault/requests/ | 사용자 프롬프트/요청 (JIRA issue에 대응) | open |
| knowledge | DOC | vault/knowledge/ | 지식/설계/결정사항 (Confluence·Notion page에 대응) | published |
| session | SES | vault/sessions/ | 세션 audit 로그 | published |

ID: `{PREFIX}-{YYYYMMDD}-{NNN}` (일 단위 3자리 시퀀스, 예: `REQ-20260821-003`).
파일명 = `{ID}.md`, 경로 = `vault/{subdir}/{YYYY}/{MM}/{ID}.md`.
ID 할당은 lockfile로 직렬화되어 멀티 세션에서도 충돌하지 않는다.

## Frontmatter 스펙

flat key만 사용(중첩 금지). 리스트는 JSON 배열 표기. 빈 값은 키 자체를 생략.

| key | 형식 | 의미 |
|---|---|---|
| id | string | 문서 ID (불변) |
| type | request \| knowledge \| session | 문서 타입 |
| title | string | 제목 |
| summary | string | 한 줄 요약 (인덱스/검색에 노출) |
| goal | string | 요청의 목표 |
| status | string | 상태머신 상태 (docs/03 참조) |
| size | S \| M \| L | 요청 크기 (소/중/대) |
| user | string | 요청자/작성자 계정 |
| machine | string | 작성된 머신 (hostname 또는 $S9_MACHINE) |
| session | string | 작성된 세션 식별자 ($S9_SESSION) |
| project | string | 소속 프로젝트 |
| parent | id | 상위 요청 (파생 요청의 원 요청) |
| children | [id] | 하위/파생 요청 (parent 지정 시 자동 back-link) |
| derived_from | id | 이 문서를 파생시킨 근원 문서 |
| relates | [id] | 관련 문서 (양방향 의미 없음, 단순 참조) |
| refs_docs | [id] | 참조하는 내부 문서 |
| refs_links | [url] | 외부 참조 링크 |
| refs_files | [path] | 참조 파일 (vault/attachments/ 또는 절대경로) |
| tags | [string] | 태그 |
| created | ISO8601 | 생성 시각 (불변) |
| updated | ISO8601 | 마지막 수정 시각 |

## Body 표준 섹션

```markdown
## Original      ← 사용자 프롬프트 원문 (수정 금지, audit 대상)
## Notes         ← 작업 메모, 진행 상황, 결정사항 (자유 편집)
## History       ← append-only 이벤트 로그 (생성/상태전이가 자동 기록)
- 2026-08-21T10:00:00+09:00 created by user1 (status: open)
- 2026-08-21T11:00:00+09:00 status: open -> in-progress (by user2) — m#2에서 이어받음
```

- `Original`은 불변 — 프롬프트 audit의 근거.
- `History`는 append-only — 누가 언제 무엇을 했는지의 타임라인. 세션 인수인계 시
  이 섹션만 읽으면 맥락 복원 가능.
- Obsidian 호환: body 안에서 `[[REQ-20260821-001]]` wiki link 사용 가능
  (Obsidian으로 vault/를 열면 그래프로 보인다).

## 예시

```markdown
---
id: REQ-20260821-002
type: request
title: 문서 포맷 설계
summary: frontmatter 스펙과 body 표준 섹션 정의
status: done
size: M
user: user1
machine: m1
project: section9
parent: REQ-20260821-001
tags: ["design", "format"]
created: 2026-08-21T10:00:00+09:00
updated: 2026-08-21T12:00:00+09:00
---

## Original
...
```
