# 10. Context Bootstrap (신규 세션 인덱싱)

## 문제

문서가 방대해질수록 세션 시작 시 전부 읽는 것은 토큰 낭비다. 컨텍스트는 작으므로
**인덱스(catalog)를 다시 요약한 2차 인덱스(digest)** 만 주입한다.

## 계층 구조 (토큰 비용 오름차순)

```
digest      (~1-3KB)  세션 시작 시 자동 주입 — 상황 파악
  ↓ 필요할 때만
catalog     (1줄/문서) s9 ls, 필터
  ↓
frontmatter (s9 show --meta)
  ↓
문서 전문   (s9 show) / 본문 검색 (s9 search --body) / 스트림 (Stream 탭)
```

## s9 digest

```bash
s9 digest [--budget N] [--user U]
```

우선순위에 따라 예산(문자 수) 안에 요약을 만든다:

1. 헤더 — 문서 수, 상태별 카운트 (항상 포함)
2. **내(현재 user) active 요청** — 이어받을 작업. 마지막까지 보존
3. 남의 active 요청 (최대 15)
4. 최근 완료 (최대 8)
5. 최근 knowledge (최대 8)
6. 푸터 — 더 깊이 조회하는 s9 명령 안내 (항상 포함)

예산 초과 시 5→4→3 순으로 3개씩 잘라내고, 극단적 예산에서는 내 active까지 줄인다.

## 자동 주입 (SessionStart hook)

- **신규 세션(startup)과 clear**: `s9-audit-session start` 가 digest를
  additionalContext로 주입 → LLM이 첫 턴부터 진행 중 작업을 안다.
- **resume**: 기존 컨텍스트가 살아 있으므로 주입하지 않는다 (토큰 절약).

## 예산 설정

```bash
s9 user config <이름> digest_budget 4000   # 문자 수 (기본 2500)
```

해석: `--budget` > 서버/훅을 실행한 사용자의 `digest_budget` > 2500.
문서가 수천 건이 되어도 digest 크기는 예산에 고정된다 — 자라는 것은
vault이지 컨텍스트 비용이 아니다.
