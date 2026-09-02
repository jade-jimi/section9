# 014 · 생성자/담당자 데이터모델과 CLI·카탈로그 변경안 (backend-developer)

## ① 현황 진단 (bin/s9 · harness 코드로 확인한 사실)

**요청의 "누구" 는 `user` 하나다.** `cmd_new` 가 `resolve_user(args.user)` 결과를 `user` 에, 머신·세션 스탬프를 `machine`/`session` 에 적는다 (bin/s9:1446-1448, 1494). 사람이 쳤는지 에이전트가 만들었는지 구분하는 필드는 없고, `--parent` 는 계보일 뿐 "누구를 처리하다 만들었나" 가 아니다 — `parent` 는 나중에 `s9 link --parent` 로도 바뀐다 (bin/s9:8671).

**`user` 를 읽는 쪽은 전부 "담당자" 의미로 쓴다** — 이것이 설계의 축이다.
- `next_pickup` 은 `r["user"] == 나` 로 집을 것을 고른다 (bin/s9:11021).
- `_spawn_worker` 는 `owner = meta["user"]` 의 `auto_resume` 설정을 보고, 워커에 `S9_USER=owner` 를 준다 (bin/s9:7233, 7396).
- `doc_visible` 은 프로젝트 없는 문서를 `row["user"] == me` 로 연다 (bin/s9:14031-14054).
- `apply_filters --user`, `by-user` 인덱스 (bin/s9:1357, 1308).
즉 `user` 는 이미 "이 일이 누구 몫인가" 다. 생성자는 History 첫 줄 `created by {user}` (bin/s9:1517) 에만 남는다.

**실행 귀속 게이트는 담당자가 아니라 생성 머신 기준이다.** `_spawn_worker` 의 `meta.get("machine") != current_machine()` (bin/s9:7247). 워처 후보 선별 `rework_watch_tick` (bin/s9:8111-8172) 과 훅이 주입하는 반려 목록 `reopened_requests` (bin/s9:10444-10467) 에는 user·machine 필터가 **없다** — 남의 반려 REQ 가 pull 돼 오면 내 리드 세션의 프롬프트에 "우선 이어서 작업하라" 로 주입된다 (bin/s9-audit-prompt:725-729). 워커 스폰만 7247 에서 막히고, 리드 주입 경로는 열려 있다.

**입구별 자동 기입 현황** (무엇이 `user`·`session` 을 채우나):
| 입구 | 코드 | user 출처 | 구분 단서 |
|---|---|---|---|
| 훅 auto-audit (사람 프롬프트) | bin/s9-audit-prompt:566, 715-716 | `S9_SESSION` 바인딩 → resolve_user | `--tag auto-audit` 뿐 |
| 대시보드 채팅 | bin/s9:18549 → `chat_audit` 6829-6830 | `--user sender`(서버 whoami, 대리 시 proxy, 18338-18346) | `--tag auto-audit` |
| 에이전트 `s9 new request --parent` | 훅 지시문 bin/s9-audit-prompt:761, 805 | 리드 세션 바인딩 user | 없음 — 사람 입력과 동일 |
| 무인 워커 후속 | `_spawn_worker` env: `S9_USER=owner`, `S9_JOB_REQ=<REQ>`, `S9_SESSION` 제거 (bin/s9:7396-7401) | owner(=담당자) | `S9_AUTO_RESUME=1` (7395) 는 cmd_new 가 안 읽음 |
| `trigger_dependents` | bin/s9:8323-8348 | REQ 를 만들지 않는다 — 전이만(`auto=True`, History `[auto]`) | — |
| 승인 후속 | bin/s9:8172-8195 | 무인 스폰 없음, 리드 턴에 주입 → 리드가 `new --parent` | 위 에이전트 행과 같음 |

**저장 형식 제약**: 프론트매터는 flat 권장(docs/01) 이나 `fm_dump`/`fm_parse` 는 dict 도 JSON 으로 왕복한다 (bin/s9:371-420, `relates_why`·`contributions` 선례). 카탈로그 행은 `catalog_row` 한 곳 (bin/s9:1162-1206). 신원은 자가신고 가드레일이지 인증이 아니다 (`project_can` 주석 bin/s9:13923-13934).

## ② 선택지

**A. 중첩 객체 `created_by: {user, kind, agent, on_behalf_of, from_req}`** — 한 덩어리라 읽기 쉽다. 단점: docs/01 flat 원칙 위반, jq 질의·by-* 인덱스·`apply_filters` 가 전부 중첩 접근으로 바뀐다, `on_behalf_of` 가 `user` 와 중복된다.

**B. 평면 필드 + `user` 를 담당자로 재정의(권고)** — `creator`·`origin`·`origin_actor`·`origin_req` 넷을 추가하고 `user` 는 그대로 두되 뜻을 "현재 담당자" 로 못 박는다. 기존 소비자(11021, 7233, 14054, 1357)가 코드 변경 없이 담당자 의미로 정확해진다. 단점: 이름이 뜻을 말하지 않으니 문서와 `--assignee` 별칭으로 보완해야 한다.

**C. `assignee` 를 새로 두고 `user` 는 생성자로 유지** — 이름은 직관적이나 `user` 를 읽는 네 자리를 전부 `assignee or user` 로 고쳐야 하고, 한 곳이라도 빠지면 "남의 일을 내 워커가 집는다" 는 핵심 결함이 그 자리에 남는다.

`assignee_history` 리스트는 두지 않는다 — History 섹션이 append-only 이벤트 로그이고(전이도 여기) 프론트매터에 이력을 복제하면 진실이 둘이 된다.

## ③ 권고안 (B)

### 필드 (request 타입, 생성 시 확정·불변인 것은 ★)
| key | 값 | 원천 |
|---|---|---|
| `user` | 현재 **담당자** 계정 (변경 가능) | 생성 시 `--assignee` 또는 creator |
| `creator` ★ | 생성 주체로 기록되는 **사람 계정** | `resolve_user()` — 워커는 `S9_USER=owner` 라 담당자 이름으로 만든다 |
| `origin` ★ | `human` · `agent` · `derived` | 아래 자동 판정 |
| `origin_actor` ★ | actor 규격 한 줄 (`lead:<model>`·`worker:rework`·`sub:designer:…`), human 이면 빈 값 | `--agent`(note 와 같은 `normalize_actor` 11326) · 워커는 `worker:<reason>` |
| `origin_req` ★ | 에이전트가 **어느 REQ 를 처리하다** 만들었나. `derived` 일 때 필수 | `--parent`/`--derived-from`/`--origin-req` > `S9_JOB_REQ` |

"누구의 요청을 처리하다" 의 **누구** 는 `origin_req` 문서의 `user` 로 답한다 — `on_behalf_of` 를 따로 두면 그 문서가 재할당될 때 낡는다. `creator` 는 항상 사람 계정이라 "에이전트가 스스로" 일 때도 그 세션의 사람에게 귀속된다(책임 소재).

`parent`/`derived_from` 과의 관계: 둘은 **계보**(후에 바뀔 수 있음, 8671), `origin_req` 는 **생성 행위의 출처**(불변). 보통 같지만 같아야 할 의무는 없다 — 예: 파생 REQ 를 만든 뒤 사람이 parent 를 다른 REQ 로 옮겨도 "무엇을 하다 나왔는지" 는 남는다. `agents`/`contributions` 는 생성 후 **처리** 이력이므로 손대지 않는다.

### origin 자동 판정 (cmd_new 한 곳, 입구는 플래그만 넘긴다)
1. `--origin human` 명시 → human. **훅(bin/s9-audit-prompt:715)·chat_audit(6829)·대시보드 새 요청 폼**이 이 플래그를 붙인다. 사람 입구는 이 셋뿐이다.
2. 아니면 `origin_req` 후보(--parent/--derived-from/--origin-req/`S9_JOB_REQ`)가 있으면 derived.
3. 아니면 `S9_SESSION` 또는 `S9_AUTO_RESUME` 이 있으면 agent(에이전트 세션 안), 둘 다 없고 stdin 이 tty 면 human(사람이 셸에서 직접).
4. `origin_actor` 는 `--agent` > (`S9_AUTO_RESUME` 이면 `worker:auto-resume`) > (`S9_SESSION` 이면 `lead`) — 정밀도는 호출자 보고에 의존한다(contributions 와 같은 한계, docs/01).

### CLI
- `s9 new request … [--origin human|agent] [--agent <actor>] [--origin-req <REQ>] [--assignee <user>]`.
- `s9 set <id> --assignee <user> [--why '...']` — **단일 쓰기 경로 `do_assign()`** 을 `cmd_set` 과 대시보드 `/api/set` 이 함께 부른다. 규칙: ① `users/<name>/` 등록 필수, role viewer 거부, 프로젝트 등록 시 `project_can(slug, new, "contribute")` 필수 ② History `- {ts} assignee: {old} -> {new} (by {actor}) — {why}` append, `updated` 갱신 ③ 종결 상태 거부 ④ in-progress 이고 다른 세션이 클레임 중이면(`rework_claimed` 3517) 거부 — 먼저 `s9 claim --release`; 허용되면 `update_active_reqs` 로 옛 클레임을 걷는다(1554-1600) ⑤ 자기 자신에게로는 no-op.
- 조회: `s9 ls --assignee`(=`--user` 별칭)·`--creator`·`--origin`; `s9 next` 는 `user` 기준 그대로(담당자).

### catalog.jsonl · 인덱스 · 문서
`catalog_row` 에 `creator`·`origin`·`origin_actor`·`origin_req` 추가(1162), docs/02 필드 목록 갱신, docs/01 에 `user`=담당자 명시. by-* 차원은 추가하지 않는다(카탈로그 필터로 충분).

### 역호환 (읽기 규칙 한 곳: `doc_creator(meta)`, `doc_origin(meta)`)
필드가 없으면 `creator = user`(생성자=담당자), `origin = ""`(미상 — 지어내지 않는다; 화면은 "기록 없음"). 소급 backfill 은 하지 않는다: 700+ 문서 재기록은 sync 커밋 폭주와 rebase 충돌 면적만 늘린다. 태그 `auto-audit`+parent 없음 → human 추정은 **표시 층에서만**.

### 실행 귀속에 미치는 효과
`_spawn_worker` 7247 의 머신 비교를 `meta["user"] == whoami["user"]` 담당자 비교로 바꾸고, `reopened_requests`(10444)·`next_pickup`(11002) 도 같은 판정 함수(`is_mine(meta)`) 하나를 쓴다. `machine` 은 생성 스탬프로 남긴다. 사용자가 여러 머신(`profile.machines`, 13321)에서 서버를 띄우면 담당자 비교만으로는 두 머신이 같이 뜬다 — 이 부분은 ⑤.

### TDD 씨앗 (파생 REQ 의 tdd 노트로)
S1 훅 경로 `--origin human` → origin=human, creator=user=바인딩 user, origin_actor 빈 값 / S2 `S9_SESSION` 세션에서 `new --parent X` → derived, origin_req=X, origin_actor=lead / S3 워커 env(`S9_AUTO_RESUME=1`, `S9_JOB_REQ=X`, `S9_USER=o`) → derived, creator=user=o, actor `worker:auto-resume` / S4 `S9_SESSION` 만 있고 parent 없음 → agent / S5 필드 없는 옛 문서 → `doc_creator==user`, origin "" / S6 `set --assignee` 미등록·viewer·종결·타세션 클레임 중 → 각각 거부, 문서 불변 / S7 성공 시 History 한 줄·카탈로그 `user` 갱신·옛 active_reqs 제거 / S8 `_spawn_worker` 가 담당자≠whoami 면 `elsewhere`, 담당자 일치면 machine 달라도 통과 / S9 `fm_dump→fm_parse` 왕복에 넷이 보존. 모두 `S9_ROOT` 격리, 모듈 로드로 함수 직접 호출.

## ④ 파생 REQ 후보
1. **요청 기원 필드 도입** (M) — goal: 새 REQ 마다 creator/origin/origin_actor/origin_req 가 채워지고 옛 문서는 읽기 규칙으로 같은 답을 낸다. 선행 없음.
2. **입구별 기원 자동 기입** (S) — goal: 훅·채팅·워커 세 입구가 플래그/env 로 origin 을 넘겨 사람 입구=human, 워커=derived 가 실측된다. 1 뒤.
3. **담당자 변경 명령** (M) — goal: `s9 set --assignee` 와 화면이 같은 `do_assign` 을 지나고 S6·S7 이 통과한다. 1 뒤.
4. **실행 귀속 담당자 기준** (M) — goal: 담당자가 아닌 REQ 는 워커 스폰·`next`·반려 주입 어디에도 오르지 않는다. 3 뒤, architect 의 동기화 설계와 합의 필요.
5. **관찰자 쓰기 차단** (S) — goal: role=viewer 계정은 new/status/note/set/link 가 CLI·서버 양쪽에서 거부된다. 독립.

## ⑤ 열린 문제 (다른 역할에게)
- architect/devops: 재할당은 프론트매터 한 줄+History 한 줄 편집이라 동시 재할당·전이 시 같은 파일 rebase 충돌이 난다 — 브랜치/디렉토리 안이 이 면적을 줄이는가. 같은 사용자의 머신이 둘일 때 실행 머신 선정 규칙(클레임 시 `exec_machine` 스탬프? 프로필 기본 머신?).
- security-engineer: `--assignee`·`--origin human` 은 자가신고다. 남의 이름으로 만들거나 남에게 할당하는 것을 막을 근거(서버 whoami 강제, `as` 대리는 admin 한정 18305)를 어디까지 세울지. viewer 의 read-only 는 `doc_visible`(14031) 이 아니라 쓰기 명령 입구에 서야 한다.
- designer/ux-writer: 카드에 "만든 사람·맡은 사람·기원" 을 한 줄로 보이는 방식, 재할당 손잡이의 자리.
- 미확인: 채팅 외의 화면 "새 요청" 입구(`/api/new` grep 무결과, web/ 미검토); `S9_JOB_REQ` 를 읽는 곳은 tests/jobfile.py 뿐이라 cmd_new 가 새로 읽어야 한다.
