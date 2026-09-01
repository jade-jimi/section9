# Codex CLI 어댑터 (프로토콜 모드)
- s9-install이 ~/.codex 존재 시 ~/.codex/AGENTS.md 에 common/PROTOCOL.md 를
  managed block으로 주입한다.
- Codex의 notify 설정 등 이벤트 지점이 확인되면 세션 로그 자동화로 확장.

## Codex local-chief orchestration

Chief와 모든 프로젝트 Codex session은 먼저 `s9 digest`에서 관련 REQ를 좁히고 project context,
durable docs/work order, project session/work-run 기록과 필요할 때 Jira·PR·release 기록을 읽어
현재 상태와 ownership을 복원한다. 현재 tree는 `list_agents`로, sibling T3 worker는 durable 기록으로
relevant existing sessions를 찾고 `send_message` 또는 해당 session 채널로 owner에게 claim·최신 증거·
남은 일을 묻거나 조향한다. active claim을 handoff 없이 다시 spawn하지 않아 duplicate ownership을
막고, 겹치지 않는 범위만 새로 맡긴다.

size M/L의 independent tracks가 있으면 available 4-slot Codex tree를 fill immediately 한다:
**lead + max 3 bounded children**이며, child도 같은 tree의 남은 슬롯 안에서만 이 local-chief 순서를
적용한다. evidence/QA/review/short implementation은 bounded child에, durable branch/PR work는
durable work order가 연결된 sibling T3 worktree session에 맡긴다. lead keeps integrating: primary
작업·통합 준비·documents/work-order 갱신·검증·후속 분해를 계속하고, 유용한 lead work가 끝난 뒤에만
기다린다.

결과는 authoritative documents에 기록한다. 별도 actionable item은 lead가 REQ/work order로 만들고,
승인과 credential gate가 충족될 때만 lead-created Jira followups를 생성·갱신한다. child는 Jira,
merge/push/deploy, production write, 게시·발송을 하지 않고 초안과 증거만 반환한다. 즉,
external writes remain lead/authorized이고 최종 통합·검증·보고도 lead 소유다.

## Codex reversible-artifact fast lane

Codex는 작업 시작 때 아래 세 종류를 먼저 구분한다.

- `reversible artifact`: PPT, report, draft, preview처럼 다시 만들거나 교체할 수 있는 산출물.
- `durable code/PR`: branch, worktree, PR 또는 독립 수명이 필요한 구현. 별도 T3 worker session과
  work order를 사용한다.
- `irreversible/external action`: merge/push/deploy, production write·traffic·grade/data/resource
  변경, destructive action, 외부 메시지·게시, Jira 변경·close. 기존 승인·검증 gate를 전부 유지한다.

size M/L의 reversible artifact는 evidence/source, diagram/plot/table, QA 트랙처럼 겹치지 않는
작업을 즉시 `spawn_agent`로 fan-out한다. 리드는 기다리지 않고 primary artifact(PPT/report/draft)를 동시에
만든다. 파일이 실제로 열리고 핵심 페이지/슬라이드가 render되며 치명적 깨짐이나 가독성 문제가
없는지 basic open/render validation을 한 뒤 first useful output을 바로 전달한다. 독립 QA 완료나
TDD ceremony는 이 첫 전달의 선행 gate가 아니다.

첫 전달 뒤에는 같은 active workflow에서 HTML/preview, metadata/source notes, artifact registry,
Section9 note/status, commit 같은 reversible bookkeeping을 batch한다. `list_agents`로 결과를 모아
필요한 보강과 최종 검증을 이어간다. common protocol의 credential source, host, configuration
경계는 fast lane에서도 그대로 적용한다. 이 순서는 Codex 전용이며 Claude의 병렬 호출 의미나
gate 순서를 바꾸지 않는다.
