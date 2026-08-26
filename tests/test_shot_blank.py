"""캡처가 백지를 성공으로 돌려주는가 (REQ-20260827-001-62x6).

화면 검증은 이 저장소의 규율이다(REQ-20260825-065: 화면 REQ 는 상신 전에 직접
캡처해서 본다). 그런데 그 규율을 지키는 도구가 두 화면에서 사람 손을 요구했다.

  - `#terminal` — SSE 상시 연결이 virtual-time 을 소진시키지 않아 캡처가 끝나지
    않는다. `?nosse` 를 붙이면 찍히는데, 도구가 알아서 붙일 수 있는 것을 사람이
    매번 기억해야 했다.
  - `#graph` — 물리 레이아웃이 자리를 잡기 전에는 점이 안 그려진다. 기본 대기로
    찍으면 **백지가 나오는데 종료 코드는 0 이다.**

나쁜 것은 실패가 아니라 **백지가 성공처럼 나오는 것**이다. 실제로 21:56 에 빈
그래프 캡처를 진짜 결함으로 한 번 오인했다. 규율을 지키는 도구가 조용히 거짓을
돌려주면 규율 자체가 무의미해진다 — 이 저장소가 하루 종일 밟은 그 패턴이다.

백지 판정에 **파일 크기를 쓰지 않는다.** 어두운 테마의 정상 캡처가 작게 압축돼
백지와 구분되지 않는다(실측 바이트 균일도: 정상 0.983 vs 백지 0.996 — 거의 붙어
있다). 대신 **한 색으로만 채워진 가로줄의 비율**을 본다.

그리고 그 줄을 셀 때 **PNG 필터를 실제로 되돌린다.** 되돌리지 않고 인코딩된
바이트만 보면 판정이 인코더의 필터 선택에 딸린다 — 같은 그림도 인코더가 바뀌면
다르게 읽힌다. 처음에 그렇게 짰다가 이 파일의 B1 이 잡아냈다(합성 PNG 는 필터를
안 쓰므로 같은 백지가 0.0 으로 읽혔다). 검증이 거짓말하지 않게 만드는 도구가
그런 것에 딸리면 안 된다.

되돌린 뒤 실측: 정상 0.09~0.20 vs 백지 0.80. 문턱 0.75 는 양쪽에 넉넉하다.

실행: python3 tests/ shot_blank
"""
import importlib.machinery
import importlib.util
import os
import struct
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


def _png(path, w, h, rowfn):
    """rowfn(y) -> bytes(w*3) 로 RGB PNG 를 만든다 (필터 0 고정)."""
    raw = b"".join(b"\x00" + rowfn(y) for y in range(h))
    def chunk(t, d):
        return (struct.pack(">I", len(d)) + t + d
                + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw)))
        f.write(chunk(b"IEND", b""))
    return path


class ShotBlank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_loader(
            "s9shot", importlib.machinery.SourceFileLoader("s9shot", S9))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.tmp = tempfile.mkdtemp(prefix="s9shotblank-")

    # ------------------------------------------------------------ 백지 판정
    def test_b1_flat_image_is_blank(self):
        """B1. 한 색으로 덮인 캡처는 '거의 비었다'로 읽힌다."""
        p = _png(os.path.join(self.tmp, "flat.png"), 40, 30,
                 lambda y: b"\x11\x22\x33" * 40)
        self.assertEqual(self.m._png_blank_rows(p), 1.0)

    def test_b2_varied_image_is_not_blank(self):
        """B2. 줄마다 값이 다른 캡처는 백지가 아니다 — 문턱 아래여야 한다."""
        p = _png(os.path.join(self.tmp, "varied.png"), 40, 30,
                 lambda y: bytes((y * 7 + i) % 251 for i in range(120)))
        v = self.m._png_blank_rows(p)
        self.assertLess(v, self.m.SHOT_BLANK_ROWS, v)

    def test_b3_threshold_leaves_room_for_dark_themes(self):
        """B3. 문턱이 어두운 테마의 정상 캡처를 잡아먹지 않는다.

        실측한 최악의 정상 캡처가 0.20, 백지가 0.80 이다. 문턱을 정상 쪽에
        붙여 놓으면 멀쩡한 캡처가 실패로 뒤집혀 도구가 길을 막고, 백지 쪽에
        붙여 놓으면 백지가 새어 나간다.
        """
        self.assertGreater(self.m.SHOT_BLANK_ROWS, 0.70)
        self.assertLess(self.m.SHOT_BLANK_ROWS, 0.82)

    def test_b4_unreadable_file_does_not_block(self):
        """B4. 판정하지 못하면 막지 않는다 — 도구가 길을 막으면 사람이 도구를
        끄고, 그 순간 규율도 함께 꺼진다."""
        p = os.path.join(self.tmp, "junk.png")
        with open(p, "wb") as f:
            f.write(b"not a png at all")
        self.assertIsNone(self.m._png_blank_rows(p))

    # ------------------------------------------------------------ 조건 맞춤
    def test_t1_terminal_gets_nosse(self):
        """T1. 터미널 화면은 SSE 를 끄고 찍는다 — 안 그러면 끝나지 않는다."""
        url, wait, why = self.m._shot_tune("http://x/#terminal", 3000)
        self.assertIn("nosse", url)
        self.assertIn("#terminal", url)
        self.assertTrue(why)

    def test_t2_graph_gets_more_time(self):
        """T2. 그래프 화면은 레이아웃이 자리 잡을 시간을 받는다."""
        url, wait, why = self.m._shot_tune("http://x/#graph", 800)
        self.assertGreaterEqual(wait, 6000)

    def test_t3_other_screens_are_untouched(self):
        """T3. 나머지 화면은 건드리지 않는다 — 조건을 전부에 걸면 캡처가 느려지고
        느린 도구는 안 쓰이게 된다."""
        url, wait, why = self.m._shot_tune("http://x/#docs", 1200)
        self.assertEqual((url, wait, why), ("http://x/#docs", 1200, ""))

    def test_t4_string_wait_is_coerced(self):
        """T4. `--wait` 는 파서가 문자열로 준다 — 여기서 숫자가 돼야 한다.

        실제로 이걸 빠뜨려 `'<' not supported between str and int` 로 죽었다.
        """
        url, wait, why = self.m._shot_tune("http://x/#graph", "800")
        self.assertIsInstance(wait, int)
        self.assertGreaterEqual(wait, 6000)

    def test_t5_existing_query_is_preserved(self):
        """T5. 이미 붙어 있는 질의 문자열을 잃지 않는다 (skin·theme 파라미터)."""
        url, _, _ = self.m._shot_tune("http://x/?skin=calm#terminal", 3000)
        self.assertIn("skin=calm", url)
        self.assertIn("nosse", url)

    def test_t6_blank_capture_exits_nonzero(self):
        """T6. 다시 찍어도 비어 있으면 **실패로 끝낸다**.

        이 한 줄이 이 요청의 전부다 — 백지를 0 으로 돌려주면 '확인했다'가
        거짓이 된다.
        """
        with open(S9, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("sys.exit(5)", src, "백지에 실패 종료 코드가 없다")
        self.assertIn("'확인했다'의 근거로 쓰지 마라", src,
                      "실패 메시지가 무엇을 하지 말라고 말하지 않는다")


if __name__ == "__main__":
    unittest.main()
