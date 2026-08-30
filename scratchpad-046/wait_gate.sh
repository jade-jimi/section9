#!/bin/bash
# 커밋 게이트(FRESH_SEC=900) 숙성 대기 — 스테이지 대상이 전부 15분 넘게
# 조용해지면 한 줄 알리고 끝난다.
cd "$(dirname "$0")/.." || exit 1
while true; do
  n=$(find web tests vault/requests/2026/08/assets/REQ-20260830-046-62x6 \
        -type f -newermt "-905 seconds" 2>/dev/null | wc -l)
  if [ "$n" -eq 0 ]; then
    echo "숙성 완료 — 게이트 통과 가능"
    exit 0
  fi
  sleep 20
done
