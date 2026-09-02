# 014 실행 귀속 규칙 — staff-engineer

대상: REQ-20260902-014-62x6 축 1(실행 귀속)·축 2의 담당자 절반. 코드 미수정, bin/s9 (20345행)·bin/s9-audit-prompt·docs/07·08 직접 확인.

## ① 현황 진단 (확인한 사실)

**게이트가 한 곳이 아니라 세 종류로 갈려 있고, 셋 다 '담당자'를 모른다.**

1. **스폰 관문** `_spawn_worker` bin/s9:7171 — 무인 스폰의 유일한 Popen 경로(rework 7511 · wake 7549 · resume-item 12521 이 모두 여기로 온다). 머신 가드는 7247 `meta.get("machine") != current_machine()` 한 줄인데, 기준이 **문서를 만든 머신**이다. 담당자를 남에게 넘겨도 그 사람 머신은 영원히 `elsewhere` 로 막히고, 같은 사용자의 두 번째 머신도 막힌다.
2. **클레임 판정** `rework_claimed` bin/s9:3517 — `state/sessions/*.json` 전부를 훑는다. 그런데 `state/sessions` 는 `SYNC_DATA_PATHS` bin/s9:8391 에 들어 있어 **남의 머신 바인딩이 pull 로 도착**한다. 그 바인딩의 생존 신호는 전부 로컬 사실이다: `chat_alive` 4279 는 `pid_alive(attach_pid)`(로컬 /proc) 와 transcript mtime(git 은 mtime 을 옮기지 않고, 경로는 로컬에 없다)을 본다. 결과 — 남의 머신 클레임은 **거의 항상 '죽은 것'으로 읽히고**, 드물게 pid 번호가 로컬 프로세스와 겹치면 '살아 있는 것'으로 오판된다. 판정이 두 방향 모두 근거 없이 틀린다.
3. **클레임 등록** `_claim_req` bin/s9:12307 (`s9 claim`·`s9 last --add` 12556 공용) 과 in-progress 전이의 자동 등록 `update_active_reqs` 1554 — **소유 검사가 없다.** 끝난 문서만 거른다(12319). `do_transition` 1716 도 사용자·머신을 보지 않는다. 즉 리드 세션·대시보드 드래그는 남의 문서를 아무 가드 없이 집는다.
4. **리드 입구** — `next_pickup` bin/s9:11002 는 `rework_claimed` + `user == 나`(창작자 기준, 11025) 로 거르지만, 매 턴 훅이 주입하는 `reopened`(10444)·`stalled`(10792)·`blocked`(11145)·`loose` 목록은 **사용자·머신을 전혀 거르지 않는다**(bin/s9-audit-prompt:726-767). 남의 반려 문서가 내 머신에 pull 되면 내 리드가 "이번 턴에 우선 이어서 작업하라"는 지시를 받는다. `CODE_BOOTSTRAP` 14661 의 `s9 next → s9 claim` 도 3번 경로로 들어간다.
5. **동기화 지연은 구조적이다** — `sync_run` 8506 은 문서 이벤트(new/status/note/set/link…, 호출부 1535·1855·12245 등)에만 돈다. **조용한 머신은 pull 을 하지 않는다.** 워처(18707, 30초)는 pull 없이 로컬 색인만 본다. 클레임 도장(`stamp_doc_session` 1997)과 바인딩 쓰기는 `maybe_sync` 를 부르지 않아, 다음 문서 이벤트까지 **내 클레임이 밖으로 나가지 않는다.**
6. 문서 frontmatter 는 `user/machine/session` 뿐(cmd_new 1494, docs/01:39-41). 담당자·생성 주체(사람/에이전트) 필드 없음. 카탈로그 행(1162)에는 `machine` 이 실리지도 않는다.
7. 시험: `elsewhere` 갈래는 test_wake_handle.py:41 이 코드명만 나열한다. 머신 간 중복 스폰 시나리오(두 S9_ROOT + bare remote) 시험은 **미확인/없음**.

## ② 선택지

| | A. 창작 머신 고정(현행 7247 확장) | B. 바인딩 리스(state/sessions 에 만료·하트비트 추가) | C. 문서 리스(frontmatter `assignee` + `lease`) |
|---|---|---|---|
| 담당자 변경 | 불가(머신≠사람) | 가능 | 가능 |
| 같은 사용자 두 머신 | 둘째 머신 영구 차단 | 파일명이 머신별이라 **둘 다 성공** — 경쟁을 판정할 CAS 가 없다 | 같은 줄을 두 머신이 쓰면 rebase 충돌 → **git push 의 non-fast-forward 가 곧 CAS** |
| pull 지연 | 무관 | 바인딩 쓰기는 sync 를 안 부른다(별도 배선 필요) | 문서 쓰기는 이미 sync 를 부른다 |
| 하트비트 | 없음 | 새 시계 필드+주기 커밋 필요 | 담당자의 문서 쓰기(note/status/set)가 곧 갱신 — 추가 커밋 0 |

A 는 요구 ②를 원천 봉쇄한다. B 는 "둘 다 성공"이 치명적이다 — 중복 방지의 핵심은 **경쟁자 둘이 같은 자리에 써야 한다**는 것이고, 바인딩은 설계상(docs/08 "머신 간 같은 파일을 쓸 일이 없음") 그 자리가 아니다. **C 를 택한다.**

## ③ 권고안 — 단일 함수 `exec_verdict` + 획득 `lease_acquire`

**필드(요청 문서)**: `assignee`(기본 = `user`), `origin: human|agent`, `origin_of`(파생 원천 사용자, 기록용), `lease: {user, machine, session, since, renewed}`. 게이트는 **`assignee` 와 `lease` 만** 본다 — parent 사슬을 걷지 않는다(부모가 재할당되면 사슬은 두 진실이 된다). 파생 REQ 는 생성 세션의 `resolve_user()`(335)가 assignee 가 되므로 "내 요청에서 파생된 에이전트 요청"은 자동으로 내 것이다.

```
exec_verdict(meta, local, want) -> Verdict(allow, code, why, holder)
  meta : id,type,status,user,assignee,lease,machine(legacy)
  local: user, machine, session, role, now, sync_mode, local_alive(session)->bool
  want : "spawn" | "claim" | "list"
```
판정 순서(싼 것부터, 첫 거부에서 멈춘다):
1. type≠request 또는 status∈TERMINAL → `closed` (7213 그대로 흡수)
2. local.role == viewer → `observer`
3. `assignee`(없으면 `user`) ≠ local.user → `not-mine` ("담당 {assignee}") — 7247 을 **대체**
4. want=spawn 이고 status≠in-progress → `not-in-progress`
5. lease 가 있고 `now - max(since, renewed) < LEASE_TTL(=CLAIM_GRACE 1800)`:
   - 같은 머신·같은 세션 → allow `renew`
   - 같은 머신·다른 세션 → **로컬 신호**(현 `rework_claimed` 의 pid/tail/mtime)로 생존이면 `busy-local`, 아니면 allow `takeover-local`
   - 다른 머신 → `busy-elsewhere`. **벽시계만** 본다 — 남의 머신 바인딩의 pid·mtime 은 근거가 아니다(진단 2)
6. allow `free`

`lease_acquire(doc_id, local, want)` — 허용/거부가 실제 효력을 갖는 유일한 자리:
① remote 모드이고 마지막 성공 pull 이 `VIEW_FRESH_SEC(60)` 보다 오래됐으면 **pull --rebase 먼저**(진단 5 의 해법 — 워처가 아니라 게이트가 당긴다) ② `exec_verdict` ③ allow 면 lease 를 frontmatter 에 쓰고(`updated` 불변, 1997 규율) `maybe_sync` ④ push 성공 → 획득. pull 충돌/push 거부 → 문서를 다시 읽어 lease 가 남의 것이면 **내 lease 를 지우고 `lost-race`**, 비어 있으면 1회 재시도.

**낙관/비관 판정(요구 ④)**: 스폰은 **비관** — push 확인 전에는 Popen 하지 않는다. 중복 스폰의 값(토큰·서로 다른 노트)이 2~3초 왕복보다 비싸고, 워처 주기가 30초라 지연이 보이지 않는다. 사람의 `s9 claim` 도 같은 경로를 지나되 **네트워크 실패 시에만** 갈린다: 워처는 `net-down` 거부, 사람은 경고 후 허용(책임 주체가 있다). local 모드(.s9-sync 없음/local)는 ④ 가 곧바로 획득이다.

**하트비트**: 새 시계를 만들지 않는다. `HEARTBEAT_WRITE_CMDS`(10475) 가 도는 명령이 담당 머신에서 실행되면 `lease.renewed` 를 갱신하고, 그 쓰기는 이미 sync 된다. 30분 무진전 = 리스 만료 = 현행 `claim_dead`(860) 와 같은 뜻. 종료 전이가 리스를 지운다 — `update_active_reqs` 의 떠남 분기(1589)와 같은 자리.

**재할당(요구 ②)**: `s9 assign <id> <user>` — assignee 갱신 + lease 삭제 + History 한 줄. 권한: 창작자·현 담당자·admin·프로젝트 maintainer 이상(`project_can` 13923 재사용); viewer 는 담당 불가. 옛 담당 머신은 다음 틱에 `not-mine` 을 받는다: 워처는 `worker_stop`(3113)으로 세우고, 리드 세션에는 훅이 "담당이 바뀌었다 — 손을 떼라"를 주입한다.

**한 게이트로 모을 자리(옆문 목록)**: `_spawn_worker` 7247(교체) · `rework_claimed` 3517(5단계의 로컬 하위 판정으로 강등, 남의 머신 바인딩은 건너뜀) · `_claim_req` 12307 · `update_active_reqs` 1554 · `next_pickup` 11025(창작자 필터 → verdict) · 훅 목록 네 곳 `reopened/stalled/blocked/loose` (want=list 로 `not-mine` 제외, 남의 것은 "담당 X — 관찰만" 한 줄로 축약). `do_transition` 자체는 게이트하지 않는다 — 전이는 판정(반려·승인)이고 실행이 아니다; 실행은 클레임에서만 시작된다.

**마이그레이션(요구 ⑤)**: 읽기 폴백 `assignee or user` 로 기존 문서를 고치지 않고 즉시 동작. `lease` 없는 in-progress 문서는 5단계를 건너뛰어 6(free)으로 — 단, 그 문서를 이미 등록한 **같은 머신** 바인딩의 `active_reqs/claim_at` 은 5-b 로컬 판정에 그대로 쓴다(REQ-20260828-005 규율 유지). `machine` 필드는 기록으로만 남고 판정에서 빠진다. 남의 머신 바인딩은 판정에서 무시하되 파일은 그대로 둔다(인수인계 열람용, docs/08).

## ④ 파생 REQ 후보

| 제목 | goal | 크기 | 선후 |
|---|---|---|---|
| 담당자 필드와 assign 명령 | assignee/origin 필드가 생성·조회·재할당 경로에 들어가고 권한 없는 assign 이 거부된다 | M | 1 |
| 실행 귀속 게이트 | exec_verdict 하나가 6 자리(③ 옆문 목록)를 대체하고 시험 매트릭스가 통과한다 | L | 1 뒤 |
| 문서 리스 획득 프로토콜 | 두 S9_ROOT + bare remote 에서 동시 클레임 시 정확히 하나만 획득한다 | M | 2 뒤 |
| 훅 목록의 담당자 필터 | 남의 담당 문서가 재작업 지시로 주입되지 않는다 | S | 2 뒤 |
| 게이트의 선행 pull | 조용한 머신의 워처가 60초 내 원격 변경을 본다 | S | 3 뒤 |

시험 매트릭스(게이트 REQ 의 tdd 노트로): V1 자기 문서·리스 없음→free / V2 담당 타인→not-mine / V3 같은 사용자·다른 머신·리스 신선→busy-elsewhere / V4 같은 머신·다른 세션·세션 죽음→takeover-local / V5 리스 30분 경과→free / V6 재할당 후 옛 머신→not-mine / V7 두 클론 동시 claim→한쪽 lost-race / V8 assignee 없는 구문서→user 폴백 / V9 viewer→observer / V10 남의 바인딩 pid 가 로컬 pid 와 겹쳐도 판정 불변.

## ⑤ 열린 문제 (다른 역할에게)

- **architect/backend**: rebase 충돌 시 `sync_run` 은 abort 후 로컬 커밋을 남긴다(8562). lease 한 줄 충돌은 "상대 것을 취하고 재판정"으로 기계 해소가 가능해야 한다 — 그 해소기를 sync 층에 두는 것이 맞는지, 획득 프로토콜이 별도 pathspec 커밋을 쓰는 것이 맞는지.
- **product-owner**: 부모 재할당 시 자식(파생 REQ)을 따라 보낼지(`--with-children`), 기본은 "안 따라감"으로 제안.
- **security**: `chat_target`(4330 부근)이 남의 머신 바인딩을 채팅 대상으로 고를 수 있다 — 게이트 밖 별도 결함. 시계 편차 가정(±5분 ≪ TTL 30분) 명시 필요.
- **미확인**: 인스턴스 리포 remote 모드에서의 실제 pull 왕복 시간; 원격 REQ 문서의 동시 note 병합 빈도(리스 외 충돌).
