# 03. Request State Machine

모든 request는 상태를 가진다. 목적: **어떤 요청도 의도치 않게 방치/누락되지 않게**
상태로 감시 가능하게 만드는 것. `s9 ls --status open` / `--status blocked` 가
곧 모니터링 대시보드다.

**review vs blocked 구분 (중요)**: `review`는 오직 **사람의 판정이 필요한 것**만.
"다른 요청이 끝나야 진행 가능"은 review가 아니라 `blocked`(의존성 대기)로 두고
note에 대기 대상 REQ를 명시한다. 자동 처리·의존 대기를 review에 넣으면 사람이
불필요하게 판정 대상으로 오해한다.

**done vs review 정책 (2026-08-23 사용자 결정)**: **검증된 것은 done, 방향만 review.**
- TDD 통과·실브라우저/CLI 검증 등 **객관적 검증 증거가 있는 구현**은 review를 거치지
  말고 바로 `done`. 문제가 있으면 사용자가 대시보드에서 반려(→in-progress)하면 되고,
  그 반려는 자동 감지·재개된다(docs/06). 즉 사후 감사(audit) 모델.
- `review`에는 **사람의 주관적 판정이 필요한 것만** 남긴다: 디자인 취향, 방향/방식
  결정, "이게 당신이 원한 것 맞나" 같은 불확실성. 사람을 승인 기계로 만들지 않는다.
- 애매하면: 검증 증거가 있으면 done, 없으면(또는 방향이 갈리면) review.

## 상태

| status | 의미 |
|---|---|
| draft | 작성 중, 아직 처리 대상 아님 |
| open | 접수됨, 착수 대기 (request 생성 시 기본값) |
| in-progress | 작업 중 |
| blocked | 진행 불가로 대기 — 외부 요인 **또는 다른 요청 완료에 종속(의존성 대기)**. 사유를 note로 남길 것 |
| review | 작업 완료, **사람(사용자)의 확인·판정 대기**. 사람이 봐야 할 것만 여기에 둔다 |
| done | 완료 (terminal) |
| cancelled | 취소 (terminal) |
| published | knowledge/session 전용 고정 상태 |

## 전이 다이어그램

```
draft ──▶ open ──▶ in-progress ──▶ review ──▶ done
  │        │  ▲       │   ▲          │
  │        │  │       ▼   │          └──▶ in-progress (재작업)
  │        │  └── blocked ┘
  │        │          │
  ▼        ▼          ▼
cancelled ◀───────────┘        (draft/open/in-progress/blocked → cancelled)
```

허용 전이표 (CLI가 강제):

| from \ to | open | in-progress | blocked | review | done | cancelled |
|---|---|---|---|---|---|---|
| draft | ✓ | | | | | ✓ |
| open | | ✓ | ✓ | | | ✓ |
| in-progress | | | ✓ | ✓ | ✓ | ✓ |
| blocked | ✓ | ✓ | | | | ✓ |
| review | | ✓ | | | ✓ | |
| done / cancelled | terminal — 전이 불가 |

## 규칙

- 전이는 `s9 status <id> <new>` 로만 수행 (직접 frontmatter 수정 금지).
  잘못된 전이는 CLI가 거부하며, 예외 상황은 `--force` 로만 우회 가능.
- 모든 전이는 History에 append: `- {시각} status: {old} -> {new} (by {user}) — {note}`
  → 상태 변경의 전체 audit trail이 문서 안에 남는다.
- 인수인계 관례: 이어받는 세션은 전이 없이도 `s9 status <id> in-progress --force`가
  아니라, note를 남기고 싶으면 동일 상태로의 전이 대신 Notes 섹션에 기록한다.
  (동일 상태 재기록은 지원하지 않음 — History 오염 방지.)
