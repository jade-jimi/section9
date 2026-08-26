# 09. Install & Authorization

## 자기완결(self-contained) 원칙

section9 사용에 필요한 **모든 시스템적 규칙·장치·설정은 section9 디렉토리 안에 존재**한다:

| 구성요소 | 리포 내 위치 | 로컬 반영 방법 |
|---|---|---|
| CLI/훅 스크립트 | `bin/` | 그대로 실행 (설치 불필요) |
| Claude Code hook 정의 | `harness/claude/hooks.json` (canonical) | `bin/s9-install` 이 `~/.claude/settings.json` 에 병합 |
| git hooks (rebuild/guard) | `bin/s9-install` 이 생성 | `.git/hooks/` 에 설치 |
| 역할/사용자 설정 | `users/<name>/` | 파일 자체가 동기화됨 |
| 대시보드 | `web/` | `s9 serve` |
| Claude skills (공용) | `harness/claude/skills/<name>/` | installer가 `~/.claude/skills/` 로 symlink |
| Claude agents (공용) | `harness/claude/agents/*.md` | installer가 `~/.claude/agents/` 로 symlink |
| skills/agents (개인) | `users/<name>/skills\|agents/` | installer가 현재 사용자 분만 symlink |

skills/agents symlink 규칙: 대상 경로가 이미 있으면 **section9 안을 가리키는
링크일 때만** 갱신하고, 사용자의 다른 스킬/에이전트는 건드리지 않는다.
새로 링크된 스킬은 다음 Claude 세션부터 로드된다. 공용/커스텀 확장 원칙:
전원이 쓰는 것은 `harness/claude/`, 개인 것은 `users/<name>/` — 저장 위치가 곧 스코프다.
현재 공용 스킬: `s9-design` (완성도 기준 + 대시보드 디자인 시스템 — ux-craft 흡수).

`~/.claude/settings.json` 은 section9 밖이지만, **원본은 항상 `harness/claude/hooks.json`** 이고
로컬 파일은 installer가 만들어내는 파생물이다. installer는 command 경로에
`/section9/bin/` 이 포함된 항목만 section9 소유로 간주해 교체하므로,
사용자의 다른 훅/설정은 절대 건드리지 않는다 (안전한 부분 병합).

## 설치 & 갱신 흐름

```bash
# 최초 (새 머신/계정)
git clone <repo-url> ~/section9
~/section9/bin/s9-install          # 디렉토리 + git hooks + claude hooks 전부
~/section9/bin/s9 user add <이름> [--role admin|member|viewer]

# 이후 갱신
git pull                            # → post-merge hook이 자동으로
                                    #    s9 index rebuild + s9-install --quiet 실행
```

즉 **pull만 하면 로컬 환경(claude hook 포함)이 최신으로 따라온다.**
claude hook 정의가 바뀐 경우 실행 중 세션에는 `/hooks` 리로드 또는 재시작이 필요할 수 있다.

## 역할 기반 인가 (A + B 계층)

역할: `admin`(harness + 문서) / `member`(문서만) / `viewer`(읽기).
`users/<name>/profile.md` 의 `role:` 필드가 저장소이며 `s9 user role <name> [role]` 로 관리.

**A. 로컬 pre-commit guard (`bin/s9-guard`)** — 커밋에 보호 경로
(`bin/ web/ harness/ .github/ .gitignore`)가 포함되면 현재 사용자
($S9_USER > OS 계정)의 role을 확인, admin이 아니면 커밋 거부.
오프라인에서도 동작하는 실수 방지 장치.

**B. GitHub 서버측 (우회 불가능한 최종 게이트)** — `.github/CODEOWNERS` 의
`@OWNER` 를 실제 admin 계정으로 교체하고, main 브랜치에
branch protection(PR 필수 + Code Owners 리뷰 필수)을 설정한다.
이러면 A를 우회해도(로컬은 인가만 있고 인증이 없으므로 S9_USER 위조 가능)
main에는 admin 승인 없이 harness 변경이 들어갈 수 없다.

한계 명시: 인증 없는 로컬 인가는 악의적 사용자를 막지 못한다 — A는
실수 방지·규율·감사용이고, 진짜 강제는 B가 담당한다. 이것이 "간단하지만
확실한" 조합의 근거다.

## 사용자 설정 (users/<name>/config/settings.json)

```bash
s9 user config <name> timezone Asia/Seoul   # 대시보드/스트림 시간 표시 시간대
s9 user config <name>                       # 전체 설정 보기
```

- 시간대 해석: `$S9_TZ` > 서버를 띄운 사용자의 `timezone` 설정 > 시스템 로컬.
- config는 자유 확장 영역 — 이후 검색 preference, 알림 등도 여기에.
