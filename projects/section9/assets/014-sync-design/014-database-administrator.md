# REQ-20260902-014-62x6 · 저장 배치·식별자·인덱스 판정 (database-administrator)

결론 먼저.
- **디렉토리를 프로젝트/사용자별로 나누지 않는다.** 파티션 키는 바꿀 수 없는 값이어야 하는데 `project` 는 `s9 set --project` 로 바뀌는 값이다. 지금 배치(`vault/<type>/YYYY/MM/`)의 키는 created 날짜라 불변이고, 프로젝트·사용자 축은 이미 카탈로그(`index/by-project`, `by-user`)가 준다. 나누면 얻는 것은 없고 자산 이동·rename 충돌·경로 이중 진실이 생긴다.
- **ID 스킴은 유지하고 지문 등록(registry)만 더한다.** 접미 4자(머신 지문)는 같은 날 NNN 충돌을 "다른 머신끼리" 는 막지만, 지문 자체의 충돌을 감지하는 장치가 없다. 사용자 접미는 틀린 단위다(한 사람이 두 머신에서 동시에 발번한다). 발번 단위 = 잠금 단위 = 머신이 맞다.
- **문서 1개 = 파일 1개를 유지하되, 병합을 줄 단위가 아니라 필드 의미 단위로 하는 merge driver 를 둔다.** 저널 분리는 읽는 쪽 전부를 바꾸는 비용 대비 이득이 없다. 지금은 두 머신이 같은 문서에 노트를 하나씩만 붙여도 `pull --rebase` 가 실패하고 sync 가 영구 정지한다(로그만 남는다).
- **인덱스는 6천 문서까지는 지금 구조로 버틴다(실측 rebuild 1.0s). 3천을 넘기면 증분 갱신으로 바꾼다.** 매 쓰기마다 전체 재생성이고 그동안 `.s9.lock` 을 쥐므로 비용이 문서 수 × 세션 수로 곱해진다.
- **마이그레이션은 파일 이동 0건.** 필드 추가는 additive 백필 1커밋(롤백 = revert), 포맷 변경은 읽기 먼저 쓰기 나중(expand→contract).

---

## ① 현황 진단 (코드·실측으로 확인한 것)

**배치와 경로 해석**
- 새 문서 경로는 한 곳에서 만든다: `bin/s9:1487` `os.path.join(VAULT, subdir, f"{d:%Y}", f"{d:%m}", doc_id+".md")` — 키는 created 날짜.
- id→경로 해석은 배치와 무관하다. `locate()` `bin/s9:901-913` 는 카탈로그 행의 `path` 로 열고, 카탈로그가 낡으면 `walk_docs()` (`bin/s9:464-470`, `os.walk(VAULT)`) 로 파일명 기준 폴백한다. `find_path` `bin/s9:916-923` 는 그 위에 모호성 검사만 얹는다. 즉 **디렉토리를 어떻게 나눠도 find_path 는 깨지지 않는다** — 깨지는 것은 다른 데다(아래).
- `link_audit` (`bin/s9:10230`대, `for p in walk_docs()` 로 id→[path,meta] 사전 구성) 도 id 기준이라 배치 무관.
- 배치를 가정하는 자리: ① `next_id` `bin/s9:946-960` 가 `VAULT/<subdir>` 만 walk 한다 ② 첨부는 문서 **옆** `assets/<id>/` 에 붙는다 (`bin/s9:9719, 9822, 12929`) — rm 은 `.trash/assets-<id>` 로, restore 는 `home/assets/<id>` 로 함께 옮긴다(`bin/s9:12861-12867, 12929-12934`) ③ 프로젝트 변경 `cmd_set` `bin/s9:8791` 은 frontmatter 만 고치고 파일을 옮기지 않는다.
- 프로젝트 없는 요청 3건, `project: section9` 579건(요청 582건). 세션·질문·지식은 project 유무가 섞여 있다(미확인: 타입별 분포).

**ID**
- `machine_fp()` `bin/s9:928-944`: `sha1(hostname|$HOME)` → base36 4자(공간 36⁴ = 1,679,616). `S9_ORIGIN` 으로만 재정의. 등록부 없음 — 지문이 겹쳐도 아무도 모른다.
- `next_id` `bin/s9:946-960`: 그날 파일명 중 **지문이 같거나 지문이 없는(레거시)** 것의 최대 NNN+1. 모형 vault 에서 다른 hostname 으로 `s9 new` 하니 `REQ-20260902-001-a5yd` 가 나왔다(기존 013 과 무관하게 001) — 지문별 독립 순번 확인.
- 레거시(접미 없음) 230건: requests 184 · sessions 34 · knowledge 11 · projects 1. `resolve_id` `bin/s9:790-798` 가 정확 일치를 우선하고, `_build_id_alias` `bin/s9:855-865` 가 레거시가 점유한 짧은 형태를 별칭에서 뺀다 — 옮기거나 개명할 이유가 없다.
- 워커 worktree 는 vault 를 본 저장소와 공유한다 (`WORKTREE_SHARED_DIRS` `bin/s9:19012`) — 같은 머신 두 트리가 같은 지문으로 이중 발번하는 경로는 없다.
- `docs/01-document-format.md:22-24` 는 아직 `PREFIX-YYYYMMDD-NNN` (접미 없음) 이라고 적혀 있다 — 문서 낡음.

**인덱스·조회 비용** (실측. 실 vault 894 문서·7.7MB·평균 8.6KB·최대 164KB / 모형 6,465 문서·168MB — 실 문서에 지문 aa01~aa09 를 바꿔 9배 복제)

| 작업 | 894 | 6,465 | 비고 |
|---|---|---|---|
| `index rebuild` | 0.27s | 0.93~1.12s | 선형 ≈0.15ms/문서 → 2만 문서 ≈3.3s |
| `new request` (walk+rebuild) | — | 0.93s | |
| `note` (write+rebuild) | — | 1.06s | **이 동안 `.s9.lock` 점유** |
| `ls --status` / `search`(메타) | 0.17 | 0.23 / 0.25s | 카탈로그만 읽음 |
| `search --body` | 0.23 | 0.59s | 파일 전부 open (`bin/s9:8856-8862`) |
| `linkcheck` | 0.23 | 0.48s | 전 문서 read_doc |
| catalog.jsonl | 657KB(846행) | 5.0MB / gzip 197KB | `/api/catalog` 는 가시 행 전부를 보낸다 (`bin/s9:17774-17795`, ETag·gzip) |

- rebuild 는 쓰기 명령마다 호출된다(27개 호출처, `grep -n "rebuild_index("`), 전량 스캔 + `os.replace` 원자 교체 (`bin/s9:1280-1300`). `load_catalog` 는 stat 키 캐시 (`bin/s9:652-685`) 라 읽기 쪽은 이미 싸다.
- docs/02 가 "수천 개가 되면 incremental (Phase 4)" 라고 이미 적어 두었다.

**동시 쓰기와 병합**
- 문서 한 장의 쓰기 지점: frontmatter `updated`(모든 쓰기가 갱신, `bin/s9:1742, 8732, 8816…`), `contributions`/`agents`/`relates` 가 **한 줄 JSON** (`fm_dump` `bin/s9:355-370`), Notes 는 History 앞에 append, History 는 파일 끝에 append. 두 머신이 같은 문서에 노트를 하나씩 붙이면 `updated` 줄 + Notes 끝 + History 끝 세 곳이 동시에 충돌한다.
- `sync_run` `bin/s9:8556-8566`: `pull --rebase --autostash` 실패 시 `rebase --abort` → 60s 백오프 → 로그만. **자동 해소 경로가 없고**, 다음 시도도 같은 충돌로 실패하므로 그 머신은 그때부터 조용히 미동기화다(docs/08 이 말한 "무증상 미동기화" 와 같은 부류).
- `.gitattributes` 없음, merge driver 없음. `sqlite3` FTS5 는 stdlib 에서 사용 가능(3.45.1 확인).

## ② 선택지와 장단점

**A. 디렉토리 분할 (`vault/<project>/…` 또는 `vault/<project>/<user>/…`)**
- 해결한다고 주장되는 것 vs 실제:
  - 충돌: git 충돌은 파일 단위다. 디렉토리는 충돌 면적을 1바이트도 바꾸지 않는다.
  - 조회 성능: 조회는 카탈로그가 한다(`apply_filters` `bin/s9:1339`, 메모리 필터). 디렉토리는 조회 경로에 없다. `next_id` 는 오히려 walk 범위가 넓어진다.
  - 권한 경계: git 에는 디렉토리 읽기 ACL 이 없다. observer 의 read-only 는 branch protection + `doc_visible` (`bin/s9:17610`대, 자기신고 기반) 의 몫이지 배치의 몫이 아니다. GitHub CODEOWNERS 경로 규칙은 PR 흐름에서만 뜻이 있는데 이 시스템은 main 직접 push 다.
  - sparse-checkout: 유일하게 실재하는 이득. 그러나 체크아웃 안 된 프로젝트의 문서로 가는 `parent/relates` 가 `link_audit` 에서 전부 "미존재" 로 잡히고 `find_path` 가 die 한다. 프로젝트별 데이터 격리가 진짜 요구라면 답은 디렉토리가 아니라 **프로젝트별 인스턴스 리포**(DOC-20260824-003 이 이미 그 구조다).
- 깨는 것: 프로젝트 변경 = `git mv` + `assets/<id>/` 동반 이동. 한쪽이 옮기고 다른 쪽이 같은 문서를 고치면 rename/modify 충돌(자동 해소 불가). 카탈로그 `path` 가 pull+rebuild 전까지 낡아 `locate` 가 폴백 walk 로 떨어진다. 프로젝트 없는 문서용 `_none/` 버킷이 필요하고, `project` 필드와 경로가 **같은 사실의 두 사본**이 된다.
- 판정: 기각.

**B. ID 접미**
- 머신 지문(현행): 발번 잠금(`.s9.lock` = 루트 단위, `bin/s9:32`) 의 도메인과 일치. 통신 없이 유일. 약점은 지문 충돌 미검지 — 생일 확률은 머신 10대 3×10⁻⁵, 100대 0.3%, 1000대 26%. 결정적 충돌(같은 hostname+HOME: 이미지 배포 PC, `ip-10-0-0-1` 류 VM)은 확률이 아니라 구성의 문제인데 이쪽이 실제 위험이다. 충돌 시 결과: 같은 날 같은 NNN → 같은 파일명 add/add → sync 영구 정지(유실은 아님).
- 사용자 접미: 한 사용자가 노트북·데스크톱에서 같은 날 발번하면 같은 NNN → 충돌. 틀린 단위.
- 문서별 랜덤(ULID 류): 전역 유일은 되지만 NNN 의 뜻("이 머신의 그날 n번째")과 `REQ-013` 축약 관습(`resolve_short` `bin/s9:800-835` 가 의존)이 사라진다. 접미 정규식 `[0-9a-z]{4}` 가 bin/s9 6곳 + web/tests 10곳에 박혀 있어 길이 변경도 이주 비용이 크다.
- 정렬성: `rows.sort(key=id)` 는 날짜→NNN→지문 순이라 머신 간 시간순이 아니다. 시간이 필요한 곳은 이미 `created` 로 정렬한다(`resolve_short`). 유지 가능.
- 판정: 현행 유지 + 지문 고정(pin) + 등록부 + pull 후 충돌 검지.

**C. 인덱스**
- 현행 전량 rebuild: 단순·무결. 비용은 문서 수에 선형이고 쓰기마다 지불하며 잠금을 쥔다. 다중 사용자에선 훅이 턴마다 note 를 쓰므로 세션 5개 × 2만 문서 = note 하나가 3초 잠금 대기를 만든다.
- 증분 upsert: `write_doc` 한 경계에서 그 문서 행만 교체(jsonl 재작성은 O(N) 이지만 파싱 없이 5MB 쓰기 수십 ms). pull 뒤에는 `git diff --name-only ORIG_HEAD HEAD -- vault` 로 바뀐 파일만. 전량은 `s9 index rebuild` 명시 호출과 드리프트 검지(행 수 ≠ 파일 수) 때만.
- SQLite(FTS5): `--body` 검색과 필터 인덱스를 해결하지만 소비자(jq, 대시보드 /api/catalog, by-*.md) 가 jsonl 을 본다. jsonl 을 export 로 남기고 엔진만 바꾸는 것은 가능하나 지금 수치(0.59s/6천)로는 시기상조.
- 판정: 증분 upsert 를 3천 문서 전(또는 rebuild 0.5s 초과 시) 도입, SQLite 는 1만 문서 또는 `--body` 1s 초과 시.

**D. 문서 1개=파일 1개 vs 사용자별 append-only 저널**
- 저널(`events/<id>/<fp>.jsonl` 당 머신 append): 병합 충돌 0. 대가 — 읽는 곳 전부(`read_doc` 호출자, `catalog_row`, `_tdd_progress`, `_review_point`, 대시보드 문서 뷰)가 fold 를 해야 하고 상태(status) 의 진실이 "마지막 이벤트" 로 옮겨가 `s9 show` 한 장이 곧 문서라는 전제가 무너진다. 재발 위험: head 문서와 저널 두 진실.
- 단일 파일 + 의미 병합: `.gitattributes vault/**/*.md merge=s9doc` 와 드라이버 `s9 merge-doc %O %A %B` — Original 은 동일해야 함(다르면 충돌 유지), frontmatter 는 키별 규칙(`updated`=max, `status`=History 시간순 마지막, 목록 필드=합집합·`contributions` 는 (actor,started) 키 dedup), Notes/History 는 타임스탬프 헤더(`NOTE_HDR_RE` `bin/s9:1205`) 기준 합집합 정렬. 실패하면 git 충돌 그대로 → sync 가 `blocked` 로 드러내야 한다(지금은 로그뿐).
- 선행 조건: 한 줄 JSON 목록을 항목당 한 줄로 바꿔 줄 단위 3-way 가 먼저 덜 부딪히게(`fm_parse` `bin/s9:393-412` 가 한 줄만 읽으므로 읽기 확장이 먼저).
- 판정: 단일 파일 유지 + 의미 병합 드라이버. 저널은 드라이버가 실패하는 유형이 실측되면 그때 그 필드만.

## ③ 권고안

1. 배치 그대로. `project`/`creator`/`assignee` 는 frontmatter 필드이고 물리 위치가 아니다. 통합 조회는 카탈로그가 이미 하고 있다.
2. ID `PREFIX-YYYYMMDD-NNN-<fp4>` 유지. 지문을 첫 사용 시 `users/<me>/config/local.json`(gitignore) 에 고정하고, 추적 파일 `users/<me>/machines.json` 에 `{fp: hostname, first_seen}` 을 등록. post-merge 훅에서 같은 fp 에 다른 hostname 이 둘이면 경고 + 그 머신의 `new` 를 막는다(`S9_ORIGIN` 재지정으로 해제). 레거시 230건은 손대지 않는다.
3. 병합: 목록 필드 줄 단위 직렬화(읽기 먼저) → merge driver → sync 실패를 `blocked` 로 드러내기. 리허설 테스트(scratchpad 에 클론 둘, 같은 문서에 각각 note, pull) 가 done 조건.
4. 인덱스: 증분 upsert 를 지금 S 크기로 준비하고 3천 문서 전에 켠다. `/api/catalog` 는 기본을 "보관 제외 + 열린 문서 + 최근 N일 done" 으로 좁힌다(2만 문서에서 15MB/폴은 안 된다).
5. 마이그레이션(현재 894 문서, 단일 머신 62x6):
   - 0) 실행 중 세션 없음 확인, `s9 sync` off(인스턴스에서만 해당; 이 업스트림 리포는 `.s9-sync` 없음).
   - 1) 백필 스크립트 `--dry` 로 변경 건수 출력 → 검토 → 실적용. 내용: creator/assignee 가 없으면 `user` 값으로, origin 없으면 `human`. 멱등(있으면 건너뜀). 한 커밋. 롤백 = `git revert <그 커밋>`.
   - 2) `machines.json` 에 `62x6 → DESKTOP-TEHV1KR` 시드.
   - 3) `index rebuild` → `linkcheck` 0건 확인 → 행 수 = 파일 수 확인.
   - 4) 다른 머신은 pull → post-merge rebuild. 파일 이동이 없으므로 rename 충돌 없음.
   - 5) 리허설: 클론 두 벌로 동시 note → 자동 병합 확인(복원 훈련에 해당). RTO/RPO 는 git 자체 — 유실 창은 마지막 push 이후 로컬 커밋(sync 가 이벤트마다 커밋하므로 사실상 0), 복구 시간은 clone 시간.
   - 우발 계획(분할을 끝내 택할 경우): sync 전 머신 정지 → 단일 커밋 `git mv`(assets 포함) → 전 머신 pull 완료 확인 후 재개. 롤백 = revert. 이력은 `git log --follow` 로만 이어지고 `blame`·plain `log -- path` 는 끊긴다.

## ④ 파생 REQ 후보

| 제목 | goal | 크기 | 선후 |
|---|---|---|---|
| 머신 지문 고정과 등록부 | pull 후 같은 지문에 다른 hostname 이 있으면 경고하고 그 머신의 발번이 멈춘다 | S | 선행 없음 |
| frontmatter 목록 줄 단위 직렬화 | contributions·agents·relates 가 항목당 한 줄이고 옛 한 줄 JSON 도 읽힌다 | S | 병합 드라이버 앞 |
| 문서 의미 병합 드라이버 | 두 클론이 같은 문서에 note 를 붙인 뒤 `pull --rebase` 가 사람 손 없이 합쳐진다(리허설 테스트 포함) | M | 위 둘 뒤 |
| sync 실패의 가시화 | pull/push 실패가 로그가 아니라 blocked 카드로 보인다 | S | 드라이버와 독립 |
| 증분 카탈로그 갱신 | 문서 하나 쓰기 후 인덱스 갱신이 문서 수와 무관하게 100ms 이내, pull 뒤 변경 파일만 갱신 | M | 3천 문서 전 |
| 카탈로그 응답 창 | 2만 문서에서 `/api/catalog` 기본 응답이 1MB 이하 | S | 증분과 독립 |
| 생성자·담당자 필드 백필 | 894 문서에 creator/assignee/origin 이 채워지고 revert 한 번으로 되돌아간다 | S | architect 필드 확정 뒤 |
| ID 스킴 문서 정합 | docs/01 이 현행 uid(접미) 스킴과 레거시 규칙을 기술한다 | S | 독립 |
| FTS 검색 인덱스(조건부) | 1만 문서에서 `search --body` 1s 이내 | L | 1만 문서 또는 1s 초과 시 |

## ⑤ 다른 역할에게 넘기는 질문

- architect: creator/assignee/origin 의 이름·값 집합과 **쓰기 분할 규칙**(누가 어느 섹션을 쓰나 — 담당자 머신만 status 를 바꾸는가, 승인자의 review→done 은 예외인가). 병합 드라이버의 필드별 규칙은 이 답에 종속된다.
- security-engineer: `doc_visible` 은 자기신고 `me` 기반이다. observer 의 read-only 는 서버 인가 + branch protection 으로만 강제되고 배치로는 불가하다 — 그 층을 어디에 세울지.
- backend-developer: sync_run 의 pull-fail 이 작업 흐름에 드러나지 않는다. blocked 전이로 연결할 때 어떤 세션이 그 문서의 주인인지(클레임) 를 어떻게 고르나.
- devops-engineer: merge driver 설정은 클론마다 `git config` 다 — `s9-install` 이 훅과 같이 심어야 한다. 인스턴스 리포 여러 개(프로젝트별 격리) 를 택하면 사용자 등록부는 어디가 정본인가.
- product-owner: 프로젝트별 **데이터 격리**(남의 프로젝트 문서가 내 디스크에 없어야 하는가) 가 요구인지. 예라면 답은 디렉토리가 아니라 인스턴스 리포 분리다.

미확인: 세션·질문·지식 문서의 project 분포, 실제 다중 머신에서 지문 충돌 사례(현재 단일 머신 62x6 뿐이라 관측 불가), `--body` 검색이 페이지 캐시 없는 콜드 상태에서 걸리는 시간.
