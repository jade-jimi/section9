# REQ-20260902-014-62x6 「다중 사용자 요청 동기화 설계」 — 공통 브리핑

## 사용자 원문
(같은 디렉토리 original.txt 전문을 먼저 Read 하라. "브레인스토밍 단계의 아이디어일 뿐, 방향 제시가 아니다"라고
사용자가 못 박았다 — 원문의 아이디어를 그대로 따르지 말고 판정하라.)

## 네 축 (사용자가 말한 것)
1. 실행 귀속: 요청 문서가 실시간 공유돼도 **자기 요청은 자기 머신에서만** 실행. 남의 in-progress 가
   pull 돼 왔을 때 내 머신의 워처/세션이 중복 실행하면 안 된다.
2. 생성자 vs 담당자: 요청은 사람이 직접 낸 것, 에이전트(시스템/LLM)가 스스로 낸 것, 에이전트가 **누구의**
   요청을 처리하다 파생한 것 — 셋을 구분해 문서에 사용자 id + 에이전트 정보로 남긴다. 생성자(creator)와
   담당자(assignee)를 분리하고 담당자는 바꿀 수 있어야 한다(남에게 할당).
3. 동기화 방식: 거의 실시간, 안전, 충돌 없음, 지저분하지 않음, 성능 저하 없음. 후보로 사용자가 던진 것:
   main 단일 브랜치 / 프로젝트별 브랜치 / 프로젝트-사용자 브랜치 / vault 하위를 프로젝트별 또는
   프로젝트/사용자별 디렉토리로 나누고 통합 조회. (모두 아이디어, 결정 아님)
4. observer 계정(또는 계정 타입): 생성·수정 불가, read-only 로 전체/프로젝트별 상태·이력·지식 검색만.

## 현재 구조 (사실 — 코드/문서로 확인된 것)
- 문서 = 파일 1개. `vault/requests/YYYY/MM/REQ-YYYYMMDD-NNN-<suffix>.md` (suffix 4자 = 머신 해시,
  bin/s9 ~936행 근처 `hashlib.sha1(machine|home)`). frontmatter: id/type/title/summary/goal/status/size/
  user/machine/session/agents/contributions/project/parent/derived_from/relates/tags/created/updated/priority.
  예시: `vault/requests/2026/09/REQ-20260902-013-62x6.md`. 문서 포맷: docs/01-document-format.md.
- 파생 인덱스 `index/catalog.jsonl` (git 무시, pull 후 post-merge 훅이 rebuild). docs/02-directory-and-index.md.
- 사용자 레지스트리 `users/<name>/profile.md` (role: admin|member|viewer — **viewer 가 이미 있다**, bin/s9 ROLES ~13147행),
  프로젝트 문서 `vault/projects/<slug>.md` 에 members(owner|maintainer|contributor|viewer, until 만료). docs/07-users.md,
  DOC-20260823-005(프로젝트 모델·로드맵 — 인가는 1단계 '기록·조회만', 강제는 차기).
- 세션 바인딩 `state/sessions/<machine>__<sid8>.json` (git track). user/active_reqs/claim_at/worker/entry 등.
  클레임 = 바인딩의 active_reqs (`s9 last <id> --add`, `s9 claim`).
- 워처: serve 가 30초마다 반려/승인/blocked 를 스캔해 무인 워커를 스폰 (`_spawn_worker` bin/s9 ~7171행).
  **이미 `meta.machine != current_machine()` 이면 "다른 컴퓨터의 것" 으로 스폰을 막는다** (~7247행). 그러나 이것은
  문서를 만든 머신 기준이지 담당자 기준이 아니고, 리드 세션의 `s9 next`/훅 주입(반려 재작업 지시)이 같은 가드를
  쓰는지는 확인 대상이다.
- 동기화: `s9 sync` (bin/s9 `sync_run` ~8500행대) — 문서 이벤트마다 commit → pull --rebase --autostash → push.
  인스턴스 리포(.s9-sync 마커)에서만, 기본 off, 모드 local/remote. 데이터 경로만 커밋(SYNC_DATA_PATHS).
  실패는 state/sync.log 에만 남고 작업을 막지 않는다. 네트워크 백오프 60s. docs/08-git-sync.md.
- 업스트림-인스턴스 구조 (DOC-20260824-003): section9 = 프레임워크, 인스턴스 리포 = 데이터. 알려진 한계:
  같은 날 같은 시퀀스 ID 충돌(suffix 로 완화), streams 용량, 세션 키 충돌.
- 대시보드 서버 `bin/s9 serve` (포트 9909) — SSE 폴, `/api/chat/target`, 채팅 수신함 `state/terminal/inbox-<sid>.jsonl`.
  머신마다 서버 하나. 인가는 `viewer_of(qs)` 로 me 를 정해 admin/본인 검사(~17394행).
- 에이전트 귀속: 노트 `--agent lead:<model>|<role>` 이 frontmatter agents/contributions 에 누적. 요청의 "누가 만들었나" 는
  user 필드 하나뿐 — 사람이 쳤는지 에이전트가 `s9 new request --parent` 로 만들었는지 구분 필드가 **없다**.
- 관계 3층: parent(1개)/derived_from/relates(--why 필수). 다중 부모 금지(DOC-20260825-002).
- 규약: CLAUDE.md, harness/common/PROTOCOL.md. 핵심 가치: 본질 파악 → 근원 해결 → 재발 방지 → 지속 개선.

## 너의 산출물
- 파일: 이 디렉토리에 `014-<너의 역할>.md` 로 **Write** 하라 (한국어, 2000자~6000자). 구조:
  ① 현황 진단(코드/문서로 확인한 사실만, 파일:행 인용) ② 선택지와 장단점 ③ 권고안(하나로 고르고 이유)
  ④ 파생 REQ 후보(제목 20자 이내 명사구 + 한 줄 goal, 크기 S/M/L, 선후 의존) ⑤ 다른 역할에게 넘길 질문/열린 문제.
- 최종 보고(대화 반환)는 **800자 이내 요지**만 — 파일이 본문이다.
- 짐작으로 쓰지 마라: bin/s9·docs·vault 를 직접 읽어 확인한 것만 사실로 적고, 확인 못 한 것은 "미확인" 으로 표시.
- 남의 도구 이름(git pull/push/branch/rebase/worktree)은 원어 그대로. 존댓말·아부 금지.
- 코드를 고치지 마라 — 설계 조사다. s9 명령으로 상태 전이도 하지 마라(리드가 한다).
