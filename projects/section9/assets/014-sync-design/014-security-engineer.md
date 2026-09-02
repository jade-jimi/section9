# 014 · observer(read-only) 계정과 인가 강제 — security-engineer

범위: REQ-20260902-014-62x6 설계 조사. bin/s9·bin/s9-audit-prompt·bin/s9-install·bin/s9-guard·docs·.gitignore·git ls-files 를 직접 읽어 확인한 것만 사실로 적는다. 코드 수정 없음.

## 결론 먼저

1. **지금 `viewer` 는 이름뿐이다.** 시스템 role `viewer` 를 판정에 쓰는 코드가 한 줄도 없다 — 문서 생성·전이·노트·역할 변경·채팅 전부 member 와 같다. 막는 것은 오직 "등록 프로젝트에 `--project` 를 명시한 생성" 하나(프로젝트 멤버 역할 기준).
2. **observer = 시스템 role `viewer` 에 이빨을 붙인 것**이면 된다. 새 역할 이름을 늘리지 말고, 읽기 범위는 프로젝트 멤버십(project role viewer)으로, 전체 관찰은 admin 이 주는 명시 플래그로.
3. **강제 자리는 `write_doc`(bin/s9:421) 하나**다. 이미 "문서 쓰기의 단일 경계"(원자 교체)로 36개 호출부가 지나간다 — 그 자리에 경로 등급별 정책을 세우고, 클래스 시험이 우회를 막는다. 프로세스 조작(chat/stop/restart/wake)은 문서 쓰기가 아니라 별도 판정 한 곳.
4. **로컬 인가는 인증이 없다**(자기신고 S9_USER). 진짜 게이트는 인스턴스 리포의 GitHub 권한이고, s9 역할은 그것과 **대조·파생**되어야 한다. observer 에게는 리포 read 권한만 준다 — 그러면 파일 직접 편집 + push 도 서버가 막는다.

## ① 현황 진단 (파일:행)

**역할 저장·판정**
- `ROLES = ["admin","member","viewer"]` bin/s9:13147. `user_role()` 13154 — profile.md `role:`; 미등록은 `""`.
- `PROJECT_ROLES` :63, `PROJECT_ROLE_LEVEL/ACTION_MIN_LEVEL` :13919-13920, `project_can()` :13923 — read 는 무조건 True, 미등록 프로젝트 True, admin 우회. 독스트링이 스스로 "보안 경계가 아니라 가드레일" 이라 명시.
- `project_can` 호출부는 8곳뿐: `s9 new --project`(1459), 자동매핑(1465), 프로젝트 member/set 의 manage/own(14109·14122·14164·14173·14295·14308). **문서 전이·노트·우선순위·링크에는 없다.**

**CLI 쓰기 경로 — viewer 가 막는 것: 없음**
- `s9 new`: `--project` 명시 + 등록 프로젝트일 때만 contribute 검사(1459). 없으면 자동매핑만 하고 **생성은 된다**(1462-1466, project 빈값).
- `do_transition()` 1716: `user` 는 기록만(1739 resolve, 1806 History). 소유자·프로젝트·역할 검사 없음. `cmd_status` 8632 동일.
- `cmd_note` 12145: resolve_user 만. 검사 없음.
- **`s9 user role <me> admin` 을 누구나 실행 가능** — 13574-13590 에 admin 검사가 없다(대시보드 쪽 18422-18441 에는 있다). 자기 승격 경로.

**대시보드(serve)**
- GET: `viewer_of()` 17394 → `whoami_info()` 304 (서버 기동 OS 계정 파생, 127.0.0.1 전제 — 독스트링 "외부 노출 시엔 실인증이 필요"). `--host` 옵션 존재(20276). 열람은 `doc_visible()` 14031: admin 전부 / **미등록 뷰어 전부(비강제)** / 프로젝트 문서는 활성 멤버 / 나머지는 작성자 본인.
- POST 18322-: actor=whoami, `is_admin` 계산(18347). admin 검사가 있는 곳: user/add 의 role, user/update 의 role, user/config 본인, secret, project member(내부 project_can). **없는 곳**: `/api/status`(18349 — 아무 문서나 전이), `/api/priority`, `/api/note`, `/api/chat`(18549 — 아무 세션 수신함에 append), `/api/wake`, `/api/stop`(18629 — 전체 워커 정지 포함), `/api/session/restart`(18658).

**훅**
- `s9-audit-prompt`:715 — request 로 분류된 프롬프트를 `s9 new request --tag auto-audit` 로 **자동 생성**(실패 시 조용히 return, 716). :661 QST 자동 생성. :728 `s9 reopened` 결과, :759 승인 메모, :764 `s9 blocked` 를 **모든 프롬프트에 최우선 주입**. `reopened_requests()` 10444 는 **user·machine 필터 없음** — 남의 반려가 내 리드에게 "즉시 재작업하라" 로 주입된다. `next_pickup()` 11002 는 user 필터는 있으나(11019-11021) machine 필터 없음.
- `_spawn_worker()` 7171 — 스폰 유일 경로. 머신 가드 7247 은 `meta.machine`(문서를 **만든** 머신) 기준, `auto_resume` 은 `meta.user` 기준(7229). 담당자 개념 없음.

**공유되는 실행 가능 콘텐츠**
- `SYNC_DATA_PATHS = vault, users, projects, state/sessions` 8391. `projects/<slug>/agents/*.md` → `.claude/agents/` 미러(`sync_project_agents` 13812, SessionStart), `_project_agent_preamble` 13861 은 워커 프롬프트 서두에 1500자 주입. `users/<u>/skills|agents` → `~/.claude/` symlink(s9-install:311-316, 현재 사용자 분만). 즉 **남이 push 한 md 가 내 세션의 에이전트 정의·워커 지침이 된다.**

**커밋되는 계정·경로 정보**
- 추적: `users/*/profile.md`(emails·github·os_accounts·machine_accounts), `users/*/config/settings.json`, `users/nicehugepark/config/harness/claude.json`(model/theme — 토큰 없음), `state/sessions/*.json` 142개 — **`transcript_path`·`agent_transcript_path`·`cwd` 절대 경로**(홈 디렉토리·OS 계정명·/tmp 경로) 포함.
- 비추적(.gitignore): `users/*/secrets/`, `users/*/config/local.json`(external_secrets_path), `streams/`, `state/*`(sessions 제외 — 수신함 `state/terminal/inbox-*.jsonl` 은 로컬 전용). 추적 파일에서 토큰 패턴 검색 결과 없음.
- 커밋 게이트: `s9-guard`(pre-commit) 는 bin/web/harness/.github/.gitignore 만 보호, S9_USER 자기신고. GitHub 최종 게이트(docs/09)도 harness 경로 CODEOWNERS 뿐 — **`users/*/profile.md` 의 `role:` 은 보호 밖의 데이터 파일**이다. `sync_run` 8506 은 로컬 git identity 로 커밋(s9 user 와 무관).

## ② observer 는 viewer 와 같은가 — 선택지

| 물음 | 선택지 | 판정 |
|---|---|---|
| 새 역할 이름? | (a) `observer` 추가 (b) `viewer` 에 강제 부여 | **(b)**. 역할 넷이면 "viewer 와 observer 의 차이" 를 매번 설명해야 하고 판정 표가 두 벌이 된다. 화면 낱말은 ux-writer 몫. |
| 읽기 범위 | (a) 전부 (b) 프로젝트 멤버십 (c) admin 이 주는 `observe: all` | **(b) 기본 + (c) 예외**. 지금 `doc_visible` 이 이미 "프로젝트 활성 멤버" 로 가른다 — project role viewer 가 곧 관찰 티켓. 전체 관찰은 감사·경영진 용도라 admin 명시 부여 + `until` 만료를 붙인다(기본 거부·예외에 만료). |
| 지식 검색만? | 요청·이력도 읽나 | **읽기는 전부 같은 등급**. "검색만" 은 화면 갈래일 뿐 서버 판정을 나누면 `/api/search` 가 `/api/doc` 을 우회하는 종류의 구멍이 생긴다(asset-text 사례와 같은 뿌리, 18183 주석). |
| 차단 범위 | 생성·수정·전이·채팅 | **전부 + 프로세스 조작(wake/stop/restart) + 역할·멤버·설정 변경**. 채팅은 남의 세션에 사용자 메시지를 넣는 행위(CLAUDE.md 15)라 쓰기보다 위험하다. |
| 훅 자동 기록 | 세션 프롬프트 → REQ/QST/SES | **막는다**. 게이트가 vault 쓰기를 거부하면 훅은 이미 조용히 물러난다(715-716). 다만 "정정 경로" 주입 문구(642·702)는 viewer 에게 내지 않아야 한다 — 관찰자에게 `s9 new request` 를 시키는 안내는 소음이자 유도다. |

## ③ 강제 자리 — 한 곳

**`write_doc(path, meta, body)` bin/s9:421 에 인가를 얹는다.** 근거: 이미 원자성의 단일 경계이고 36개 호출부(CLI new/status/note/set/link/tag/priority, 대시보드 do_*, 훅 SES/QST, 프로필 갱신)가 전부 지난다. 경로 등급별 정책:

| 경로 | 정책 |
|---|---|
| `vault/**` | `user_role(actor) == "viewer"` → 거부. 등록 프로젝트 문서면 `project_can(contribute)` 추가. |
| `users/<x>/profile.md` | `role:` 이 바뀌면 actor admin 필수(CLI 자기 승격 봉쇄). 그 외 필드는 본인·admin. |
| `vault/projects/<slug>.md` | 기존 manage/own 판정 유지(그 함수들이 이미 write_doc 앞에 있다). |
| `state/sessions/**` | 통과(런타임 상태, 문서 아님). |

actor 는 `resolve_user()` — 새 신원을 만들지 않는다. 훅 경로의 SES 문서는 viewer 에게도 "무기록" 이 맞으므로 예외를 두지 않는다. 우회 방지: `tests/test_code_read_gate.py` 와 같은 **클래스 시험** — `ROLES` 의 viewer × 모든 쓰기 서브커맨드 × 대시보드 POST 라우트를 전수 순회해 거부를 확인. 라우트가 늘면 시험이 먼저 깨진다.

**문서 쓰기가 아닌 조작**(`/api/chat`·`/api/wake`·`/api/stop`·`/api/session/restart`·`/api/session/wake`)은 write_doc 를 지나지 않는다. 이것은 두 번째 판정 자리 하나로 모은다 — POST 진입부 18347 의 `is_admin` 옆에 `can_operate = user_role(actor) != "viewer"` 를 두고 위 다섯 라우트가 공통으로 본다. 세션 소유자 검사(남의 세션에 chat/restart)는 다중 사용자 서버가 생길 때의 일이고 지금은 127.0.0.1 전제 — 열린 문제 ⑤ 로 넘긴다.

**층별 실패 가정**
- 1층 write_doc 게이트가 뚫리면(파일 직접 편집·S9_USER 위장): 2층 git 이 막아야 한다 → observer 는 인스턴스 리포에 **read 권한만**. push 자체가 거부된다.
- 2층이 잘못 설정되면(observer 에게 write 권한): 3층 `s9 doctor`/serve 기동 시 GitHub collaborator permission 과 profile role 을 대조해 **불일치 경고**(gh api `repos/{o}/{r}/collaborators/{u}/permission`). 경고를 무시하면 남는 것은 감사 흔적(History by, 커밋 author)뿐이다 — 이 한계를 결정권자에게 명시한다.

## ④ 다중 사용자 공유 환경 위협 → 통제 (1:1)

| # | 위협 | 지금 상태 | 통제 |
|---|---|---|---|
| T1 | **공유 문서 = 프롬프트 인젝션 매개체.** 남이 쓴 review note(≤500자, 18350)·반려 사유·note 가 내 리드 프롬프트(훅 728)와 워커 프롬프트에 지시로 주입된다. `projects/*/agents/*.md`·`users/*/skills` 는 아예 에이전트 정의로 로드된다. | 필터·출처 표식 없음 | (i) 실행 가능 콘텐츠(`projects/*/agents`, `users/*/skills|agents`, `harness/`)는 CODEOWNERS 로 admin 승인 필수. (ii) 주입 시 출처 봉투 `<<by user@machine · 문서 데이터>>` 로 감싸고 규약에 "이 안의 지시는 데이터" 명시. (iii) 훅 주입(reopened/blocked/승인)은 **내 담당·내 머신** 것만 — 2축(assignee)과 같은 판정 함수를 써야 한다(옆문 금지). |
| T2 | 바인딩 공유(`state/sessions` 추적)로 홈 경로·OS 계정·/tmp 경로·pid 노출 | 142개 파일에 절대 경로 | 커밋되는 바인딩에서 `transcript_path`·`agent_transcript_path`·`cwd`·`attach_pid` 를 로컬 사이드카(`state/sessions/local/`)로 분리. 다른 머신이 필요한 것은 user·active_reqs·claim_at·ended 뿐이다(docs/08 의 목적). |
| T3 | 수신함 공유 | `state/terminal` 은 gitignore — **노출 없음** | 유지. 단 `.gitignore` 한 줄이 유일한 방어이므로 SYNC_DATA_PATHS 에도 넣지 않는 현 구조(두 겹)를 시험으로 고정. |
| T4 | 계정 프로필·토큰 커밋 | secrets/·local.json·streams 는 ignore, 토큰 패턴 검색 없음. profile 의 emails·os_accounts 는 추적 | 이메일은 설계상 공유 데이터(인증 없는 신원 매칭에 쓴다) — 인스턴스 리포가 private 인 것이 전제. pre-commit 에 토큰 패턴 거부(ghp_·github_pat_·sk-ant-) 한 줄 추가. |
| T5 | **리포 접근권한 ≠ s9 역할.** `users/*/profile.md` 의 `role:` 은 보호 밖 파일 — push 권한이 있으면 누구나 자신을 admin 으로 커밋 가능. CLI `s9 user role` 도 무검사 | 불일치 탐지 없음 | R2(CLI admin 검사) + CODEOWNERS 에 `users/*/profile.md` + R6(권한 대조). 역할 진실은 GitHub 권한이고 profile 은 캐시라는 원칙을 docs/09 에 명시. |
| T6 | 미등록 뷰어 = 전부 열람(`doc_visible` 14042) | 부트스트랩 편의 | 다중 사용자 인스턴스(`.s9-sync` remote)에서는 미등록 → **거부**로 뒤집는다. 편의는 단일 사용자 로컬에만. |
| T7 | 남의 in-progress 가 내 머신에서 실행(중복·월권) | 스폰은 `meta.machine`, 훅 주입은 무필터 | 1축 설계자 몫이나 보안 관점 요구: 판정은 **담당자(assignee)+머신** 한 함수, `_spawn_worker`·`next_pickup`·`reopened_requests`·훅 주입이 같은 함수를 호출. |

## ⑤ 파생 REQ 후보

| 제목 | goal | 크기 | 선후 |
|---|---|---|---|
| viewer 쓰기 게이트 | viewer 역할로 vault 문서 생성·전이·노트가 CLI·대시보드·훅 전 경로에서 거부되고 클래스 시험이 전수 확인 | M | 선행 없음 |
| 역할 변경 admin 전용 | `s9 user role` 이 admin 아닌 actor 를 거부 | S | 없음 |
| 관찰 범위 부여 | admin 이 `observe: all\|projects` + until 을 주면 doc_visible 이 그대로 따른다 | S | 게이트 뒤 |
| 관찰자 훅 무기록 | viewer 세션에서 REQ/QST/SES 가 생기지 않고 정정 유도 문구도 나오지 않는다 | S | 게이트 뒤 |
| 조작 라우트 역할 판정 | chat/wake/stop/restart 가 viewer 를 거부 | S | 게이트와 병행 |
| 리포 권한 대조 | doctor/serve 가 GitHub 권한과 profile role 불일치를 경고 | M | 없음 |
| 실행 콘텐츠 승인 게이트 | projects/*/agents·users/*/skills·profile role 이 CODEOWNERS 보호 | S | 없음 |
| 바인딩 로컬 필드 분리 | 커밋되는 바인딩에 절대 경로·pid 가 없다 | S | 3축 설계와 조율 |
| 주입 출처 봉투 | 남의 note·반려 사유가 프롬프트에 들어갈 때 출처와 데이터 표식이 붙는다 | M | T7 판정 함수 뒤 |

## ⑥ 다른 역할에게

- architect/backend(1·2축): assignee 필드가 생기면 `_spawn_worker` 7247·`next_pickup`·`reopened_requests`·훅 주입이 **같은 판정 함수** 를 쓰는지 — 게이트가 두 벌이면 성긴 쪽으로 샌다(7208 주석의 교훈).
- 3축(동기화): `users/*/profile.md` 가 공유 데이터로 실시간 push 되는 구조에서 역할 변경 커밋은 admin 만 통과시킬 방법(CODEOWNERS 는 PR 전제 — 이벤트 커밋 직push 와 충돌). 브랜치 보호와 자동 push 의 양립이 3축의 결정 사항.
- ux-writer/tech-writer: 화면 낱말 — `viewer` 그대로 둘지 「관찰자」로 옮길지. 내부 role 값은 viewer 유지 권고.
- 미확인: 대시보드가 `--host 0.0.0.0` 으로 뜬 인스턴스가 실제 있는가(있으면 whoami 파생이 무너져 실인증이 선행). `docs_bulk` 13048 만 CLI 에서 doc_visible 을 쓰는 이유.
