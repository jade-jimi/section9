"""대화 기록이 사람별 자리로 간다 (REQ-20260827-078-62x6).

REQ-20260827-047 의 목표는 둘이었다 — 공개 이력에서 걷어내기(끝남)와 **사용자별
보관으로 옮기기**. 이것이 남은 절반이다.

예전엔 모두가 `streams/` 한 곳에 섞였다. 대화 원문은 사람마다 성격이 다른
기록이라(REQ-20260824-022 열람 격리) 섞어 두면 "누구 것을 누가 보는가"를 나중에
가를 수 없다. `.gitignore` 는 `users/*/streams/` 를 이미 막아 두었다.

**파일 이름은 건드리지 않는다.** `s9 resume` 은 미러 이름이 원본 basename 과
100% 일치하는 데 기댄다(DOC-20260823-002). 옮기는 것은 디렉터리뿐이다.

**옛 자리는 계속 읽는다.** 이미 그 자리에 쌓인 기록이 있고, 못 읽게 되면 과거
세션 resume 과 화면이 조용히 비어 버린다 — 조용히 비는 것이 이 저장소의 상습
실패다.

실행: python3 tests/ streams_per_user
"""
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
STOP_HOOK = os.path.join(HERE, "..", "bin", "s9-audit-response")


class StreamsPerUser(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9spu-")
        os.environ["S9_ROOT"] = self.root
        os.environ["S9_MACHINE"] = "boxA"
        os.environ["S9_USER"] = "alice"
        self.env = {**os.environ}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")
        self.cli("user", "add", "bob")
        spec = importlib.util.spec_from_loader(
            "s9_spu", importlib.machinery.SourceFileLoader("s9_spu", S9))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None and r.returncode != expect:
            raise AssertionError(f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def put(self, where, name="aaaa1111-2222.jsonl", body="x\n"):
        os.makedirs(where, exist_ok=True)
        p = os.path.join(where, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return p

    # N1. 자리는 사람마다 다르다
    def test_n1_per_user_dir(self):
        a = self.m.streams_dir("alice")
        b = self.m.streams_dir("bob")
        self.assertNotEqual(a, b)
        self.assertTrue(a.endswith(os.path.join("users", "alice", "streams")))

    # N2. 훅이 그 자리에 쓴다 — 옛 공용 자리가 아니다
    def test_n2_hook_writes_there(self):
        src = os.path.join(self.root, "sess.jsonl")
        with open(src, "w", encoding="utf-8") as f:
            f.write("x\n")
        spec = importlib.util.spec_from_loader(
            "s9_spu_stop",
            importlib.machinery.SourceFileLoader("s9_spu_stop", STOP_HOOK))
        stop = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stop)
        self.assertEqual(stop.mirror_transcript(src), "full")
        self.assertTrue(os.path.isfile(
            os.path.join(self.m.streams_dir("alice"), "sess.jsonl")))
        self.assertFalse(os.path.isfile(
            os.path.join(self.root, "streams", "sess.jsonl")))

    # N3. 파일 이름은 그대로 — resume 이 이름에 기댄다
    def test_n3_basename_kept(self):
        self.put(self.m.streams_dir("alice"))
        got = self.m.streams_glob("aaaa1111*.jsonl", "alice")
        self.assertEqual(os.path.basename(got[0]), "aaaa1111-2222.jsonl")

    # B1. 옛 공용 자리도 계속 읽는다 — 못 읽으면 과거가 조용히 사라진다
    def test_b1_legacy_still_read(self):
        self.put(os.path.join(self.root, "streams"), name="old-1111.jsonl")
        got = [os.path.basename(p) for p in self.m.streams_glob("*.jsonl")]
        self.assertIn("old-1111.jsonl", got)

    # B2. 같은 이름이 양쪽에 있으면 새 자리가 이긴다
    def test_b2_new_wins(self):
        self.put(os.path.join(self.root, "streams"), body="old\n")
        self.put(self.m.streams_dir("alice"), body="new\n")
        got = self.m.streams_glob("aaaa1111*.jsonl", "alice")
        self.assertEqual(len(got), 1)
        self.assertEqual(open(got[0], encoding="utf-8").read(), "new\n")

    # B3. 남의 자리는 훑지 않는다 — 열람 격리가 이 분리의 이유다
    def test_b3_other_user_not_scanned(self):
        self.put(self.m.streams_dir("bob"), name="bobs-9999.jsonl")
        got = [os.path.basename(p) for p in self.m.streams_glob("*.jsonl",
                                                                "alice")]
        self.assertNotIn("bobs-9999.jsonl", got)

    # N4. 꺼 두면 쓸 자리를 주지 않는다 (훅이 이 한 번의 호출로 둘 다 판단한다)
    def test_n4_off_gives_no_dir(self):
        self.assertTrue(self.cli("stream", "--dir").strip())
        self.cli("user", "config", "alice", "stream_mirror", "off")
        self.assertFalse(self.cli("stream", "--dir").strip())

    # R1. 저장소에 올라가지 않는다 — .gitignore 가 이미 막고 있다
    def test_r1_gitignored(self):
        ig = open(os.path.join(HERE, "..", ".gitignore"),
                  encoding="utf-8").read()
        self.assertIn("users/*/streams/", ig)


if __name__ == "__main__":
    unittest.main()
