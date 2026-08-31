# Bismuth — 프로젝트 컨텍스트

> LLM·참여자의 단일 진입점 (DOC-20260824-001). 배경·용어·핵심 링크를 여기에 유지하라.
> 규약은 이 파일과 assets/ 둘뿐 — 그 외 하위 구조는 자유. 10MB+ 파일은 링크로 대체.

## 배경

Bismuth is the Louisville offline-failover and grading node. Work includes autonomy, backlog
recovery, false Bin-2 prevention, retained evidence, grade synchronization, and publishing honest
system-health snapshots to cloud consumers.

## 용어

- Execution host: `Louiville`; repository: `/home/jade/bismuth`
- Evidence rule: runtime, database, Parquet, container, and station evidence is gathered on Louisville.
- Bismuth T3 threads are created by Louisville's own `t3code.service` and run directly in
  `/home/jade/bismuth` on that computer. `/home/jade/section9-chief/projects/bismuth` remains only
  the Chief/Section9 coordination record; it is not the execution workspace and must never be
  presented as the opened Bismuth session.

## 핵심 링크

- 프로젝트 문서(메타·멤버·이력): vault/projects/bismuth.md
- 에셋(외부 파일): projects/bismuth/assets/
