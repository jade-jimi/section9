"""bin/s9 의 소스를 구간으로 읽는 시험용 자 — portpool·webasset 처럼 제 이름의 헬퍼.

구조 시험 몇 개가 "이 코드가 저 코드보다 먼저 온다"를 `src[i:i+2200]` 같은
**글자 수 창**으로 재고 있었다. 그 수는 "이 근처"라는 뜻이었을 뿐인데, 같은
구간에 주석 몇 줄만 늘어도(REQ-20260901-020 의 연결 상한이 그랬다) 계약이
멀쩡한 채로 시험만 깨진다 — 한 번의 변경에 서로 다른 파일 둘이 같은 이유로
깨졌다. 재는 것은 **순서**이지 분량이 아니니, 창은 함수 경계로 잡고 그 판정을
한 곳에만 둔다.
"""
import re


def serve_tail(src):
    """cmd_serve 의 기동 구간 — 기동 지문 자리부터 그 함수 끝까지.

    끝은 '들여쓰기 없는 다음 줄'이다(모듈 최상단 정의가 다시 시작하는 자리).
    """
    i = src.index("SERVE_CODE_STAMP = running_code_stamp()")
    m = re.compile(r"^\S", re.M).search(src, i)
    return src[i:m.start() if m else len(src)]
