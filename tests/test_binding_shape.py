"""한 필드가 두 뜻으로 쓰이면 데이터가 상한다 (REQ-20260827-011-62x6).

`agent_transcript_path` 가 한때 **문자열**과 **리스트** 두 뜻으로 쓰였다. 읽는
자리 셋 중 둘은 `isinstance` 로 방어했지만 쓰는 자리 하나가 안 했고, 그 하나로
`list("/tmp/claude-…")` 이 새어 경로가 글자 하나씩 쪼개진 채 저장됐다:

    ["/", "t", "m", "p", "/", "c", "l", "a", "u", "d", "e", …]

**해가 없지 않다.** 그중 `"/"` 는 실제로 존재하는 디렉토리라 활동 경로 판정에서
살아남아 **루트 디렉토리의 mtime 이 세션 활동 신선도로 계산된다.** 그리고
바인딩마다 가짜 경로 100여 개를 매번 `os.path.exists` 로 두드리는데, 그건 채팅
대상 고르기가 메시지마다 도는 경로다(실측 107개 → 정상 1개).

고침의 요점은 되돌리기가 아니라 **자리**다. 방어를 읽는 쪽에 흩어 두면 쓰는 쪽
하나만 새어도 데이터가 상하고, 그 데이터를 읽는 새 코드가 또 당한다. 그래서
바인딩을 읽고 쓰는 **경계 한 곳**에서 모양을 바로잡는다.

이 결함은 이 저장소가 같은 날 세 번 밟은 것과 같은 계열이다 — `data-goto` 가 탭
이름과 상태 전이 두 뜻을 가졌고(REQ-20260826-025), 질문 판정자가 두 입구에 갈려
있었고(REQ-20260826-033), 마크다운 렌더러가 두 벌이었다(REQ-20260827-008).

실행: python3 tests/ binding_shape
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class BindingShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9bshape-")
        os.environ["S9_ROOT"] = cls.tmp
        spec = importlib.util.spec_from_loader(
            "s9bshape", importlib.machinery.SourceFileLoader("s9bshape", S9))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)
        cls.real = os.path.join(cls.tmp, "agent-out.jsonl")
        with open(cls.real, "w") as f:
            f.write("{}\n")

    def test_s1_split_path_is_rejoined(self):
        """S1. 글자로 쪼개진 경로가 다시 하나로 붙는다 (실제로 상해 있던 모양)."""
        b = self.m._norm_binding(
            {"agent_transcript_path": list(self.real)})
        self.assertEqual(b["agent_transcript_path"], [self.real])

    def test_s2_split_path_that_no_longer_exists_is_dropped(self):
        """S2. 붙였는데 그 파일이 없으면 버린다.

        죽은 세션의 임시 파일은 이미 사라졌다. 없는 경로를 남겨 두면 활동
        판정이 매번 헛되이 두드린다.
        """
        b = self.m._norm_binding(
            {"agent_transcript_path": list("/tmp/사라진/파일.output")})
        self.assertEqual(b["agent_transcript_path"], [])

    def test_s3_root_slash_never_survives(self):
        """S3. `"/"` 가 활동 경로로 살아남지 않는다.

        이게 이 결함의 진짜 해다 — 루트는 실제로 존재하므로 걸러지지 않고,
        그 mtime 이 "이 세션은 살아 있다"로 읽힌다.
        """
        b = self.m._norm_binding({"agent_transcript_path": list("/tmp/x")})
        self.assertNotIn("/", b["agent_transcript_path"])

    def test_s4_plain_string_becomes_a_list(self):
        """S4. 옛 문자열 형태도 리스트로 맞춘다 — 두 뜻 중 하나로 모은다."""
        b = self.m._norm_binding({"agent_transcript_path": self.real})
        self.assertEqual(b["agent_transcript_path"], [self.real])

    def test_s5_healthy_list_is_untouched(self):
        """S5. 멀쩡한 목록은 건드리지 않는다 — 고침이 새 손실이 되면 안 된다."""
        good = ["/a/b/one.output", "/a/b/two.output"]
        b = self.m._norm_binding({"agent_transcript_path": list(good)})
        self.assertEqual(b["agent_transcript_path"], good)

    def test_s6_the_boundary_is_read_and_write(self):
        """S6. 정규화가 **읽기와 쓰기 양쪽**에 걸려 있다.

        한쪽만 걸면 다른 쪽으로 상한 데이터가 계속 들어온다. 방어가 경계에
        있어야 한다는 것이 이 문서의 요점이다.
        """
        with open(S9, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("return _norm_binding(json.load(f))", src,
                      "읽기 경계에 정규화가 없다")
        self.assertIn("binding = _norm_binding(binding)", src,
                      "쓰기 경계에 정규화가 없다")

    def test_s7_round_trip_repairs_the_stored_file(self):
        """S7. 상한 바인딩을 읽어 쓰면 파일이 고쳐진다 — 옛 데이터가 스스로
        정리되는 경로가 있어야 사람이 손으로 고치지 않는다."""
        m = self.m
        os.makedirs(m.STATE, exist_ok=True)
        b = {"machine": "testbox", "session": "shapetst",
             "agent_transcript_path": list(self.real)}
        m.write_binding(b)
        again = m.read_binding("testbox", "shapetst")
        self.assertEqual(again["agent_transcript_path"], [self.real])
        with open(m.binding_path("testbox", "shapetst"), encoding="utf-8") as f:
            self.assertEqual(
                json.load(f)["agent_transcript_path"], [self.real])


if __name__ == "__main__":
    unittest.main()
