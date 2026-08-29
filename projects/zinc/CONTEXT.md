# Zinc — 프로젝트 컨텍스트

> LLM·참여자의 단일 진입점 (DOC-20260824-001). 배경·용어·핵심 링크를 여기에 유지하라.
> 규약은 이 파일과 assets/ 둘뿐 — 그 외 하위 구조는 자유. 10MB+ 파일은 링크로 대체.

## 배경

Zinc owns cloud operations and infrastructure controls: Bismuth host/system health, Domain
Connector, IAM, deployments, capacity, and production reachability. It must fail closed when a
producer or private dependency cannot be measured.

## 용어

- Repository: `/home/jade/repo/bda-zinc`
- Bismuth boundary: Zinc reports the machine/system; Argon reports data-handling behavior.

## 핵심 링크

- 프로젝트 문서(메타·멤버·이력): vault/projects/zinc.md
- 에셋(외부 파일): projects/zinc/assets/
