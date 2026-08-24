# 00. Overview

## 문제

- 수십 명이 멀티 모델 / 멀티 계정 / 멀티 머신 / 멀티 세션으로 동시에 LLM 작업을 한다.
- LLM은 컨텍스트 사이즈 제한과 컴팩션 때문에 장기기억이 불가능하다.
- 토큰 리밋에 걸리면 같은 머신의 다른 계정, 다른 세션으로 작업을 이어받아야 하는데,
  이어받는 세션은 이전 컨텍스트가 없다.
- 사람 간 의사소통 없이도 업무를 공유/모니터링/관리할 수 있어야 한다.

## 해법

프롬프트의 모든 것을 audit하고 문서화하여, LLM이 **로컬 파일시스템의 md 문서**를
외부기억으로 사용하게 한다. 즉 만드려는 시스템(JIRA + Confluence + Notion + Obsidian
유사체) 자체가 컨텍스트 한계의 해법이다.

```
사용자 프롬프트 ──▶ request 문서 (메타데이터 + 원문 + 상태)
LLM 작업 결과  ──▶ knowledge 문서 / request History
세션 audit     ──▶ session 문서
                        │
                        ▼
              index/ (catalog.jsonl + by-* md)
                        │
                        ▼
        어떤 user/machine/session의 LLM이든
        catalog → 인덱스 → 문서 순으로 최소 토큰 조회
```

## 인수인계 시나리오

- user1이 m#1, 세션 s#1에서 작업 중 토큰 리밋 → 같은 세션 s#1에 user2 로그인,
  또는 새 세션 s#2에 user2 로그인.
- 어느 경우든 이어받는 쪽은 `s9 ls --status in-progress` 로 진행 중 요청을 찾고,
  해당 문서의 History와 Notes만 읽으면 된다. 문서의 `user/machine/session`
  필드가 누가 어디서 만들었는지 audit 정보를 보존한다.

## 아키텍처 결정

| 결정 | 이유 |
|---|---|
| 로컬 md 파일만 사용, DB 없음 | Obsidian 원칙. 사람이 직접 읽고 고칠 수 있고, git 등으로 동기화 가능 |
| 인덱스는 파생물 (rebuild 가능) | 인덱스 깨짐이 데이터 손실이 되지 않게 |
| catalog.jsonl (기계용) + by-* md (사람/LLM용) 이중 인덱스 | LLM은 jsonl 한 줄 = 문서 하나로 토큰 효율적으로 스캔, 사람은 md로 브라우징 |
| frontmatter는 flat key (중첩 없음) | 파서 단순화, grep 가능성 유지 |
| CLI는 python3 stdlib only | 어떤 머신에서든 의존성 설치 없이 동작 |
| 쓰기 시 lockfile | 멀티 세션 동시 쓰기에서 ID 충돌 방지 |

## 로드맵

- **Phase 1 (완료)** — 문서 포맷 / 디렉토리 구조 / 인덱스 / 검색 / 상태머신 / CLI 최소 구현
- **Phase 2 (완료)** — 웹 시각화: `s9 serve` — kanban(by-status), 문서 브라우저, 링크 그래프 (docs/05)
- **Phase 3 (프롬프트 audit 완료)** — UserPromptSubmit hook으로 프롬프트 → request 문서 자동 생성 (docs/06). 세션 로그(SES) 자동 기록은 후속
- **Phase 4** — 우선 검색(자기 문서 우선), 권한/조직 단위 스코프, incremental index
