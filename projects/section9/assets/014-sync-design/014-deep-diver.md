# 014 deep-diver — 남의 요청이 내 머신에서 실행되는 경로 전수 (현행 코드)

질문: 다른 사용자·다른 머신의 문서(와 바인딩)가 pull 돼 왔을 때, 내 머신의 어떤 경로가 그것을 집는가.
증거 계층: 1차(bin/s9·훅 코드, 격리 재현 실행 출력). 재현 스크립트: 같은 디렉토리 `repro_cross_machine.py`, `repro_reassign.py`
(S9_ROOT=mktemp, S9_MACHINE=alpha/beta, Popen 가짜로 실스폰 차단, 실행 exit=0).

## ① 현황 진단 (사실)

**신원 필드.** 문서 생성 시 `user/machine/session` 을 한 번 찍는다 (bin/s9:1494). `machine` = `$S9_MACHINE` 또는 hostname
(bin/s9:177) — id 접미(`machine_fp`, :936, 머신명+홈 해시 4자)와는 다른 값이다. 이후 전이·클레임은 `session` 만 갈아탄다
(`_merge_session_stamp` :1865, `stamp_doc_session` :1997); **`machine` 은 생성 뒤 어디서도 갱신되지 않는다** → 뜻이
"만든 머신"에 고정. 실측 [b2]: beta 세션이 `s9 claim` 하면 `session=bbbb2222, sessions=[aaaa1111,bbbb2222]`, `machine=alpha` 그대로.

**경로별 판정** ("pull 된 남의 문서를 집는가"):

| 경로 | 위치 | 가드 | 판정 |
|---|---|---|---|
| (a) 무인 스폰 전부 (반려 워처·긴급 즉시·깨우기·항목 재개) | `_spawn_worker` :7171, 가드 :7247 `meta.machine != current_machine()` → `elsewhere`. 호출자 `_spawn_rework`:7511 `_spawn_wake`:7549 `cmd_resume_item`:12521 이 전부 여기를 지남 | 있음(단일 지점) | **안 집는다** [a]: beta 워처 `rework_watch_tick(grace=0)` → `[]`, Popen 0회. 대조 alpha → 스폰 1회 |
| (a′) 반대 방향 — 남이 내 문서를 이어받은 뒤 **내(만든) 머신** 워처 | `rework_claimed` :3517 는 `state/sessions/*.json` 전부를 훑지만 생존을 `chat_live`(:4262 → inbox tail·`pid_alive(attach_pid)`·transcript mtime)로 판정 — 셋 다 **그 머신에서만 참**인 신호 | 없음 | **중복 스폰** [1]: beta 세션이 claim 한 X 를 alpha 워처가 `rework_claimed=False` 로 보고 스폰 (Popen 2회). 가드가 "담당자"가 아니라 "만든 머신" 기준이라 생기는 역방향 구멍 |
| (b) `s9 next` | `next_pickup` :11002 — `r.user == 나` 필터만, machine 없음. `--all` 이면 사용자 필터도 해제 | user 만 | **집는다** [b]: alice@beta 가 alpha 의 X 를 "이어받기: s9 claim X" 로 받음 |
| (b) 훅 주입 reopened/stalled/blocked/approvals/review | `reopened_requests`:10444 `stalled_requests`:10792 외(:11061~11174) 모두 **user·machine 필터 없음**. bin/s9-audit-prompt:726(반려 "이번 턴에서 우선 이어서") :733(stalled) :757(approvals "후속 착수") :764(blocked '패치 적용 대기'면 "이 세션이 지금 적용") | 없음 | **집는다** [b][4]: bob@beta 의 `s9 reopened`·`blocked`·`stalled(40분)` 에 alice@alpha 문서가 실려 매 턴 착수 지시로 주입 |
| (b) SessionStart digest | s9-audit-session:484 → `cmd_digest` :11255 "⚠ 반려/재개 … 최우선으로" 절은 무필터, "active — {user}" 만 user 필터 | 부분 | 반려 절은 **집는다** |
| (c) 수신함 event | `chat_notify_transition` :7086. 드래그 착수: `chat_target(None)` :7096 = **이 머신의 라이브 리드 아무나** 에게 "지금 클레임하고 즉시 착수하라". 반려: 문서 `session` 바인딩 + id 를 잡은 바인딩 중 `chat_live or fresh` | 없음 | 드래그 통지는 **집는다**. 반려 통지는 남의 바인딩이 pid 충돌하면 읽는 이 없는 수신함으로 [c]: `inbox-aaaa1111.jsonl` 이 beta 에 생김 |
| (d) `s9 status` 의 `maybe_auto_resume` | :3254 → `rework_kick` :8075 → (a) 가드 | (a) 상속 | 안 집는다 [2]. 단 `block("elsewhere")` 는 `_auto_log` 를 안 찍어 spawn.log 엔 `PENDING` 만 남음 — **막힌 사실이 보이지 않는다** |
| (e) `trigger_dependents` | :8323 — 카탈로그 전수, `blocked_by` 에 done id 면 `do_transition(in-progress, auto=True)` | 없음 | **집는다** [e]: beta 에서 X done → alpha 의 Y 가 beta 에서 재개(`machine=alpha` 유지). rework 후보는 아니라 워처는 안 뜨지만 (b) 목록엔 오른다 |
| (f) `/api/status`·`/api/wake` | :18349, :18621 — actor 는 whoami/admin 대리뿐, 문서 user·machine 대조 없음 | 없음 | 누구 문서든 전이·깨우기 가능 |

**바인딩 공유의 섞임.** `STATE = state/sessions` (:34) 는 git track(.gitignore `!state/sessions`)이고 `SYNC_DATA_PATHS` 에 든다(:8397).
- `chat_target` :4327 은 모든 바인딩을 돌려 `chat_live` 로 거른다. 남의 바인딩은 transcript·스트림이 여기 없어 보통 죽은 것으로 보이지만 **`attach_pid` 가 내 머신의 산 pid 와 겹치면**(`pid_alive` :3983 는 claude 여부를 안 봄) 살아난다 [f]: beta 의 `chat_target()` 이 `alpha/aaaa1111` 을 골랐다 → 채팅이 아무도 안 읽는 수신함으로. 실리포 바인딩 159건 중 131건이 attach_pid 를 가진다. 같은 충돌로 `rework_claimed(X)=True` [3] → 내 문서의 재작업을 남의 유령 클레임이 막는다.
- **내 전이가 남의 바인딩 파일을 고쳐 쓴다**: `update_active_reqs` :1554 · `_release_binding_claim` :1975("머신은 가리지 않는다") [3]: beta 의 review 전이·`claim --release` 가 `alpha__aaaa1111.json` 을 재작성. sync 로 push 되므로 두 머신이 같은 파일을 쓴다 — docs/08-git-sync.md:13 "같은 파일을 쓸 일이 없음" 은 **코드와 모순**. `sync_run` :8506 은 pull 실패 시 abort+백오프만 하므로 충돌은 조용한 미동기화로 남는다.
- `approvals_seen.json` 이 `state/sessions/` 안에 있어 track 된다(git ls-files 확인) → 한 머신의 소비가 다른 머신의 '본 것'이 되거나 파일 충돌.

**고고학.** machine 가드는 최초 공개 커밋(22e59ad)부터 스폰 함수 둘(:1140, :1221)에 있었고 REQ-20260825-090 이 `_spawn_worker` 하나로 모았다. 의도는 처음부터 "**만든 머신에서만**"이었고 담당자 개념은 없었다. tests 에 `elsewhere` 를 **단정하는** 케이스가 없다(test_wake_handle.py:41 은 코드 열거; test_auto_resume_gate 는 S9_MACHINE=testbox 로 가드를 통과시킬 뿐).

**역할.** `ROLES` 에 viewer 가 있으나(:13147) 강제 지점은 admin 검사 5곳뿐 — viewer 를 막는 코드는 0곳(grep 전수).

## ② 선택지

A. **가드 기준을 담당자로** — 문서에 `assignee`(없으면 `user`)를 두고 `_spawn_worker` 가드를 `assignee == 나 and assignee_machine == 여기` 로. 장점: 게이트가 이미 단일 지점이라 한 줄 교체. 단점: (b)(c)(e) 읽기 경로는 그대로 남아 리드가 손으로 집는 경로가 열려 있음.
B. **클레임을 머신 밖에서도 읽히게** — 바인딩에 `last_seen`(심박) 을 적어 sync 하고, `rework_claimed` 가 `machine != 여기` 바인딩은 pid/transcript 대신 `last_seen` 신선도로 판정. 장점: (a′) 역방향 중복을 막음. 단점: sync 지연(초~분)만큼 창이 남고, 바인딩 커밋 빈도가 늘어 state/sessions 충돌이 커짐.
C. **"내 것" 술어 하나** — `is_mine(row)`(assignee·machine) 를 만들어 next/reopened/stalled/blocked/approvals/digest/훅/`trigger_dependents`/드래그 통지가 전부 그것으로 거른다. 장점: 리드 경로의 오집 근절, 게이트 두 벌 방지 규율과 같은 결. 단점: 관측(남의 상태 보기)과 실행(내가 집기)을 분리해 화면·CLI 에 "남의 것" 표시가 필요.
D. 바인딩을 sync 에서 빼기 — 충돌·유령 클레임을 없애지만 B 가 불가능해지고 docs/08 의 인수인계 용도가 사라짐.

## ③ 권고

**A + C 를 먼저, B 는 그 위에.** 근거: 실측된 오집 7경로 중 6곳이 읽기 경로(b·c·e)이고, 그 지시문은 "지금 착수하라"는 강제 어조라 리드가 남의 문서를 집는 것이 시간 문제다. 실행 귀속의 뿌리는 "누가 맡았나"가 문서에 없다는 것이므로 `assignee`(+`assignee_machine`, 기본 = 생성자·생성 머신) 가 근원이고, 스폰 가드와 읽기 술어가 같은 필드를 보게 해야 게이트가 한 벌이 된다. B 는 남에게 넘긴 뒤에도 만든 머신이 조용하도록 하는 보강이며 A 가 있으면 필요성이 줄어든다(만든 머신은 이미 담당이 아니라서 스폰 안 함). 바인딩 불가침(남의 파일 쓰기·pid 판정 금지)은 선택지와 무관하게 즉시 고칠 결함이다.

## ④ 파생 REQ 후보

1. 「스폰 가드 담당자 기준」 M — goal: `_spawn_worker` 가 assignee·assignee_machine 이 이 머신·이 사용자일 때만 스폰하고 `elsewhere` 를 spawn.log 에 남긴다. 선행: assignee 필드(다른 역할 결정).
2. 「내 것 술어 단일화」 M — goal: next/reopened/stalled/blocked/approvals/digest/훅 주입/드래그 통지가 한 `is_mine` 로 걸러지고 남의 것은 "관측" 절로만 보인다. 선행: 1.
3. 「남의 바인딩 불가침」 S — goal: `update_active_reqs`·`_release_binding_claim`·`chat_target`·`rework_claimed` 가 `machine != current_machine()` 바인딩을 쓰지도 pid 로 살리지도 않는다. 독립.
4. 「의존 해제의 귀속」 S — goal: `trigger_dependents` 가 담당자 머신이 아닌 곳에서는 재개하지 않고 통지만 남긴다. 선행: 1.
5. 「approvals_seen 머신 분리」 S — goal: 소비 기록이 sync 되지 않는다(state/ 로 이동 또는 머신별 파일). 독립.
6. 「교차 머신 회귀 시험」 S — goal: 이 문서의 재현 두 편이 tests/ 로 들어가 [a][a′][b][e][f] 를 단정한다. 선행: 1·3.
7. 「클레임 심박 동기화」 M — goal: 원격 바인딩의 신선도를 `last_seen` 으로 판정. 선행: 3, 필요성은 1 뒤 재평가.

## ⑤ 다른 역할에게

- architect/data: `assignee` 의 형태 — 사용자 id 만인가, `user@machine` 인가, 머신 신원은 hostname(`machine`)과 `machine_fp` 중 무엇으로 통일하나. 생성자(creator)/에이전트 출처와 한 표에 둘 것인가.
- devops: state/sessions 를 계속 sync 할 것인가(B 의 전제) — 하면 바인딩 충돌 대책(머신별 디렉토리·`--ours` 전략), 안 하면 인수인계 화면의 대체.
- security: viewer 강제 지점이 0곳이고 `/api/status` 가 문서 주인을 안 본다 — observer 축은 새 기능이 아니라 기존 role 의 강제 부재부터.
- designer/ux-writer: "남의 것(관측)"과 "내 것(실행)"을 카드·훅 문구에서 어떻게 가르나.
미확인: 채팅 수신함 이벤트가 실제 다중 머신 sync 환경에서 어느 빈도로 유령 세션에 가는지(실측 없음, pid 충돌 확률 추정만).
