"""대화 기록 미러를 끄고 켠다 (REQ-20260827-042-62x6).

사용자 판정: 기본은 켠다 · 기본 보관 1주일(설정 변경 가능) · 끄면 화면에서 Stream
탭이 안 보이고 미러도 안 하고 깃헙에도 안 올라간다.

**끄면 전부 내린다**는 결정에는 이유가 있다. 문서별 스트림은 미러가 아니라 **원본을
먼저 보므로**, 미러만 꺼도 그 원본이 있는 머신에서는 계속 열린다. 그러면 스위치가
"껐는데 왜 보이지?"가 되고, 언젠가 Claude Code 가 제 기록을 지우는 날 **말없이
사라진다.** 이 저장소가 계속 싸워 온 실패 모양이다. 그래서 스위치의 뜻을 하나로
만든다 — "나는 대화 기록을 쓰지 않는다".

깃헙 부분은 저절로 성립한다: 끄면 아무것도 안 쓰이므로 올라갈 것이 없다.
조건부 ignore 규칙보다 튼튼하다 — **없어서 안 올라가는 것**이다.

실행: python3 tests/ stream_switch
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")
STOP_HOOK = os.path.join(HERE, "..", "bin", "s9-audit-response")


class env_as:
    """S9_ROOT·S9_USER 를 세운 채로 모듈을 불러 쓰는 구간."""

    def __init__(self, root, user="alice"):
        self.vals = {"S9_ROOT": root, "S9_USER": user}

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.vals}
        os.environ.update(self.vals)
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _load(name, path):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="s9sw-")
        self.env = {**os.environ, "S9_ROOT": self.root, "S9_MACHINE": "testbox",
                    "S9_USER": "alice"}
        self.env.pop("S9_SESSION", None)
        self.cli("init")
        self.cli("user", "add", "alice")

    def cli(self, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=self.env, timeout=30)
        if expect is not None:
            self.assertEqual(r.returncode, expect,
                             f"s9 {' '.join(argv)}\n{r.stdout}{r.stderr}")
        return r.stdout + r.stderr

    def set_cfg(self, **kw):
        d = os.path.join(self.root, "users", "alice", "config")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "settings.json")
        cur = {}
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                cur = json.load(f)
        cur.update(kw)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cur, f)

    def mirror(self, name, age_days=0, body="a\n"):
        d = os.path.join(self.root, "streams")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name + ".jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        if age_days:
            t = time.time() - age_days * 86400
            os.utime(p, (t, t))
        return p


class MirrorSwitch(Base):
    """N1·N2·R2 — 미러를 쓰는가."""

    def drive(self):
        src = os.path.join(self.root, "sess-2222.jsonl")
        with open(src, "w", encoding="utf-8") as f:
            f.write("x\n")
        with env_as(self.root):
            m = _load("s9_sw_stop", STOP_HOOK)
            return m.mirror_transcript(src)

    # N1. 설정이 없으면 켜진 것 — 지금 동작 그대로
    def test_n1_default_on(self):
        self.assertEqual(self.drive(), "full")
        self.assertTrue(os.path.exists(
            os.path.join(self.root, "streams", "sess-2222.jsonl")))

    # N2. 꺼 두면 쓰지 않는다
    def test_n2_off_writes_nothing(self):
        self.set_cfg(stream_mirror="off")
        self.assertEqual(self.drive(), "off")
        self.assertFalse(os.path.exists(
            os.path.join(self.root, "streams", "sess-2222.jsonl")))

    # R2. 설정이 깨져 있어도 켜진 것으로 본다 — 기록을 남기는 쪽이 안전하다
    def test_r2_broken_config_is_on(self):
        d = os.path.join(self.root, "users", "alice", "config")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "settings.json"), "w") as f:
            f.write("{ not json")
        self.assertEqual(self.drive(), "full")


class Retention(Base):
    """N3·B1·B2·B3 — 보관 기간."""

    def prune(self):
        # 모듈 상수(ROOT·USERS·STATE·STREAMS)는 **import 시점의 S9_ROOT** 로
        # 정해진다 — 손으로 몇 개만 덮으면 나머지가 실 리포를 가리켜, 테스트가
        # 통과해도 아무것도 지키지 못한다. 그래서 환경을 세운 뒤 불러온다.
        with env_as(self.root):
            m = _load("s9_sw_mod_" + str(id(self)), S9)
            return m.prune_streams()

    # N3. 기본 7일 — 지난 것은 정리, 최근 것은 남는다
    def test_n3_default_seven_days(self):
        self.mirror("aaaa1111", age_days=9)
        self.mirror("bbbb2222", age_days=2)
        self.prune()
        s = os.path.join(self.root, "streams")
        self.assertFalse(os.path.exists(os.path.join(s, "aaaa1111.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(s, "bbbb2222.jsonl")))

    # B1. 진행 중 REQ 가 붙들고 있는 세션은 지나도 안 지운다
    def test_b1_active_session_kept(self):
        sid = "cccc3333"
        self.mirror(sid, age_days=30)
        rid = self.cli("new", "request", "--title", "t", "--summary", "s",
                       "--goal", "g", "--size", "S", "--user", "alice",
                       "--body", "x").split()[0]
        env = {**self.env, "S9_SESSION": sid}
        subprocess.run([S9, "status", rid, "in-progress", "--note", "t"],
                       capture_output=True, env=env, timeout=20)
        self.prune()
        self.assertTrue(os.path.exists(
            os.path.join(self.root, "streams", sid + ".jsonl")),
            "진행 중인 세션의 기록이 지워졌다")

    # B2. 0 이하이면 무제한 보관 — 아무것도 안 지운다
    def test_b2_zero_means_forever(self):
        self.set_cfg(stream_keep_days=0)
        self.mirror("dddd4444", age_days=90)
        self.prune()
        self.assertTrue(os.path.exists(
            os.path.join(self.root, "streams", "dddd4444.jsonl")))

    # B3. 꺼도 이미 있던 미러는 지우지 않는다 — 끄는 것과 지우는 것은 다른 결정이다
    def test_b3_off_does_not_delete(self):
        self.set_cfg(stream_mirror="off", stream_keep_days=0)
        self.mirror("eeee5555", age_days=1)
        self.prune()
        self.assertTrue(os.path.exists(
            os.path.join(self.root, "streams", "eeee5555.jsonl")))


class Surface(Base):
    """N4·F1 — 사람에게 보이는 자리."""

    # N4. `s9 stream` 이 지금 상태를 말한다
    def test_n4_status_command(self):
        self.mirror("ffff6666")
        out = self.cli("stream")
        self.assertIn("켜짐", out)
        self.assertIn("7", out)          # 보관일
        self.set_cfg(stream_mirror="off")
        self.assertIn("꺼짐", self.cli("stream"))

    # F1. 꺼져 있으면 resume 이 거부하고 이유를 말한다 — 조용히 실패하지 않는다
    def test_f1_resume_refuses_with_reason(self):
        self.set_cfg(stream_mirror="off")
        self.mirror("aaaa1111-2222-3333-4444-555555555555")
        out = self.cli("resume", "aaaa1111", "--yes", expect=1)
        self.assertIn("꺼져", out, out)


if __name__ == "__main__":
    unittest.main()
