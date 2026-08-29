# Chief of Staff — 프로젝트 컨텍스트

> LLM·참여자의 단일 진입점 (DOC-20260824-001). 배경·용어·핵심 링크를 여기에 유지하라.
> 규약은 이 파일과 assets/ 둘뿐 — 그 외 하위 구조는 자유. 10MB+ 파일은 링크로 대체.

## 배경

Chief is Jade's cross-project operating system for Element Energy work. Section9 is now the chosen
primary browser shell; Chief's existing file/Jira/Bitbucket/release/session services remain the
authoritative execution backend. The integration must reduce weekend-return cognitive load without
copying mutable work state into a second ledger.

## 용어

- Chief source: `/home/jade/chief` and its loopback mobile API on `127.0.0.1:14098`.
- Section9 shell: this repository's `web/index.html` and stdlib server.
- Attached work: live Chief project/work/release/report/session projections, not copied Section9
  request documents.
- Human gate: Jade's dev-to-production approval; agent actions may verify/repair/merge only to dev.
- Main frontend: dashboard route `/app/chief-mobile/` after parity cutover.

## 핵심 링크

- 프로젝트 문서(메타·멤버·이력): vault/projects/chief.md
- 에셋(외부 파일): projects/chief/assets/
- Integration request: `REQ-20260829-001-wfow`
- Chief backend: `/home/jade/chief/mobile/server.py`
- Previous frontend/rollback: `/home/jade/chief/mobile/`
- Section9 clone: `/home/jade/repo/section9`
