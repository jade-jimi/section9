<!-- section9 protocol — 모든 AI 하네스(Claude/Gemini/Codex/Copilot …)에 공통 주입되는 규약.
     하네스가 자동 훅을 지원하면(예: Claude Code) 1·3·6번은 훅이 대신 수행한다. -->

# section9 작업 규약 (AI agent용)


## 응답 형식 (모든 에이전트·예외 없음)

모든 응답은 **현재 시각과 응답 주체 이름** 한 줄로 시작한다 — 대괄호 안에 한
덩어리로 묶고, 백틱으로 감싼다:

```
`[2026-08-26 22:16:35 KST - lead]`
```

백틱은 **커밋 해시가 받는 그 강조**다(인라인 코드). 마크다운 제목 기호 `#` 는
붙이지 않는다 — 제목은 본문 구조를 뜻하지 이 표기의 강조 수단이 아니고,
헤딩을 렌더하지 않는 화면에서는 `#` 문자가 그대로 새어나온다.

이름은 리드가 직접 답할 때 `lead`, 위임된 에이전트는 자기 역할명(`designer`,
`backend-developer` …)이다 — 누가 말하고 있는지가 보여야 위임된 작업의 보고를
리드의 말과 구분할 수 있다.
매 응답마다다 — 짧은 답도, 이어지는 답도, 서브에이전트의 보고도 생략하지 않는다.
**시각을 지어내지 마라.** 모델은 지금이 몇 시인지 모른다: 훅이 주입하는 `◈ 현재 시각`
값을 그대로 쓰고, 그 주입이 없는 환경(서브에이전트·훅 없는 하네스)이면
`date '+%Y-%m-%d %H:%M:%S KST'` 로 직접 얻어라. 어림짐작한 시각은 없느니만 못하다.


너의 외부기억은 `~/section9` 이다 (CLI: `~/section9/bin/s9`). 컨텍스트가 아니라 여기에 기록된 것만이 영속한다.

0. **최초 부트스트랩**: `~/.claude/settings.json` 에 section9 훅이 없거나 이 환경이 처음이면
   먼저 `~/section9/bin/s9-install` 을 실행해 훅/스킬/역할에이전트/git hook을 설치하라 (Windows: `bin\s9-install.cmd`).
   **역할 에이전트·스킬은 Claude Code 세션이 '시작될 때'만 로드된다** — 세션 도중 설치하면 이 세션에선
   스폰 불가하니, 설치 후 반드시 **세션 재시작**을 안내하라(그래야 designer 등 역할 에이전트 위임이 작동;
   훅/audit도 재시작 또는 /hooks 리로드로 활성). 즉 설치는 작업 시작 '전에' 완료돼 있어야 한다.
1. **세션 시작**: `s9 digest` 를 실행해 진행 중 작업을 파악하라. 세션 식별자가 있으면 모든 s9 호출에 `S9_SESSION=<앞8자>` 를 붙여라.
2. **요청 접수**: 사용자의 작업 요청은 반드시 request 문서로 기록하라 —
   `s9 new request --title '20자 이내 명사구' --summary '...' --size S|M|L [--project P] [--parent ID] --body '원문'`.
   단순 질문/감탄은 기록하지 말고 `s9 log "question: ..."` 로 세션 로그만 남겨라.
   **한 프롬프트에 서로 다른 작업 요청이 여러 개면 반드시 분리하라**: 첫 번째(또는 가장 큰)
   요청을 주 REQ로 두고, 나머지는 각각 `s9 new request --parent <주 REQ>` 로 등록해
   개별 상태로 추적한다. 하나의 REQ에 뭉뚱그리면 부분 완료를 추적할 수 없다.
   **분리한 파생 REQ 중 이번에 처리할 것은 open으로 방치하지 말고 즉시 in-progress로 착수하라** —
   필요한 파생 작업의 진행에 사용자의 별도 지시를 기다리지 않는다.
3. **상태 전이**: 착수 `s9 status <id> in-progress`, 완료 `done`, 확인 대기 `review` — 항상 `--note` 로 근거를 남겨라.
4. **작업 기록**: 구현/결정의 최종 보고를 `s9 note <id> "..." --label response` 로 문서에 남겨라. 터미널 출력은 사라진다.
   **모든 작업 노트는 처리한 에이전트를 `--agent` 로 명시하라** — 리드가 직접 하면 `--agent lead:<model>`(예: `lead:claude-opus-4-8`), 위임했으면 그 역할(예: `--agent security-engineer`). REQ 프론트매터 `agents:` 에 자동 누적되어 "이 요청에 어떤 에이전트가 관여했나"가 문서 최상단에서 일람된다. Claude는 Stop/SubagentStop 훅이 이를 기계적으로 수행하므로 별도 조치 불필요; **훅이 없는 하네스(Gemini/Codex 등)는 리드가 `--agent` 를 직접 붙여라.**
   **개발/구현 요청이면 코드 착수 전에 TDD 시나리오(정상/경계/실패/회귀 케이스)를 `s9 note <id> --label tdd` 로 REQ 문서에 먼저 작성**하라 — 사람이 구현 커버리지를 문서에서 확인할 수 있어야 한다. 통과한 시나리오는 체크(`- [x]`)로 갱신한다. (tdd 스킬 참조)
5. **관계/지식**: 파생 작업은 `s9 link --parent`, 재사용할 지식은 `s9 new knowledge`.
   새 스킬 역량이 필요하면 **먼저 마켓플레이스에서 검색·설치**하고(집단지성 우선), 없을 때만 자작한다 (harness/claude/skills/README.md).
6. **주체**: 사용자가 요청 주체 변경을 원하면 `s9 user switch <이름>` (미등록이면 `s9 user add` 먼저).
7. **위임(라우팅)**: 전문영역 작업(프론트/백엔드/DB/보안/ML/테스트/문서 등)은 그 역할 에이전트에 위임하고, 서로 독립적인 하위작업이 여럿이면 병렬로 위임하라.
   **직접 처리 하한선** — 다음은 리드가 직접 하라(왕복 비용·컨텍스트 손실이 위임 이득을 넘는다): ① size S 급 또는 단일 파일 수정, ② 한 턴 안에 끝나는 단순 작업, ③ 여러 영역을 관통하는 판단·설계, ④ section9 자체·메타 작업. 판단이 애매하면 직접 처리 쪽으로 기울여라(과잉위임 방지).
   **위임 산출물도 audit 대상이다** — Claude는 SubagentStop 훅이 서브에이전트 최종 보고를 `--label subagent` 로 자동 캡처한다. 훅이 없는 하네스는 리드가 서브에이전트 결과 요지를 `s9 note <id> --label subagent` 로 직접 남겨라. 위임을 audit 공백으로 만들지 마라.
   **화면 디자인은 designer 에이전트가 기본이다** — 대시보드·UI·스킨 등 시각 작업은 리드가
   직접 CSS를 만지지 말고 `designer` 에 위임하라(그 에이전트가 `s9-design`·`browser-verify` 스킬을
   로드한다: 완성도 기준과 이 제품의 시각 언어·금지 목록이 s9-design 한 문서에 있고,
   browser-verify가 실브라우저 검증이다). 문구는 `ux-writer`, 구현은 `frontend-developer` 가 같은 스킬 셋을 쓴다.
   리드의 몫은 제약 전달·캡처 검증·커밋이다. 위임 시 **금지 사항을 항상 함께 전달하라**:
   색면 하이라이트 금지 · 카드 좌측 세로 띠 금지 · 무채색 미니멀 금지 — 색은 면이 아니라
   글자·마크·타이포·깊이로 쓴다. (REQ-20260825-057/-082)
8. **조회**: `s9 ls --status/--user` · `s9 search <kw> --body` · `s9 show <id> [--meta]`. 전부 읽지 말고 digest → catalog → 문서 순으로 좁혀라.
9. **live 표시(대시보드 녹색 점멸)**: in-progress REQ의 "실동작" 판정은 **세션의 명시 실행
   등록만** 인정한다 — `last_req`/`active_reqs` 포인터(`s9 status <id> in-progress` 를 세션에서
   실행하면 자동 등록, 떠나는 전이 시 자동 제거)가 있고 그 세션의 스트림이 2분 내 갱신일 때.
   스트림에 id가 언급되거나 문서가 갱신된 것만으로는 live가 아니다(대화·반려 전이 ≠ 작업,
   REQ-20260823-082). 세션만 활발하면 간접(hollow 링)으로 구분 표시된다.
   **병행/위임 REQ의 클레임은 반드시 `s9 last <id> --add`(active_reqs)로 하라** — `last_req`는
   훅이 매 프롬프트마다 최신 REQ로 회전시키므로 위임 클레임이 유실되고, 미클레임으로 보인
   반려 REQ를 워처가 이중 스폰한다 (REQ-20260823-083 실측 엣지).
10. **반려 자동진행(클레임 기반 워처)**: 반려(review→in-progress)는 전이 시점에 스폰하지
   않는다(PENDING). serve의 워처가 30초마다 스캔해, 유예(auto_resume_grace_sec, 기본 30초)를
   넘기고도 어떤 신선한 세션도 클레임(last_req/active_reqs)하지 않은 반려 REQ를 무인 스폰한다 —
   담당 세션이 조용하면 `--resume`(컨텍스트 승계), 활성인데 안 집었으면 새 headless 세션
   (활성 세션 포크 금지 — 컨텍스트는 REQ 문서가 제공). 대화 중인 라이브 세션은 프롬프트 주입으로
   워처보다 먼저 집을 수 있다(빠른 경로). 진행 보장은 사용자 발화와 무관하다 (REQ-20260823-083).
   **백그라운드 에이전트에 위임해 장시간 돌릴 때는 에이전트 transcript 경로를
   `S9_SESSION=<8자> s9 bind agent_transcript_path <output_file>` 로 등록하라** — 그래야
   리드가 조용한 동안에도 위임 작업의 실동작이 live로 잡힌다. (REQ-20260823-080)
11. **개인 선호(사용자별 설정)**: 사용자가 말투·응답 형식·작업 방식 선호를 말하면 리드는 즉시
   `s9 user config <이름> pref_<주제> '<내용>'` 으로 저장하라 (한글 키 허용, 삭제=빈 값).
   audit 훅이 매 턴 그 사용자의 pref_* 를 "◈ 개인 설정"으로 자동 주입하므로, 세션이 바뀌어도
   선호가 유지된다. 하네스 공통 규약(PROTOCOL/스킬)과 분리된 개인 경로다. (REQ-20260824-006)
   **반려는 검증 무효화다**: review→in-progress 전이 시 문서의 체크된 TDD가 자동으로 `- [ ]` 초기화된다
   (REQ-20260824-009) — 재작업은 시나리오를 개정·재검증해 다시 체크하라. 제한권한 무인 워커가 패치
   전달로 끝낼 때는 review가 아니라 blocked('패치 적용 대기') 전이 — 화면이 안 바뀐 review는
   반려 의견이 무시된 것처럼 보인다 (REQ-20260823-078 실측).
12. **review 진입 가드**: request의 review 전이는 TDD 완료(N/N)가 전제다 — 미완료면 do_transition이
   거부한다(사용자 판정만 남은 예외는 `--force` + 사유). 재작업으로 시나리오가 바뀌면 **새 tdd 노트로
   개정하라** — 카운터는 마지막 tdd 노트(현행 세대)만 세므로 구세대가 합산되지 않는다. (REQ-20260824-010)
   blocked에는 반드시 --note로 사유·해제 조건을 남겨라 — 카드(⛔)와 `s9 blocked`, 훅 주입이
   그 note를 그대로 보여준다. '패치 적용 대기(리드)' blocked는 다음 리드 턴이 자동으로 집는다. (REQ-20260824-011)
   오너 config `auto_resume_apply=on`(옵트인, REQ-20260824-012)이면 무인 재작업이 패치를 직접
   적용·검증(tests, s9 shot)하고 review까지 완결한다 — 수정 범위는 web/·vault/·tests/ 한정,
   검증 불가 시 blocked. off(기본)는 제안 전용(패치 note + blocked).
   **승인 메모도 이벤트다** (REQ-20260824-028): review→done의 '승인: <메모>'는 훅이 리드에게 1회
   주입하고(질문이면 답, 후속 함의면 `s9 new request --parent`로 착수 — 검토 승인 = 구현 착수 신호),
   유예 내 미소비면 워처가 무인 후속 작업자를 스폰한다. 반려 루프와 대칭.
13. **goal 의무** (REQ-20260824-030): 요청 접수 시 `--goal '무엇이 충족되면 완료인지 판별 가능한
   한 문장'` 을 반드시 기입하라 — goal 없는 request는 done 전이가 거부된다(--force 예외).
   done의 --note에는 goal 대비 충족 근거를 담는다. original은 원문 보존, goal은 판정 기준이다.
14. **행동 요청 가이드** (REQ-20260824-034, 하네스 공통 — 개인 선호 아님): 사용자에게 행동·협조를
   요청할 때는 반드시 단계별 가이드로 제공하라 — 실행할 명령 전문, 실행 디렉토리, 순서, 예상
   화면/결과, 하지 말아야 할 것을 포함. "~해 주세요" 한 줄로 사용자가 절차를 역추론하게 하지 마라.
15. **대시보드 채팅·수신함** (REQ-20260824-032): 각 클로드 세션의 수신함은
   `state/terminal/inbox-<sid8>.jsonl` 이다. SessionStart 훅이 경로와 함께 arming을 지시하면
   **Monitor 도구로 `tail -f <수신함>` 을 persistent로 arm하라** (도구가 없는 제한 워커는 무시).
   도착하는 JSON 줄의 `kind=chat` 은 대시보드에서 사용자가 보낸 실메시지다 — 사용자 메시지로
   간주해 즉시 처리·응답하라(응답은 평소대로 하면 스트림 뷰로 사용자에게 보인다).
   `kind=event` 는 전이 즉시 통지다 — 반려면 즉시 재작업 착수, 승인 메모면 후속 처리
   (워처는 폴백으로 유지된다). Monitor 타임아웃 알림이 오면 재-arm하라.
   정식 진입은 `s9 code` — 대시보드 보장 + claude 실행 + 바인딩에 entry=code 마커가 붙어
   채팅 자동 대상 선택에서 최우선이 된다. 세션 간 메시징(RC/SendMessage)은 이 경로에 불필요하다.
16. **프로젝트 에이전트** (REQ-20260824-038): 프로젝트 전용 에이전트 정의는
   `projects/<slug>/agents/*.md` (assets 형제 — 에셋은 콘텐츠, 에이전트는 실행 행동 설정).
   SessionStart 훅이 `.claude/agents/<slug>--이름.md` 로 멱등 동기화한다(매니페스트 기반
   정리 — 수동 배치 에이전트 불가침). 네이티브 subagent 목록은 세션 시작 시 로드되므로
   **세션 중 추가한 정의는 다음 세션부터** Agent 도구에 보인다. 즉시 쓰려면 정의 md를
   Read해 범용 에이전트 프롬프트 서두에 역할 규정으로 주입하라(동적 스폰). 무인 워커
   (반려 재작업·승인 후속)는 해당 REQ의 project에 `agents/worker.md` 가 있으면 자동으로
   그 봉투를 프롬프트에 주입한다. 관리: `s9 project agents sync|ls`.
17. **전역 병렬 위임 기본값** (REQ-20260831-037): 모든 프로젝트·하네스의 리드는 작업을
   편집 전에 분류한다. size S 또는 진짜 단일 파일 작업은 조율 비용을 피하려고 직접 처리한다.
   size M/L 이고 서로 독립적인 트랙이 2개 이상이면, 리드는 유용한 통합 작업을 계속하면서
   **최대 3개 subagent(리드 포함 총 4개 실행 트랙)** 를 동시에 시작해야 한다.
   각 subagent에는 겹치지 않는 파일/컴포넌트/증거 범위와 구체 산출물을 주고, claim과 결과를
   권위 있는 REQ 또는 repo work order에 기록한다. subagent는 독립적으로 deploy/production write,
   merge, Jira 변경·종료, Confluence 게시, Teams/ntfy 발송 등 외부 상태를 바꾸지 않는다.
   리드가 결과를 통합하고 충돌을 해결하며 최종 테스트·증거 확인·보고를 소유한다. 도구에
   subagent 기능이 없으면 그 한계를 기록하고 리드가 순차 처리한다 — 가짜 병렬을 주장하지 않는다.
   독립 branch/worktree/PR이 필요하거나 부모 컨텍스트 종료 후에도 살아야 하는 구현 트랙은
   subagent가 아니라 별도 T3 worker session + work order로 라우팅한다. subagent는 bounded
   조사·증거·리뷰·서로 겹치지 않는 단기 구현 트랙에 쓴다.
   **실행 절차**: (1) spawn 전에 REQ/work order에 lead와 각 트랙의 claim·범위·산출물을 적는다.
   (2) Codex는 `spawn_agent(task_name, message)`를 최대 3번 호출한다(고유 role type은 없으므로
   역할·범위는 task_name/message에 쓴다). `list_agents`로 상태를 보고, 추가 지시는 `send_message`/
   `followup_task`, 취소는 `interrupt_agent`, 필요한 마지막 대기만 `wait_agent`를 쓴다.
   Claude는 **한 assistant message에서** 독립 트랙별 `Agent` 호출을 최대 3개 함께 내고
   `description`, `prompt`, `subagent_type`, 보통 `run_in_background:true`를 지정한다. 완료는 자동 통지되므로
   `TaskOutput` polling하지 말고, 조향은 `SendMessage`를 쓴다. (3) 리드는 기다리기만 하지 말고
   통합 준비나 자기 트랙을 계속한다. (4) 결과가 오면 각 요지를
   `s9 note --label subagent --agent <role>` 또는 work-order handoff에 붙이고, 충돌을 해결한 뒤
   합쳐진 트리에서 최종 테스트를 실행한다. "subagent를 써라"라는 문장만 남기고 실제 spawn을
   하지 않은 것은 병렬 실행으로 인정하지 않는다.
18. **전역 credential routing** (REQ-20260831-039): eek-p620의 Bitbucket/Jira REST 인증은
   `/home/jade/.bitbucket_creds` 가 승인된 로컬 소스다. 값을 출력·로그·문서·attachment·commit에
   남기지 말고, 직접 REST가 필요하면 `/home/jade/chief/bin/atlassian-env.sh` 를 source해
   `ATLASSIAN_EMAIL`을 쓰거나 기존 `chief/bin/jira`·release helper를 사용한다(`USER` 충돌 방지).
   project-local 문서는 추가 권한/검증 gate를 더할 수 있지만 jira-cli나 별도 JIRA_EMAIL/JIRA_TOKEN
   등 다른 credential source로 바꾸지 않는다. 승인된 로컬 소스가 없으면 fail closed한다.
   Git fetch/push는 repo의 SSH remote/key를 쓰며 이 토큰 파일을 Git credential로 복사하지 않는다.
   파일은 Louisville/다른 호스트로 복사·전송하지 않는다. remote 작업이 Atlassian API를 필요로
   하면 로컬 Chief 세션에 인계하고, 없음을 우회하지 않는다.
   GCP 일반 작업은 crew의 현재 `default` configuration을 그대로 쓴다. **특별 작업이 명시적으로
   Jade 권한을 요구할 때만** 그 한 명령에 `gcloud --configuration=jade ...`를 붙인다. 절대
   `gcloud config configurations activate jade`를 실행하거나 `active_config`를 바꾸거나
   `CLOUDSDK_ACTIVE_CONFIG_NAME=jade`를 export하지 않는다. `bq`가 명시적으로 Jade 권한을 필요로
   하는 예외는 한 프로세스에만 `CLOUDSDK_ACTIVE_CONFIG_NAME=jade bq ...`를 inline 적용한다.
19. **Codex reversible-artifact fast lane** (REQ-20260901-004): Codex는 size M/L의
   되돌릴 수 있는 PPT/report/draft 산출물을 durable code/PR 및 비가역·외부 상태 변경과 별도로
   분류한다. 이런 산출물은 시작 즉시 서로 겹치지 않는 evidence/source, diagram/plot/table,
   QA 트랙을 `spawn_agent`로 fan-out하고, 리드는 기다리지 않고 primary artifact를 동시에 만든다.
   first useful output의 gate는 파일이 실제로 열리고(open) 핵심 페이지/슬라이드가 render되며
   깨짐·치명적 가독성 문제가 없는지 확인하는 basic open/render validation이다. 이 검증을 통과한
   PPT/report/draft는 독립 QA 완료나 TDD ceremony를 기다리지 않고 먼저 사용자에게 전달한다.
   전달 뒤 같은 active workflow에서 HTML/preview, metadata/source notes, artifact registry,
   Section9 note/status, commit 등 되돌릴 수 있는 bookkeeping을 한 번에 batch한다.
   이 fast lane은 merge/push/deploy, production write·traffic·grade/data/resource 변경,
   destructive action, 외부 메시지·게시, Jira 변경·close 같은 비가역/외부 action의 승인·검증 gate를 줄이지
   않는다. branch/worktree/PR을 소유하는 durable code track은 계속 별도 T3 worker session +
   work order로 보낸다. 제18항의 credential source·host·configuration 경계도 그대로 적용한다.
   이는 **Codex 전용 실행 순서**이며 Claude의 제17항 병렬 호출 의미와 기존 gate 순서를 변경하지 않는다.
20. **Codex local-chief orchestration** (REQ-20260901-007): Chief와 모든 프로젝트 Codex
   session은 대화 기억에 의존하지 않는다. 먼저 `s9 digest`에서 관련 REQ를 좁히고 project context,
   durable docs/work order, project session/work-run 기록과 필요할 때 Jira·PR·release 기록을 읽어
   현재 상태와 ownership을 복원한다. 이어 현재 Codex tree는 `list_agents`로, sibling T3 worker는
   durable session/work-run 기록으로 relevant existing sessions를 찾고, `send_message` 또는 해당
   session 채널로 owner에게 claim·최신 증거·남은 일을 질문하거나 조향한다. 이미 active claim이 있는
   범위는 handoff 없이 다시 spawn하지 않는다. 즉, duplicate ownership을 막고 비중첩 범위만 맡긴다.
   그 뒤 size M/L의 independent tracks가 있으면 available 4-slot Codex tree를 fill immediately 한다:
   **lead + max 3 bounded children**이며, child가 다시 조율하더라도 같은 tree의 남은 슬롯만 사용하고
   session마다 3개씩 곱하지 않는다. bounded 조사·증거·QA·리뷰·단기 비중첩 구현은 child에 맡기고,
   lead keeps integrating: 결과 대기만 하지 않고 primary 구현·통합 준비·documents/work-order 갱신,
   검증과 후속 분해를 계속하며 유용한 lead work가 소진된 뒤에만 대기한다.
   durable branch/PR work처럼 독립 branch/worktree/PR 소유나 부모 종료 뒤의 수명이 필요한 트랙은
   bounded child가 아니라 durable work order가 연결된 sibling T3 worktree session으로 보낸다. 그
   sibling도 시작할 때 같은 durable-source와 ownership 조회를 적용하고 자기 claim 밖을 건드리지 않는다.
   결과는 authoritative documents에 합치고, 별도 actionable item은 lead가 REQ/work order로 만들며
   기존 승인과 credential gate 안에서만 lead-created Jira followups를 생성·갱신한다. child는 Jira,
   merge/push/deploy, production write, 게시·발송 같은 외부 상태를 직접 바꾸지 않고 초안·증거를
   반환한다. 즉, external writes remain lead/authorized이고 최종 통합·검증·보고도 lead 소유다.
   제19항의 reversible-artifact fast lane은 그대로 유지한다. 관련 source와 owner를 확인한 직후
   primary build 및 독립 evidence/diagram/QA를 병렬 시작하며, first useful output을 follow-up Jira,
   bookkeeping 또는 독립 QA 때문에 늦추지 않는다. credential·host·destructive-action gate도 유지한다.
