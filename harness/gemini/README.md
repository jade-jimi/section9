# Gemini CLI 어댑터 (프로토콜 모드)
- s9-install이 ~/.gemini 존재 시 ~/.gemini/GEMINI.md 에 common/PROTOCOL.md 를
  managed block으로 주입한다 (전역 컨텍스트로 모든 세션에 로드됨).
- Gemini CLI가 훅/이벤트 API를 제공하게 되면 여기에 스크립트를 추가해
  Claude 수준의 완전 자동 audit으로 승격한다.
