# Codex CLI 어댑터 (프로토콜 모드)
- s9-install이 ~/.codex 존재 시 ~/.codex/AGENTS.md 에 common/PROTOCOL.md 를
  managed block으로 주입한다.
- Codex의 notify 설정 등 이벤트 지점이 확인되면 세션 로그 자동화로 확장.

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
