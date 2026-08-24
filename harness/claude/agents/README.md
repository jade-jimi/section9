# 공용 에이전트 로스터 (26종)

`s9-install`이 이 디렉토리의 `*.md`(README 제외)를 `~/.claude/agents/`로 심링크한다.
section9 사용자 전원이 동일한 에이전트를 쓰며, git으로 동기화된다.
사용자별 에이전트는 `users/<name>/agents/`.

## 공통 규칙 (모든 에이전트)

- 각 에이전트는 **guru 수준 정체성** + **전문 영역 기준** + **필수 스킬** + **산출물 기준**을 내장한다.
- **스킬 강제 로드**: 작업 시작 전 지정 스킬을 반드시 로드한다. Skill 도구가 없으면
  `harness/claude/skills/<이름>/SKILL.md`를 직접 Read한다. 스킬 미확인 상태의 산출물은 금지.
- 모든 에이전트는 `s9-protocol` 스킬을 공통 로드해 section9 작업 규약(기록/조회/상태)을 따른다.

## 역할군 × 필수 스킬

| 역할군 | 에이전트 | 필수 스킬 |
|---|---|---|
| **기획·제품** | project-manager | s9-protocol + product-discovery |
| | product-owner | s9-protocol + product-discovery |
| | architect | s9-protocol + eng-principles |
| | staff-engineer | s9-protocol + eng-principles + **tdd** + review-discipline |
| **디자인·문서** | designer | s9-protocol + s9-design + **browser-verify** + writing-clarity |
| | ux-writer | s9-protocol + writing-clarity |
| | document-writer | s9-protocol + writing-clarity |
| | document-reader | s9-protocol + research-method |
| **개발** | frontend-developer | s9-protocol + eng-principles + **tdd** + s9-design + browser-verify |
| | backend-developer | s9-protocol + eng-principles + **tdd** |
| | ios-developer | s9-protocol + eng-principles + **tdd** |
| | android-developer | s9-protocol + eng-principles + **tdd** |
| **데이터·AI** | data-engineer | s9-protocol + data-practice + eng-principles |
| | database-administrator | s9-protocol + data-practice + ops-practice |
| | data-analyst | s9-protocol + data-practice + research-method |
| | ml-engineer | s9-protocol + data-practice + ops-practice |
| | ai-engineer | s9-protocol + data-practice + eng-principles |
| **인프라·보안** | devops-engineer | s9-protocol + ops-practice + testing-discipline |
| | cloud-engineer | s9-protocol + ops-practice + security-practice |
| | security-engineer | s9-protocol + security-practice + review-discipline |
| | white-hacker | s9-protocol + security-practice + testing-discipline |
| **품질·실행** | quality-assurance | s9-protocol + testing-discipline + **browser-verify** + review-discipline |
| | code-reviewer | s9-protocol + review-discipline + eng-principles |
| | code-executor | s9-protocol + testing-discipline |
| | test-executor | s9-protocol + testing-discipline + **browser-verify** |
| **조사** | deep-diver | s9-protocol + research-method + testing-discipline |

## 스킬 (11종) — 사용 에이전트 수

`harness/claude/skills/`에 자체 작성(외부 마켓플레이스 비의존, 자기완결).

| 스킬 | 내용 | 사용 |
|---|---|---|
| s9-protocol | section9 외부기억 작업 규약 | 26 (전원) |
| eng-principles | 소프트웨어 설계·구현 품질 기준 | 9 |
| testing-discipline | 테스트 설계·실행·격리 기준 | 6 |
| data-practice | 데이터 모델링·파이프라인·분석 | 5 |
| ops-practice | 배포·인프라·운영 신뢰성 | 4 |
| review-discipline | 코드 리뷰·품질 검증 방법론 | 4 |
| security-practice | 보안 설계·감사·공격 표면 | 3 |
| research-method | 심층 조사·문서 독해 방법론 | 3 |
| writing-clarity | 사용자 대상 글·문서 명료성 | 3 |
| tdd | Test-Driven Development 필수 규율 (개발 직군) | 5 |
| browser-verify | 실브라우저 UI 검증 (WSL→Windows 포함) | 4 |
| s9-design | 대시보드 디자인 시스템 | 2 |
| product-discovery | 문제 정의·우선순위·요구사항 | 2 |

## 확장

- 새 역할 = 이 디렉토리에 `<name>.md` 추가(정체성/스킬/기준/산출물), `s9-install` 재실행.
- 새 스킬 = `skills/<name>/SKILL.md` 추가 후 관련 에이전트의 필수 스킬 목록에 편입.
- 사용자 전용 역할/스킬은 `users/<name>/agents|skills/`.
