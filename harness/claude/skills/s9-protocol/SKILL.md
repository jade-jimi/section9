---
name: s9-protocol
description: section9 외부기억 작업 규약. 어떤 역할이든 작업 기록/조회/상태 관리 전에 로드. 트리거: s9, 요청 문서, 작업 기록, 외부기억.
---

# section9 작업 규약 (모든 역할 공통)

전체 규약 원문: `~/section9/harness/common/PROTOCOL.md` 를 Read하라. 핵심 요약:

- 외부기억 = `~/section9`, CLI = `~/section9/bin/s9`. 컨텍스트가 아니라 문서만 영속한다.
- 상황 파악: `s9 digest` → `s9 ls --status/--user` → `s9 show <id> [--meta]` → `s9 search <kw> --body`. 넓은 것부터 좁혀 토큰을 아껴라.
- 작업 기록: 진행/결정은 `s9 note <REQ-id> "..." --label <역할명>`, 상태는 `s9 status <id> <to> --note`, 재사용 지식은 `s9 new knowledge`.
- 파생 작업 발견 시 `s9 new request --parent <REQ>` 로 분리 등록.
- 세션 식별자가 주어졌으면 모든 s9 호출에 `S9_SESSION=<8자>` 를 붙여라.
