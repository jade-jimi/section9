"""옛 코드로 도는 서버가 스스로 드러난다 (REQ-20260827-059-62x6).

실사고 2026-08-27:

    16:59  대시보드 서버 기동
    20:55  질문 큐(REQ-20260827-049)를 고쳐 커밋 — 테스트 6/6 통과
    21:17~ 질문이 계속 유실됨 (QST-025·026 미답)

**채팅→질문 등록은 서버 프로세스 안에서 돈다.** 그래서 디스크의 코드를 고쳐도
16:59에 뜬 서버는 옛 코드고, 큐에 쌓지 않았다. 테스트는 디스크 코드를 직접
실행하니 전부 통과했다 — 고쳤다고 믿을 근거만 늘었다.

대시보드는 이미 배너로 정직하게 알리고 있었다(REQ-20260826-011). 그런데 그건
**사람이 화면을 볼 때만** 보인다. 리드는 화면을 안 본다 — REQ-20260827-046에서
멈춘 작업에 대해 배운 것과 같은 모양이다: **표식만으로는 약하고 주입해야 실제
장치가 된다.**

읽을 수 없으면 낡았다고 단정하지 않는다 — 근거 없는 경고는 곧 무시되고, 한 번
무시되기 시작하면 진짜일 때도 안 읽힌다(code_is_stale 과 같은 규율).

실행: python3 tests/ serve_stale
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
HOOK = os.path.join(HERE, "..", "bin", "s9-audit-prompt")


def _load(name, path):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ServeStale(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9stale-")
        os.makedirs(os.path.join(self.root, "state"), exist_ok=True)
        self.m = _load("s9_stale_" + os.path.basename(self.root), S9)
        self.m.ROOT = self.root

    def stamp(self, d):
        with open(os.path.join(self.root, "state", "serve-code.json"), "w",
                  encoding="utf-8") as f:
            json.dump(d, f)

    # N1. 기동 뒤 코드가 바뀌었으면 말한다
    def test_n1_stale_reported(self):
        self.stamp({"stamp": {"mtime": 1.0, "size": 10}, "pid": os.getpid(),
                    "started": "2026-08-27T16:59:19+09:00"})
        msg = self.m.serve_stale()
        self.assertIn("옛 코드", msg)
        self.assertIn("--restart", msg, "무엇을 하라는지 말하지 않는다")

    # N2. 같은 코드면 조용하다 — 늘 켜져 있는 경고는 안 읽힌다
    def test_n2_fresh_silent(self):
        self.stamp({"stamp": self.m.code_stamp(), "pid": os.getpid()})
        self.assertEqual(self.m.serve_stale(), "")

    # B1. 서버가 안 돌면 낡을 것도 없다
    def test_b1_dead_server_silent(self):
        self.stamp({"stamp": {"mtime": 1.0, "size": 10}, "pid": 999999999})
        self.assertEqual(self.m.serve_stale(), "")

    # B2. 지문 파일이 없거나 깨졌으면 단정하지 않는다
    def test_b2_no_stamp_silent(self):
        self.assertEqual(self.m.serve_stale(), "")
        with open(os.path.join(self.root, "state", "serve-code.json"), "w") as f:
            f.write("{깨진")
        self.assertEqual(self.m.serve_stale(), "")

    # N3. serve 가 기동 시 지문을 남긴다 — 남기지 않으면 물어볼 데가 없다
    def test_n3_serve_writes_stamp(self):
        src = open(S9, encoding="utf-8").read()
        i = src.index("SERVE_CODE_STAMP = code_stamp()")
        self.assertIn("serve-code.json", src[i:i + 800],
                      "serve 가 기동 지문을 디스크에 남기지 않는다")

    # N4. 프롬프트 훅이 매 턴 주입한다 — 배너는 화면을 볼 때만 보인다
    def test_n4_hook_injects(self):
        src = open(HOOK, encoding="utf-8").read()
        self.assertIn('"serve-stale"', src, "훅이 serve-stale 을 부르지 않는다")
        self.assertIn("{stale_serve}", src, "부르기만 하고 주입하지 않는다")


if __name__ == "__main__":
    unittest.main()
