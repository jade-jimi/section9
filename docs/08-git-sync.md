# 08. Git Sync (멀티 머신/계정 동기화)

section9는 GitHub 리포로 동기화된다. 로컬 파일 원칙은 유지하면서,
git이 머신 간 전송 계층이 된다.

## track / ignore 결정

| 경로 | git | 이유 |
|---|---|---|
| vault/ | **track** | source of truth. 문서 1개 = 파일 1개라 충돌 면적 최소 |
| streams/ | **track** | transcript 미러 — 이게 있어야 다른 머신/계정에서 스트림 로그 확인 가능 |
| users/ | **track** | 사용자 레지스트리는 전 머신 공유 |
| state/sessions/ | **track** | 바인딩 키에 machine이 포함되어 머신 간 같은 파일을 쓸 일이 없음. 인수인계 시 다른 머신의 현재 주체/진행 REQ를 볼 수 있어 유용 |
| docs/, bin/, web/ | **track** | 설계 문서와 구현 자체 |
| index/ | **ignore** | 파생물. 커밋하면 모든 머신의 모든 쓰기가 catalog.jsonl 한 파일에서 충돌 → pull 후 재생성 |
| .s9.lock | **ignore** | 일시적 lock |

## pull 후 인덱스 재생성 (자동화됨)

`.git/hooks/post-merge` 와 `post-checkout` 이 `s9 index rebuild` 를 실행한다.
**git hook은 리포에 동기화되지 않으므로** 새 머신 셋업 시 수동 설치 필요 (아래).

## 새 머신/계정 셋업 절차

```bash
git clone <repo-url> ~/section9
~/section9/bin/s9-install       # 디렉토리 + git hooks + claude hooks 일괄 (docs/09)
~/section9/bin/s9 user add <내이름>
```

이후에는 `git pull` 만 하면 post-merge hook이 index rebuild와
`s9-install --quiet` 를 자동 실행해 로컬 환경을 최신으로 유지한다.

## 동기화 운영

- 커밋/푸시 주기는 사용자가 결정 (예: 세션 종료 시, 또는 cron).
  전형적 흐름: `git pull --rebase && git add -A && git commit -m "sync" && git push`
- vault 문서와 streams 파일은 append/생성 위주라 rebase 충돌이 드물다.

## 알려진 한계 (설계상 트레이드오프)

1. **ID 충돌**: 두 머신이 오프라인 상태로 같은 날 문서를 만들면
   `REQ-YYYYMMDD-NNN` 시퀀스가 겹칠 수 있다 (같은 파일명, 다른 내용 → git 충돌).
   git이 충돌로 잡아주므로 데이터는 유실되지 않지만 수동 해결(한쪽 시퀀스 rename)이
   필요하다. 잦아지면 ID에 machine을 넣는 스킴(REQ-YYYYMMDD-m1-NNN)으로 전환.
2. **streams 용량**: transcript는 세션당 수 MB까지 자란다. 매 턴 전체 복사라
   git 히스토리가 커질 수 있다 — 오래된 스트림의 아카이브/정리 정책은 추후
   (예: 90일 지난 streams는 별도 브랜치나 git-lfs).
3. **세션 키 충돌**: streams 파일명은 세션 id 앞 8자(hex) — 충돌 확률은
   무시 가능한 수준이지만 0은 아니다.
