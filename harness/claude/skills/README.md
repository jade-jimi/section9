# 스킬 소싱 정책 (검색 → 설치 → 자작)

스킬 품질은 즉흥 작성보다 **집단지성으로 다듬어진 것**이 대체로 높다. 따라서
새 역량이 필요할 때 다음 순서를 강제한다 — 자작은 최후 수단이다.

## 1. 검색 (먼저)

등록된 플러그인 마켓플레이스에서 해당 역량의 스킬/플러그인을 찾는다:

```bash
claude plugin marketplace list          # 등록된 마켓플레이스 확인
claude plugin marketplace add <source>  # 신뢰 소스가 있으면 추가 (관리자 승인)
# 마켓플레이스의 스킬/플러그인 카탈로그를 검색
```

- 공식/사내 신뢰 마켓플레이스를 우선한다. 임의 출처는 admin(harness 권한) 승인 후 추가.
- Anthropic 번들 스킬(dataviz, artifact-* 등)이 이미 역량을 커버하면 그것을 쓴다.

## 2. 설치 (있으면)

```bash
claude plugin install <plugin>@<marketplace>
```

- 설치된 스킬은 그대로 사용. section9 에이전트의 필수 스킬 목록에서 이름으로 참조한다.
- 버전/출처를 기록해 재현 가능하게 한다.

## 3. 자작 (없을 때만)

마켓플레이스에 마땅한 것이 없을 때만 `harness/claude/skills/<name>/SKILL.md` 로 작성한다.
이 디렉토리의 현재 스킬들은 **이 환경에 등록된 마켓플레이스가 없어**(위 1단계에서
확인됨) 자작된 것이다. 신뢰 마켓플레이스가 붙고 더 나은 대체 스킬이 확인되면
자작 스킬을 교체하는 것을 우선 검토한다.

## 자작 스킬의 품질 기준

집단지성 스킬과 격차를 줄이기 위해, 자작 스킬은:
- 추상 규칙마다 검증 가능한 기준(수치/조건)과 예시를 붙인다.
- 실제 사고/피드백에서 나온 규칙임을 표시한다(예: 격리 테스트, 병목 시각화).
- 사용하는 에이전트의 실전 결과로 반증되면 개정한다(살아있는 문서).

## 현재 자작 스킬 (13종)

s9-protocol, eng-principles, tdd, review-discipline, security-practice,
data-practice, ops-practice, product-discovery, writing-clarity, research-method,
browser-verify, testing-discipline, s9-design.
(s9-design은 2026-08-25 판정으로 ux-craft를 흡수했다 — 화면·문구 기준은 이 하나뿐이다.)
(매핑은 `../agents/README.md`, 재생성은 `../gen_roster.py`)
