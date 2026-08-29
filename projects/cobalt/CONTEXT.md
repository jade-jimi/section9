# Cobalt — 프로젝트 컨텍스트

> LLM·참여자의 단일 진입점 (DOC-20260824-001). 배경·용어·핵심 링크를 여기에 유지하라.
> 규약은 이 파일과 assets/ 둘뿐 — 그 외 하위 구조는 자유. 10MB+ 파일은 링크로 대체.

## 배경

Cobalt is the Inertia customer front door: landing experience, digital twin, engineering/customer
visualizations, and the product-facing interpretation of telemetry and battery value.

## 용어

- Repository: `/home/jade/repo/bda-cobalt`
- Release model: feature PRs integrate to dev autonomously after verification; production is Jade's gate.

## 핵심 링크

- 프로젝트 문서(메타·멤버·이력): vault/projects/cobalt.md
- 에셋(외부 파일): projects/cobalt/assets/

## Future product backlog

- `BDA-3050` — multi-tenant Cobalt administration and fail-closed tenant isolation.
- `BDA-3051` — choose the engineering SaaS name, target users/MVP, Cobalt reuse boundary, and
  dedicated project/repository before creating it.
- These items relate, but neither has started. Do not create the new project or repository until
  BDA-3051 records the naming and ownership decision.
