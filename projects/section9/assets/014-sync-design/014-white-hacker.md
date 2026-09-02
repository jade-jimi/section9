`[2026-09-02 13:58:40 KST - white-hacker]` — REQ-20260902-014 공격 관점 검토

승인 범위: 이 저장소의 자체 설계 검토(section9 하네스). 실행 공격 코드는 쓰지 않고 경로만 규명한다. 근거: REQ-20260902-014 위임 지시문.

## 위협 모델 (다중 사용자·다중 머신 git 공유로 갈 때)

- 자산: 각 팀원 머신에서 도는 무인 워커의 실행 권한(파일 편집·`gh`·테스트·`bin/s9`), 요청 귀속(누가 냈나/누가 커밋했나), 개인 설정(자율 실행 허가).
- 신뢰 경계: 인스턴스 리포에 **push 권한을 가진 팀원**과, 그가 미는 문서 본문을 **pull 해 자기 머신에서 여는** 다른 팀원 사이. 지금은 이 경계에 아무 서명·검증이 없다.
- 공격자 능력: 인스턴스 리포에 push 가능한 팀원 하나가 악의적이거나 계정이 탈취됨. 또는 외부 입력(이메일·첨부·채팅)이 문서 본문/노트에 흘러들어옴.
- 핵심 사실: `vault/`·`users/`·`projects/`·`state/sessions`는 전부 **track**된다(`.gitignore`, docs/08-git-sync.md:10-14, `SYNC_DATA_PATHS` bin/s9:8391). `s9-guard`(pre-commit)와 CODEOWNERS는 `bin/ web/ harness/ .github/ .gitignore` **다섯 경로만** 보호한다(bin/s9-guard:19, .github/CODEOWNERS). 그 밖의 track 경로는 아무 member나 커밋·push할 수 있다 — 여기가 공격 표면 전부다.

---

## 시나리오 1 — 공유 문서가 남의 머신에서 임의 실행을 튼다 (심각도: 치명)

**경로.** 무인 워커 스폰의 유일 경로는 `_spawn_worker`(bin/s9:7171)다. 스폰 프롬프트는 `_spawn_rework`(bin/s9:7460)·`_spawn_wake`(bin/s9:7518)가 만든다. 이 프롬프트에 실리는 문서 유래 조각은 셋이다:
1. **프로젝트 에이전트 규정** — `_project_agent_preamble`(bin/s9:13861)이 `projects/<slug>/agents/worker.md`를 **프롬프트 맨 앞에 1500자 그대로** 붙인다(bin/s9:7486, 7525). 역할 규정 위치라 방벽 문구가 약하다.
2. **제목** — `_safe_title`(bin/s9:7453)가 `<<`/`>>`를 `«`/`»`로 치환해 방벽 안에 가둔다.
3. **반려 노트** — `safe_note`(bin/s9:7464)는 `re.sub(r"\s+"," ",note)[:300]`만 한다. **델리미터 치환이 없다.** 노트는 `<<참고>>\n{safe_note}\n<</참고>>`(bin/s9:7510) 안에 그대로 들어간다.

**방벽 탈출(fence escape).** 제목은 REQ-20260830-017에서 `«»` 치환을 받았는데(주석이 "제목은 무방비였다"고 인정), **같은 방벽을 쓰는 노트에는 그 치환이 옮겨지지 않았다** — "게이트가 두 벌이면 성긴 쪽으로 샌다"의 재현. 반려 노트 본문에 `<</참고>>` 를 넣으면 참고 방벽이 그 자리에서 닫히고, 뒤에 이어 쓴 문장은 워커 LLM에게 **명령 위치**로 읽힌다. 노트는 review→in-progress 전이 시 History 라인으로 문서에 박히고(`_last_transition` bin/s9:3290, 워처가 `lt[3]`을 그대로 넘김 bin/s9:8174), 문서 본문은 공유되므로 공격자가 곧바로 채운다.

**게이트를 통과시키는 법.** `_spawn_worker`가 남의 것을 막는 유일 검사는 `meta.get("machine") != current_machine()`(bin/s9:7247)와 오너 설정 `auto_resume`(bin/s9:7237, `owner = meta.get("user")`)다. 그런데 `machine`·`user`는 **프론트매터의 평문**이고 공격자가 자유롭게 쓴다. 공격자가 `machine: <피해자 호스트명>`, `user: <auto_resume 켠 피해자>`로 문서를 지으면 머신 게이트는 통과하고, 피해자 설정(`auto_resume_apply=on` 등)이 봉투 판정에 쓰인다. 마지막 관문은 claim/캡뿐이다.

**영향.** 피해자가 apply 모드면 봉투는 `--permission-mode acceptEdits` + `Bash(python3 tests/:*)` + `Bash(cp .../web/:*)`(bin/s9:7337-7339), `auto_resume_gh`면 `Bash(gh:*)`(bin/s9:7350)까지 붙는다. 주석 스스로 "이 봉투는 경계가 아니다 … `gh api` 하나로 저장소 설정 대부분을 바꿀 수 있다"고 적는다(bin/s9:7343 부근). 즉 공유 문서 한 개가 **피해자 머신에서 편집 자동승인 + GitHub 권한을 쥔 에이전트**를 띄우고, 방벽 탈출로 그 에이전트를 조종한다.

**차단(설계, 게이트 한 곳).** ① `safe_note`에 `_safe_title`과 **같은** 델리미터 치환을 즉시 적용 — 방벽 신뢰의 근본은 약하나 최소한 탈출은 막는다. ② 근원책은 **귀속의 서명**이다: `machine`/`user`/`assignee`를 평문으로 믿지 말고, 스폰 게이트가 "이 머신에서 실행해도 되는가"를 **로컬에만 있는 신뢰값**(예: 이 머신이 발급하고 track하지 않는 self-claim 토큰, 또는 이 머신 세션이 실제로 등록한 active_reqs)으로만 판정하게 한다. 문서가 스스로 "나는 이 머신 것"이라 선언하는 지금 구조는 self-authorization(confused deputy)이다. ③ 프로젝트 에이전트/노트 등 **문서 유래 텍스트는 워커 프롬프트에서 명령 권위를 못 갖게** 데이터 채널로 분리(방벽이 아니라 도구 인자로 전달). 판정 지점은 `_spawn_worker` 한 곳으로 이미 단일화돼 있으니 여기에 세운다.

## 시나리오 2 — 담당자/생성자 필드 위조 (심각도: 높음)

**경로.** 원문이 요구하는 creator/assignee 분리는 프론트매터 필드가 될 텐데, `vault/`는 아무 member나 쓸 수 있어(s9-guard 무보호) **남이 내 담당으로 바꿔 내 머신에 일을 떠넘기거나**(시나리오 1의 machine/user 위조와 결합), `user`·`agents`·`contributions`를 고쳐 **내 이름으로 기여가 쌓이게** 만들 수 있다. post-commit 훅이 커밋 노트를 문서에 남기므로(bin/s9-install:151) 실행 흔적도 위조 귀속을 따라간다. git 커밋 저자 자체는 로컬 git 사용자지만, 시스템 내부의 "누가 했나"는 전부 이 평문 필드다.

**차단.** 담당자 변경을 **전이 이벤트**로만 허용하고(임의 필드 편집이 아니라 `s9 assign` 같은 명령 + History 기록), 그 이벤트에 행위자 신원을 붙여 사후 감사 가능하게. 강제(비위조)는 시나리오 1-②의 신뢰값 위에서만 성립한다 — 서명 없는 필드는 "실수 방지·감사"까지가 한계임을 설계에 명시(s9-guard가 이미 그 한계를 인정하듯).

## 시나리오 3 — 남이 내 설정을 바꿔 내 머신 동작을 바꾼다 (심각도: 치명)

**경로.** `users/<name>/config/settings.json`은 **track된다**(git ls-files 확인). 이 파일이 `auto_resume`·`auto_resume_apply`·`auto_resume_gh`·`s9code_args`·`worker_worktree`를 담고(nicehugepark 실값: apply=on, gh=on, `s9code_args="--permission-mode auto --model opus"`), `user_config`(bin/s9:277)가 이걸 읽어 봉투(시나리오 1)와 `s9 code` 기동 인자(`code_launch_args` bin/s9:2647)를 정한다. **push 권한자가 남의 settings.json을 커밋하면**, 피해자가 다음 pull에서 그것을 받고 이후 자기 머신의 워커·`s9 code`가 공격자가 정한 권한으로 뜬다. 개인·비밀은 `local.json`으로 분리돼 gitignore되지만(bin/s9:264), **자율 실행 허가를 여는 바로 그 키들이 공유 파일에 산다.**

**차단.** 자율 실행 권한을 여는 설정(`auto_resume*`, `s9code_args`, `worker_worktree`)은 **track 대상에서 빼고 `local.json`(머신·계정 로컬)으로 옮긴다.** 공유돼야 하는 것은 표시 취향(skin/tone)뿐이다. "이 머신이 무엇을 자동 실행해도 되는가"는 그 머신의 주인만 정한다 — 원격이 값을 밀어 넣을 수 있으면 그건 원격 코드 실행 스위치다.

## 시나리오 4 — 프로젝트 에이전트 정의로 남의 세션을 조종 (심각도: 높음)

**경로.** `projects/<slug>/agents/*.md`는 track되고 s9-guard **무보호**다. SessionStart 훅이 `sync_project_agents`(bin/s9:13812)로 `.claude/agents/<slug>--이름.md`에 미러해 **네이티브 subagent 정의**로 만들고(bin/s9-audit-session:357), 무인 워커는 `worker.md`를 프롬프트 서두에 주입(시나리오 1-①)한다. 즉 그 프로젝트를 여는 모든 팀원의 에이전트 역할 규정과 워커 봉투 프롬프트를 **공격자가 원격에서 바꿔 쓴다.** 이것은 프롬프트 방벽 밖의, 권위 있는 시스템 프롬프트 주입이다.

**차단.** `projects/**/agents/**`를 s9-guard PROTECTED와 CODEOWNERS에 추가해 admin 리뷰 없이는 main에 못 들어가게 한다(같은 게이트에 얹는다). 근본적으로 "코드처럼 실행되는 텍스트"는 데이터가 아니라 harness와 같은 신뢰 등급으로 다뤄야 한다.

## 시나리오 5 — git 훅을 매개로 한 코드 실행 (심각도: 조건부 치명)

**사실.** `.git/hooks/*`는 **git이 전송하지 않는다** — push로 남의 훅 파일 자체를 바꿀 수는 없다(로컬 검증: pull로 훅 내용 변경 안 됨). 그러나 `post-merge`/`post-checkout`은 pull마다 **작업 트리의 `bin/s9 index rebuild`와 `bin/s9-install`을 실행**한다(bin/s9-install:151-156). 실측: `pull --rebase --autostash`는 로컬 커밋 유무와 무관하게 `post-checkout`+`post-rewrite`를 fire했다(`post-merge`는 rebase 경로라 직접은 안 뜨지만 `sync_run`은 rebase, 체크아웃 경유 훅이 붙는다). 따라서 **공격자가 `bin/s9`나 `harness/`를 바꿔 push할 수 있으면**, 그것을 pull하는 모든 머신이 훅을 통해 그 코드를 실행한다 = 함대 전역 원격 코드 실행. `s9-install`은 여기서 `~/.claude/settings.json`의 훅까지 다시 쓴다.

**현 방어와 구멍.** `bin/`·`harness/`는 s9-guard(로컬, S9_USER 위조로 우회 가능 — 설계상 인정)와 **서버측 branch protection**이 막는다. 실측: main에 `require_code_owner_reviews=true`, `required_approving_review_count=1`이 걸려 있다 — 다행. 그러나 **`enforce_admins=false`**다: admin 계정(또는 그 탈취)은 리뷰 없이 직접 push한다. 그리고 원문이 그리는 "다중 사용자 실시간 동기화"가 **main 직접 push 모델**이면(브레인스토밍의 첫 후보), 이 보호는 PR을 거치는 사람에게만 유효하고 `sync_run`의 자동 commit→push 경로(bin/s9:8535)는 데이터 경로만 실으므로 bin은 안 나가지만, **사람이 손으로 bin을 커밋해 push하는 순간** CODEOWNERS 우회가 곧 전역 실행이다.

**차단.** ① `enforce_admins=true`로 admin도 예외 없이 리뷰를 거치게. ② PROTECTED에 `projects/**/agents/**`(시나리오 4)와 자율 실행 설정 파일(시나리오 3)을 포함 — "실행/권한을 여는 것은 전부 admin 게이트"라는 한 원칙으로 통일. ③ 동기화 브랜치 전략을 정할 때 **코드(bin/harness/web)와 데이터(vault/users/projects)를 다른 신뢰 등급으로 분리** — 데이터는 실시간 공유하되, 코드는 pull이 곧 실행이므로 절대 실시간 자동 동기화 대상에 넣지 않는다.

---

## 종합 권고 (우선순위)

1. **자율 실행을 여는 모든 것을 track에서 빼고 로컬로**: `auto_resume*`·`s9code_args`·`worker_worktree`(시나리오 3), 그리고 스폰 게이트의 self-authorization 제거(시나리오 1-②). — 이 하나가 시나리오 1·3의 근원.
2. **s9-guard/CODEOWNERS PROTECTED 확장** + `enforce_admins=true`: `projects/**/agents/**` 추가(시나리오 4·5).
3. **워커 프롬프트의 문서 유래 텍스트를 데이터 채널로 분리**하고, 임시책으로 `safe_note` 델리미터 치환(시나리오 1).
4. **담당자/귀속은 전이 이벤트 + 감사**로만, 평문 필드 신뢰의 한계를 설계에 명문화(시나리오 2).

## 파생 REQ 후보

- **자율실행 설정 로컬 격리** (goal: `auto_resume*`·`s9code_args`가 track되지 않고 원격 push로 바뀌지 않음을 시험으로 확인) · 크기 M · 선행 없음(가장 시급).
- **스폰 게이트 self-auth 제거** (goal: `machine`/`user` 평문만으로는 남의 머신에서 워커가 뜨지 않음) · 크기 L · 위 설정 격리 후.
- **워커 프롬프트 주입 방벽 정비** (goal: 노트·제목·프로젝트 에이전트가 워커에게 명령 권위를 못 가짐, fence-escape 회귀 시험) · 크기 M · 독립.
- **실행경로 track 확장 게이트** (goal: `projects/**/agents/**`가 admin 승인 없이 main에 못 들어감 + `enforce_admins=true`) · 크기 S · 독립.

## 다른 역할에게 넘길 열린 문제

- (architect) 브랜치 전략에서 코드/데이터 신뢰 분리를 어떻게 구조화할지 — 데이터만 실시간, 코드는 릴리스 게이트.
- (backend) 스폰 게이트가 신뢰할 "로컬 전용 실행 승인" 값의 형태(머신 발급 토큰 vs. 세션 active_reqs만) 결정.
- (security-engineer) observer 계정이 공유 서버(`--host 0.0.0.0`)에 붙을 때 `whoami_info`의 실인증 부재(bin/s9:11466 부근, 문서 스스로 "외부 노출 시 실인증 필요") — 이 REQ 범위 밖이나 다중 사용자로 가면 함께 열린다.
