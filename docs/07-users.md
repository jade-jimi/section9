# 07. User Registry & Session Binding

목표: 요청의 **주체(user)** 를 OS 계정이 아니라 section9에 등록된 사용자로 관리하고,
같은 머신·같은 세션 안에서도 주체를 전환할 수 있게 한다
(예: user1이 토큰 리밋에 걸려 같은 세션을 user2가 이어받는 경우).

## 디렉토리

```
section9/
├── users/                        # 사용자 레지스트리 — 디렉토리명 = 등록된 사용자
│   ├── user1/
│   │   ├── profile.md            # name/display/email/registered/registered_on
│   │   └── config/               # 개인 설정 자유 확장 영역
│   └── user2/...
└── state/sessions/               # machine+session → current user 바인딩
    └── {machine}__{session}.json # {machine, session, user, since, history[], ses_doc}
```

- **등록 확인 = 디렉토리 존재 여부.** `users/<name>/` 이 있으면 등록된 사용자다.
  `ls ~/section9/users` 만으로도 확인 가능.
- `users/<name>/config/` 는 개인별 설정 확장 영역 — 검색 preference, 알림 설정 등
  이후 필요한 무엇이든 이 아래에 추가한다 (스키마 강제 없음).
- 바인딩 `history[]` 는 append-only — 누가 언제 주체를 바꿨는지의 audit trail.
- `state/` 는 **세션 단위 런타임 상태** 전용이다. vault(문서)·users(레지스트리)와
  분리한 이유: 바인딩은 문서가 아니라 가변 상태이고, 세션이 끝나면 가치가
  낮아지는 소모성 데이터라서 정리/보존 정책을 따로 가져갈 수 있어야 한다.
  파일은 그 세션에서 최초의 `s9 user switch` 또는 `s9 log` 시점에 생긴다.
- OS 계정 fallback: 바인딩도 `$S9_USER` 도 없으면 OS 계정명이 주체가 된다
  (미등록이어도 audit이 실패하지 않도록 의도된 동작). 이 경우 hook이
  additionalContext에 경고를 실어 등록/전환을 유도한다.

## machine / session 수집

- **machine**: `$S9_MACHINE` 또는 hostname — CLI가 스스로 수집.
- **session**: Claude Code hook의 stdin JSON `session_id` (앞 8자)에서 수집 —
  auto-audit hook이 프롬프트마다 바인딩 키로 사용하고, additionalContext로
  `S9_SESSION=<id>` 를 LLM에 주입해 이후 모든 s9 호출에 바인딩이 이어진다.

## user 해석 우선순위

`s9 new` / `s9 status` 등 주체가 필요한 모든 명령에 적용:

1. `--user` 플래그 (명시적 1회성 지정)
2. **세션 바인딩** — `state/sessions/{machine}__{$S9_SESSION}.json` 의 user
3. `$S9_USER` 환경변수
4. OS 계정명 (fallback)

바인딩이 환경변수보다 우선인 이유: "현재 사용자 변경"은 세션의 상태이고,
셸에 남아 있는 낡은 export보다 최신 전환이 이겨야 하기 때문.

## 화면 관리 (Users 탭)

대시보드 Users 탭에서 등록·프로필 수정·개인화 설정이 가능하다.
CLI와 동일한 함수(do_user_add/update/config_set)를 호출하는 단일 쓰기 경로이며,
모든 변경은 profile.md Notes에 audit 라인(누가·언제·무엇 [via dashboard])으로 남아
git으로 추적된다. 인가: role 부여/변경은 me가 admin일 때만, config는 본인 또는 admin.

## 명령

```bash
s9 user add <name> [--display D] [--email E]   # 등록 (users/<name>/ 생성)
s9 user list                                    # 등록 목록 (= users/ 디렉토리)
s9 user switch <name> [--session S] [--machine M]  # 현재 사용자 변경 (미등록이면 거부)
s9 user current                                 # 해석 결과 + 출처 표시
```

프롬프트로 전환하는 경로: 사용자가 "지금부터 user2로 진행해" 라고 하면
LLM이 hook 규약 (4)에 따라 `S9_SESSION=<id> s9 user switch user2` 를 실행한다.

## 인수인계 시나리오 재현

```bash
# user1이 세션 s#1에서 작업 중 → user2가 같은 세션을 이어받음
S9_SESSION=s1 s9 user switch user2
# 이후 s#1에서 생성/전이되는 모든 문서의 주체 = user2,
# 전환 이력은 state/sessions/{machine}__s1.json history에 남음
```
