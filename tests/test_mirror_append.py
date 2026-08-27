"""미러는 늘어난 만큼만 쓴다 (REQ-20260827-039-62x6).

사용자 질문("stream 이 가치가 있나?")을 재다 발견했다. `mirror_transcript()` 가
`shutil.copyfile` 로 **매 턴 transcript 전체를 다시 썼다.** 이 세션은 그때 7.7MB
였으니 한 턴에 7.7MB 를 다시 쓴 것이고, 세션이 자랄수록 턴당 비용이 커진다 —
누적은 대략 제곱으로 는다(오늘 이 세션만 7GB 규모).

미러 자체는 없앨 것이 아니다. Claude Code 가 자기 기록을 지우면 그때 남는 건
미러뿐이고(이미 1건 있었다), 대시보드가 `~/.claude` 배치에 기대지 않게 해준다 —
계정을 바꾸면 그 배치가 움직인다. 고칠 것은 **값을 치르는 방식**이다.

이어 쓰기에는 함정이 하나 있다. transcript 는 **압축(compact)으로 줄거나 다시
쓰일 수 있다.** 그때 뒤에만 이어 붙이면 미러는 원본과 다른 파일이 된다. 그래서
길이만 보지 않고 앞부분이 그대로인지도 본다 — 아니면 전체 복사로 물러난다.

실행: python3 tests/ mirror_append
"""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STOP_HOOK = os.path.join(HERE, "..", "bin", "s9-audit-response")


def _load(name, path):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MirrorAppend(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9mir-")
        self.src = os.path.join(self.root, "sess-1111.jsonl")
        self._old = os.environ.get("S9_ROOT")
        os.environ["S9_ROOT"] = self.root
        self.m = _load("s9_mirror", STOP_HOOK)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("S9_ROOT", None)
        else:
            os.environ["S9_ROOT"] = self._old

    @property
    def dst(self):
        return os.path.join(self.root, "streams", "sess-1111.jsonl")

    def write(self, text):
        with open(self.src, "w", encoding="utf-8") as f:
            f.write(text)

    def read_dst(self):
        with open(self.dst, encoding="utf-8") as f:
            return f.read()

    # N1. 미러가 없으면 전체를 쓴다
    def test_n1_first_copy(self):
        self.write("a\nb\n")
        self.assertEqual(self.m.mirror_transcript(self.src), "full")
        self.assertEqual(self.read_dst(), "a\nb\n")

    # N2. 자란 만큼만 이어 쓴다 — 결과는 전체 복사와 **같아야** 한다
    def test_n2_append_only(self):
        self.write("a\nb\n")
        self.m.mirror_transcript(self.src)
        self.write("a\nb\nc\n")
        self.assertEqual(self.m.mirror_transcript(self.src), "append")
        self.assertEqual(self.read_dst(), "a\nb\nc\n")

    # N3. 늘어난 것이 없으면 건드리지 않는다
    def test_n3_no_growth_no_write(self):
        self.write("a\nb\n")
        self.m.mirror_transcript(self.src)
        before = os.stat(self.dst).st_mtime_ns
        self.assertEqual(self.m.mirror_transcript(self.src), "skip")
        self.assertEqual(os.stat(self.dst).st_mtime_ns, before)

    # B1. 원본이 작아졌으면(압축) 전체 복사로 물러난다
    def test_b1_shrunk_source_full_copy(self):
        self.write("a\nb\nc\n")
        self.m.mirror_transcript(self.src)
        self.write("z\n")
        self.assertEqual(self.m.mirror_transcript(self.src), "full")
        self.assertEqual(self.read_dst(), "z\n")

    # B2. 길이는 같은데 앞부분이 바뀌었으면 전체 복사로 물러난다 —
    #     길이만 보면 되감김을 놓친다
    def test_b2_rewritten_prefix_full_copy(self):
        self.write("aaa\nbbb\n")
        self.m.mirror_transcript(self.src)
        self.write("xxx\nyyy\n")
        self.assertEqual(self.m.mirror_transcript(self.src), "full")
        self.assertEqual(self.read_dst(), "xxx\nyyy\n")

    # F1. 원본이 없으면 조용히 물러난다 — 미러 실패가 응답 캡처를 막으면 안 된다
    def test_f1_missing_source_is_quiet(self):
        self.m.mirror_transcript(os.path.join(self.root, "nope.jsonl"))
        self.assertFalse(os.path.exists(self.dst))

    # R1. 파일명은 원본 basename 그대로 — resume 이 그 이름을 찾는다
    def test_r1_name_preserved(self):
        self.write("a\n")
        self.m.mirror_transcript(self.src)
        self.assertTrue(os.path.exists(self.dst), os.listdir(self.root))


if __name__ == "__main__":
    unittest.main()
