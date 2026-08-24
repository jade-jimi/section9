# section9

멀티 유저 · 멀티 모델 · 멀티 머신 · 멀티 세션 환경에서 LLM 프롬프트 작업을
**로컬 md 문서**로 audit / 문서화 / 인덱싱하여, LLM의 컨텍스트 메모리 한계를
**외부기억(external memory)** 으로 대체하는 시스템.

> **처음이라면 [사용자 가이드](docs/guide.md)부터** — 설치 절차, 화면별 사용법,
> 터미널(Claude Code) 연동, 프로젝트 운영까지 실제 화면과 함께 단계별로 안내한다.
> (로컬에서는 인터랙티브 버전 [web/guide.html](web/guide.html)을 브라우저로 열 수 있다.)
> 시스템 내부가 궁금하면 [docs/](docs/00-overview.md)의 설계 문서를 보라.


## 핵심 원칙

1. **문서가 single source of truth** — 모든 데이터는 `vault/` 아래 md 파일.
   원격 저장소나 DB 없음. 인덱스는 파생물이며 언제든 재생성 가능.
2. **풍부한 메타데이터** — 모든 문서는 frontmatter에 사용자, 시각, 상태, 관계,
   참조, 태그를 가진다. 인덱싱과 검색은 전부 이 메타데이터에서 나온다.
3. **복합 인덱스** — by-user / by-status / by-project / by-tag / by-date 로
   같은 문서가 여러 축으로 인덱싱된다. 기계용으로는 `index/catalog.jsonl` 하나.
4. **요청은 상태머신** — 모든 request는 상태를 가지며, 정의된 전이만 허용.
   요청이 의도치 않게 방치/누락되는 것을 상태로 감시한다.
5. **적은 토큰으로 조회** — LLM은 파일 전체를 읽기 전에 catalog / 인덱스 /
   `s9 ls` 한 줄 요약으로 먼저 좁힌다.

## 주요 기능

- **자동 audit**: Claude Code 훅이 모든 프롬프트를 REQ 문서로 기록하고(잡담·질문은 제외),
  세션 시작 시 digest·프로젝트 컨텍스트·개인 설정을 자동 주입한다.
- **상태머신 + 품질 가드**: goal 없는 요청은 done 불가, TDD 미완이면 review 진입 불가,
  반려는 검증(체크박스)을 자동 무효화한다.
- **무인 루프**: 반려하면 워처가 유예 후 무인 재작업 세션을 스폰하고(옵트인 시 적용·검증까지),
  승인 메모도 이벤트로 소비되어 후속 작업이 자동 파생된다.
- **대시보드** (Board / Docs / Graph / Audit / Stream / **Terminal** / Settings):
  실행 주체만 켜지는 live 표시, 리뷰 승인·반려 버튼, 프로젝트 멤버 관리.
- **Terminal 탭**: Claude Code CLI 재현 — 대시보드에서 라이브 세션과 직접 대화한다.
  전송은 세션별 수신함 파일 append → 세션의 Monitor(tail)가 즉시 깨어나 처리(세션 간
  메시징·RC 불필요). SSE 푸시(1초 미만), ANSI/글리프 렌더, `/` 팔레트, 이미지 첨부,
  단축키, 에이전트 스트립(이름·실시간 라벨·경과·토큰, ← 로 열람).
- **신원·격리**: 사용자는 선택하는 것이 아니라 서버가 파생(whoami)하며, 문서·스트림
  열람은 프로젝트 멤버십으로 격리된다.
- **프로젝트 단위**: `projects/<slug>/` 에 CONTEXT.md(자동 주입)·assets·**agents**
  (세션 시작 시 네이티브 subagent로 동기화, 무인 워커 봉투 자동 주입).
- **계정·사용량**: 헤더에 로그인된 클로드 계정과 사용량(세션 5h·주간·모델별)을
  60초 주기로 표시 — 계정 전환 즉시 반영.

## 프로젝트 (projects)

요청·문서·화면을 **프로젝트 단위로 묶고 격리**하는 축. 프로젝트는 PRJ 문서(slug 키)로
등록되고, 파일 공간 `projects/<slug>/` 를 가진다.

```bash
s9 project add pay --name "결제 시스템" --user alice    # 등록 (owner=alice) + 공간 스캐폴드
s9 project member pay add bob --role maintainer         # 멤버 (owner/maintainer/contributor/viewer)
s9 project ls / show pay / authz pay bob                # 목록·상세·권한 확인
s9 new request --project pay ...                        # 요청을 프로젝트에 귀속
s9 project agents sync                                  # 프로젝트 에이전트 → .claude/agents 미러
```

```
projects/<slug>/
├── CONTEXT.md   # 프로젝트 컨텍스트 — 이 프로젝트의 요청 접수 시 세션에 자동 주입된다
├── assets/      # 프로젝트 자료(문서·이미지·데이터)
└── agents/      # 프로젝트 전용 에이전트 정의(*.md)
                 #   세션 시작 시 .claude/agents/<slug>--이름.md 로 동기화 → 네이티브 subagent
                 #   agents/worker.md 는 무인 재작업 워커의 프롬프트 봉투로 자동 주입
```

- **역할·인가**: 멤버 변경은 maintainer+, owner 지정·마지막 owner 강등 차단은 owner 전용.
  대시보드의 프로젝트 정보 박스에서 인라인으로 관리한다.
- **가시성 격리**: 문서(`/api/doc`)·스트림(`/api/stream*`) 열람은 소유자·프로젝트 멤버·admin
  으로 제한 — 비멤버에게는 존재 자체가 보이지 않는다(404).
- **화면**: Board/Docs/Graph 모두 프로젝트 필터를 지원한다. 요청 카드·그래프 노드는
  프로젝트로 좁혀 볼 수 있다.

## Quickstart

```bash
export PATH="$HOME/section9/bin:$PATH"   # 또는 alias s9=~/section9/bin/s9

s9 new request --title "로그인 버그 수정" --user user1 --project auth \
   --size M --tag bug --body "재현 절차: ..."
s9 ls --user user1 --status open        # 한 줄 요약 목록
s9 search 로그인 --body                 # 메타데이터 + 본문 검색
s9 show REQ-20260821-001                # 문서 전체 / --meta 는 frontmatter만
s9 status REQ-20260821-001 in-progress  # 상태 전이 (상태머신 검증됨)
s9 link REQ-20260821-002 --parent REQ-20260821-001
s9 index rebuild                        # 인덱스 전체 재생성
s9 serve                                # 웹 대시보드 http://127.0.0.1:9909/
s9 code                                 # 통합 진입: 대시보드 보장 + claude 실행
                                        #   (뒤 인자는 claude로 전달: s9 code --permission-mode acceptEdits)
```

## LLM 사용 프로토콜 (외부기억으로 쓰는 법)

세션이 새로 시작되거나 컴팩션 후에도, 아래 순서를 따르면 컨텍스트 없이 이어서 작업할 수 있다.

1. `s9 ls --user <me> --status in-progress` — 내가 진행 중이던 요청부터 확인.
2. 필요한 문서만 `s9 show <id> --meta` 로 메타데이터 먼저, 그다음 본문.
3. 사용자의 새 프롬프트는 auto-audit hook이 자동으로 request 문서로 기록한다
   (docs/06). LLM은 주입된 문서 ID에 `s9 set` 으로 간결한 제목/요약을 보강하고,
   파생 작업은 `--parent` 로 연결한다. (hook이 없는 환경에서는 `s9 new request` 수동 기록)
4. 작업 진행/완료 시 `s9 status` 로 전이하고 `--note` 로 근거를 남긴다.
5. 얻은 지식/결정사항은 `s9 new knowledge` 로 남겨 다음 세션이 재사용한다.

다른 사용자/머신/세션에서 이어받을 때도 같은 프로토콜 — 문서와 인덱스가
로컬 파일이므로 어떤 세션이든 같은 상태를 본다.

## 디렉토리

```
section9/
├── bin/s9                  # CLI + 웹 서버 (python3 stdlib only)
├── web/index.html          # 대시보드 (Board/Docs/Graph/Audit/Stream/Terminal/Settings, 의존성 없음)
├── harness/                # AI 도구별 어댑터 — claude(완전 자동)/gemini/codex/copilot(프로토콜 모드) + common/PROTOCOL.md
├── docs/                   # 설계 문서 (00~11)
├── tests/                  # stdlib unittest 스위트 (S9_ROOT 격리)
├── projects/<slug>/        # 프로젝트 에셋 공간 — CONTEXT.md + assets/ + agents/  (로컬 인스턴스 데이터)
├── vault/                  # 모든 문서 (source of truth, 로컬 인스턴스 데이터)
│   ├── requests/YYYY/MM/REQ-YYYYMMDD-NNN.md
│   ├── knowledge/YYYY/MM/DOC-YYYYMMDD-NNN.md
│   ├── sessions/YYYY/MM/SES-YYYYMMDD-NNN.md
│   └── attachments/
├── users/<name>/           # 사용자 레지스트리 (profile.md + config/)
├── state/sessions/         # machine+session → current user 바인딩
├── streams/                # Claude Code transcript 미러 (훅이 매 턴 복사, git으로 공유)
└── index/                  # 파생 인덱스 (재생성 가능)
    ├── catalog.jsonl       # 기계용 master index (1 doc = 1 line)
    ├── by-user/  by-status/  by-project/  by-tag/  by-date/
```

> **공개 리포 범위**: 이 리포는 시스템 코드(bin/web/harness/docs/tests)만 담는다.
> `vault/ users/ state/ streams/ projects/ index/` 는 각 설치본의 로컬 데이터로
> `.gitignore` 되어 있으며, `s9 init`(또는 첫 실행)이 빈 구조를 만든다.
> 팀 내 vault 동기화가 필요하면 docs/08-git-sync.md 대로 **별도 private 원격**을 쓴다.

## 설계 문서

- [docs/00-overview.md](docs/00-overview.md) — 목표, 아키텍처, 로드맵
- [docs/01-document-format.md](docs/01-document-format.md) — 문서 포맷, 메타데이터 스펙, ID 체계
- [docs/02-directory-and-index.md](docs/02-directory-and-index.md) — 디렉토리 구조, 인덱스 설계, 동시성
- [docs/03-state-machine.md](docs/03-state-machine.md) — request 상태머신
- [docs/04-search-and-cli.md](docs/04-search-and-cli.md) — 검색 전략, CLI 레퍼런스
- [docs/05-web-dashboard.md](docs/05-web-dashboard.md) — 웹 대시보드 (Board/Docs/Graph)
- [docs/06-auto-audit.md](docs/06-auto-audit.md) — 프롬프트 자동 audit hook
- [docs/07-users.md](docs/07-users.md) — 사용자 레지스트리, 세션 바인딩, 현재 사용자 변경
- [docs/08-git-sync.md](docs/08-git-sync.md) — GitHub 동기화 전략, 새 머신 셋업, 한계
- [docs/09-install-and-authz.md](docs/09-install-and-authz.md) — 자기완결 설치(s9-install), skills/agents 편입, 역할 기반 인가, 사용자 설정
- [docs/10-context-bootstrap.md](docs/10-context-bootstrap.md) — 신규 세션 digest 자동 주입, 예산 설정
- [docs/11-windows.md](docs/11-windows.md) — 순수 Windows(비-WSL) 지원, .cmd 래퍼, 플랫폼 분기
- [harness/README.md](harness/README.md) — 멀티 하네스(Claude/Gemini/Codex/Copilot) 지원 매트릭스와 어댑터 원칙
