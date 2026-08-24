<!-- section9:begin -->
<!-- section9 protocol — 모든 AI 하네스(Claude/Gemini/Codex/Copilot …)에 공통 주입되는 규약.
     하네스가 자동 훅을 지원하면(예: Claude Code) 1·3·6번은 훅이 대신 수행한다. -->

# section9 작업 규약 (AI agent용)

너의 외부기억은 `~/section9` 이다 (CLI: `~/section9/bin/s9`). 컨텍스트가 아니라 여기에 기록된 것만이 영속한다.

0. **최초 부트스트랩**: `~/.claude/settings.json` 에 section9 훅이 없거나 이 환경이 처음이면
   먼저 `~/section9/bin/s9-install` 을 실행해 훅/스킬/git hook을 설치하라 (Windows: `bin\s9-install.cmd`).
   설치 후 사용자에게 세션 재시작(또는 /hooks 리로드) 시 자동 audit이 시작됨을 알려라.
1. **세션 시작**: `s9 digest` 를 실행해 진행 중 작업을 파악하라. 세션 식별자가 있으면 모든 s9 호출에 `S9_SESSION=<앞8자>` 를 붙여라.
2. **요청 접수**: 사용자의 작업 요청은 반드시 request 문서로 기록하라 —
   `s9 new request --title '20자 이내 명사구' --summary '...' --size S|M|L [--project P] [--parent ID] --body '원문'`.
   단순 질문/감탄은 기록하지 말고 `s9 log "question: ..."` 로 세션 로그만 남겨라.
3. **상태 전이**: 착수 `s9 status <id> in-progress`, 완료 `done`, 확인 대기 `review` — 항상 `--note` 로 근거를 남겨라.
4. **작업 기록**: 구현/결정의 최종 보고를 `s9 note <id> "..." --label response` 로 문서에 남겨라. 터미널 출력은 사라진다.
5. **관계/지식**: 파생 작업은 `s9 link --parent`, 재사용할 지식은 `s9 new knowledge`.
6. **주체**: 사용자가 요청 주체 변경을 원하면 `s9 user switch <이름>` (미등록이면 `s9 user add` 먼저).
7. **조회**: `s9 ls --status/--user` · `s9 search <kw> --body` · `s9 show <id> [--meta]`. 전부 읽지 말고 digest → catalog → 문서 순으로 좁혀라.
<!-- section9:end -->
