# harness/ — AI 도구별 통합 어댑터

section9 코어(bin/s9, vault, index, web)는 하네스 중립이다. 이 디렉토리는
각 AI 코딩 도구를 section9에 연결하는 어댑터를 담는다.

## 지원 수준 매트릭스

| 하네스 | 자동 audit (훅) | 프로토콜 주입 | 어댑터 |
|---|---|---|---|
| Claude Code | ● 완전 자동 (prompt/response/session 훅) | additionalContext | claude/ |
| Gemini CLI | ○ (훅 API 부재 — 도구가 지원하면 추가) | GEMINI.md managed block | gemini/ |
| Codex CLI | ○ | AGENTS.md managed block | codex/ |
| GitHub Copilot | ○ | AGENTS.md (repo) managed block | copilot/ |

- **완전 자동**: 하네스의 훅이 프롬프트 audit·응답 캡처·세션 로그·digest 주입을
  기계적으로 보장한다 (LLM 협조 불필요).
- **프로토콜 모드**: 하네스의 instructions 파일에 `common/PROTOCOL.md` 를
  managed block(`<!-- section9:begin/end -->`)으로 주입 — LLM이 규약에 따라
  s9 CLI를 직접 호출한다. audit 완전성은 LLM 준수도에 의존하며(한계 명시),
  해당 도구가 훅 API를 제공하게 되면 어댑터를 확장해 완전 자동으로 올린다.

## 원칙

- 규약의 원본은 `common/PROTOCOL.md` 하나 — 하네스별 파일은 전부 이것의 주입본.
- 설치/갱신은 `bin/s9-install` 이 수행: 존재하는 하네스(~/.claude, ~/.gemini,
  ~/.codex)를 감지해 해당 어댑터만 적용. 임의 위치는
  `s9-install --agents-md <파일경로>` 로 주입 가능 (예: 프로젝트 AGENTS.md).
- managed block 바깥의 사용자 내용은 절대 건드리지 않는다.
