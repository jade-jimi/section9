---
name: browser-verify
description: UI/화면 요구사항을 실제 브라우저로 검증하는 필수 규약. designer, frontend-developer, quality-assurance, test-executor 등 화면 관련 작업에서 반드시 로드. 트리거: UI, 화면, 대시보드, 브라우저, 렌더링, 반응형, 인터랙션.
---

# Browser Verification (하네스 필수)

화면/UI 요구사항의 검증은 **코드 리뷰만으로 끝내지 않는다**. 코드가 맞아 보여도 실제
렌더 결과는 다르다(레이아웃 붕괴, 잘림, 겹침, 폰트/색, 느린 로딩, 죽은 버튼). 반드시
**실제 브라우저를 띄워 사람이 하듯 조작**한 근거를 산출물에 포함한다.

## 필수 동작 (가능한 도구로 실제 수행)

1. **띄우고 본다**: 대상 URL(예: `s9 serve` → http://127.0.0.1:9909)을 실제 브라우저로
   열고 초기 렌더를 스크린샷으로 남긴다.
2. **기다린다**: 비동기 로딩·폴링·애니메이션이 있으면 안정될 때까지 대기한 뒤 다시 확인.
   (live 스트림, 그래프 물리 정착, digest 반영 등)
3. **조작한다**: 클릭/탭(버튼·탭 전환·카드), 입력(검색·폼), 드래그(칸반·그래프 노드),
   **스크롤**(긴 목록·터미널 뷰의 하단 도달, 가로 스크롤 컨테이너)을 실제로 수행하고
   각 상태를 스크린샷으로 비교.
4. **반응형**: 좁은 폭/넓은 폭에서 헤더 wrap, 사이드바, 컬럼이 의도대로인지 확인.
5. **콘솔/네트워크**: JS 에러와 실패한 요청(4xx/5xx)이 없는지 본다.

## 검증 수단 (있는 것을 쓴다 — 순서대로 시도)

- 브라우저 자동화 MCP(Playwright/Chrome 계열)나 그에 준하는 도구가 붙어 있으면 그것으로
  navigate/click/scroll/screenshot을 실제 실행한다.
- **Chrome이 설치된 환경**: Chrome 확장(Claude용 브라우저 확장/DevTools MCP 등)을 통해서도
  동일 절차로 확인이 가능해야 한다. 확장 경로가 있으면 그 경로로도 검증한다.
- built-in `run` 스킬이 앱 구동/스크린샷 경로를 제공하면 활용한다.

## ⚠ WSL 환경 (중요 — 리눅스에 브라우저가 없다고 포기하지 마라)

이 하네스는 WSL(Windows 안의 리눅스)에서 자주 돈다. `which google-chrome`가
비어도 **Windows 쪽에 브라우저가 있다**. 리눅스에 브라우저가 없다는 이유로
"미검증"으로 넘기지 말고 아래를 시도하라:

- **Windows 브라우저로 URL 열기**: 서버는 리눅스에서 `s9 serve` 로 띄우고
  (127.0.0.1은 WSL↔Windows 간 공유됨), Windows 기본 브라우저로 그 주소를 연다 —
  `cmd.exe /c start http://127.0.0.1:9909` 또는 `wslview <url>`(wslu 설치 시)
  또는 `powershell.exe -c "Start-Process <url>"`. 그다음 사용자에게 화면 확인을 요청하거나
  스크린샷을 받는다.
- **Windows의 Chrome을 headless로 구동**: `"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"`
  (또는 Program Files (x86))를 `--headless --screenshot=<경로> --window-size=1440,900 <url>`
  로 호출해 렌더 결과를 PNG로 얻는다. 경로에 공백이 있으니 따옴표 필수.
- **Windows의 Playwright/Chrome MCP**: Windows 측에 설치돼 있으면 그 MCP로 조작한다.
- **간편 헬퍼**: `~/section9/bin/s9 shot <url> [--out PNG] [--size 1440,900]` 가
  WSL이면 Windows Chrome/Edge를 headless로 구동해 스크린샷 PNG 경로를 출력한다.
  이 PNG를 Read 도구로 열어 실제 렌더를 눈으로 확인하라. (브라우저 없으면 비-0 종료 +
  수동 확인 명령 안내 — 그때만 미검증 처리.)
- 위 경로들을 실제로 시도해 본 뒤에도 불가능할 때만 "실브라우저 미검증"을 명시한다 —
  단, WSL에서 Windows 브라우저 경로를 **시도조차 안 하고** 미검증 처리하는 것은 금지.

## 보고

수행한 조작 목록, 각 단계 스크린샷(또는 관찰), 발견한 시각/동작 결함, 사용한 검증 수단,
미검증으로 남긴 부분을 명시한다. "코드상 문제없음"만으로 UI 완료를 선언하지 않는다.
