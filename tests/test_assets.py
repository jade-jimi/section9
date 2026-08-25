"""첨부 저장·서빙 테스트 (REQ-20260825-013 승인 → -050 구현, -023 렌더).

첨부는 문서의 일부 — 문서와 같은 월 디렉토리의 assets/<문서ID>/에 두고,
열람은 문서 가시성을 상속하는 /api/asset 라우트로만. rm은 첨부도 함께
tombstone. 격리: S9_ROOT=mktemp.

실행: python3 tests/ assets
"""
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)   # 최소 더미 바이트


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9asset-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")
        cls.port = free_port()
        cls.srv = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)],
            env={**cls.env, "S9_REWORK_WATCH": "off"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(timeout=5)

    @classmethod
    def cli(cls, *argv, expect=0):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=cls.env, timeout=20, stdin=subprocess.DEVNULL)
        if expect is not None and r.returncode != expect:
            raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
        return r.stdout

    def get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def upload_tmp(self, name="shot.png"):
        """업로드 임시본 흉내 — state/terminal/uploads/<계정>/<파일>"""
        d = os.path.join(self.tmp, "state", "terminal", "uploads", "tester")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "wb") as f:
            f.write(PNG)
        return p

    def new_req_with_image(self, title, img):
        return self.cli("new", "request", "--title", title, "--summary", "s",
                        "--size", "S", "--goal", "g",
                        "--body", f"화면 문제다\n[Image: {img}]").split()[0]

    def body_of(self, rid):
        import glob
        p = glob.glob(os.path.join(self.tmp, "vault", "**", rid + ".md"),
                      recursive=True)[0]
        with open(p, encoding="utf-8") as f:
            return f.read()

    # A1. ingest: 업로드 임시본이 문서 옆 assets/<id>/로 이동하고 본문이 상대경로로
    def test_a1_ingest_moves_and_rewrites(self):
        src = self.upload_tmp("a1.png")
        rid = self.new_req_with_image("첨부 이전", src)
        self.cli("assets", "ingest", rid)
        body = self.body_of(rid)
        self.assertIn(f"[Image: assets/{rid}/a1.png]", body)
        self.assertNotIn(src, body)
        self.assertFalse(os.path.exists(src), "임시본이 남았다(이동 아님)")
        import glob
        moved = glob.glob(os.path.join(self.tmp, "vault", "**", "assets", rid,
                                       "a1.png"), recursive=True)
        self.assertEqual(len(moved), 1, "문서 옆 assets/에 없다")

    # A2. 서빙: 문서 가시성 상속 라우트로 바이트가 그대로 내려온다
    def test_a2_serving(self):
        src = self.upload_tmp("a2.png")
        rid = self.new_req_with_image("첨부 서빙", src)
        self.cli("assets", "ingest", rid)
        code, data = self.get(f"/api/asset?doc={rid}&f=a2.png")
        self.assertEqual(code, 200)
        self.assertEqual(data, PNG)
        # 없는 파일·다른 문서·경로 탈출은 404 (존재 여부 누설 금지)
        self.assertEqual(self.get(f"/api/asset?doc={rid}&f=none.png")[0], 404)
        self.assertEqual(
            self.get(f"/api/asset?doc={rid}&f=../../../etc/passwd")[0], 404)
        self.assertEqual(self.get("/api/asset?doc=REQ-9999-999&f=a2.png")[0], 404)

    # A3. rm: 첨부도 문서와 함께 tombstone(.trash)으로 — 고아 파일 없음
    def test_a3_rm_moves_assets(self):
        src = self.upload_tmp("a3.png")
        rid = self.new_req_with_image("첨부 삭제", src)
        self.cli("assets", "ingest", rid)
        self.cli("rm", rid, "--reason", "test")
        import glob
        live = glob.glob(os.path.join(self.tmp, "vault", "requests", "*", "*",
                                      "assets", rid, "*"))
        self.assertEqual(live, [], "삭제 후에도 첨부가 남아 있다")
        trashed = glob.glob(os.path.join(self.tmp, "vault", "**", ".trash",
                                         "assets-" + rid, "a3.png"),
                            recursive=True)
        self.assertEqual(len(trashed), 1, "첨부가 tombstone으로 옮겨지지 않았다")
        self.assertEqual(self.get(f"/api/asset?doc={rid}&f=a3.png")[0], 404)

    # A4. migrate: 기존 문서들의 절대경로 첨부를 일괄 이전
    def test_a4_migrate(self):
        src = self.upload_tmp("a4.png")
        rid = self.new_req_with_image("일괄 이전", src)
        out = self.cli("assets", "migrate")
        self.assertIn(rid, out)
        self.assertIn(f"[Image: assets/{rid}/a4.png]", self.body_of(rid))


class TestInlineRenderContract(unittest.TestCase):
    """문서 뷰 렌더 계약 (REQ-20260825-023): 첨부 HTML은 자리표시자로 보호돼
    linkifyIds가 src/href 속성 안 문서 id를 건드려 태그를 깨뜨리지 않는다."""
    def setUp(self):
        with open(os.path.join(HERE, "..", "web", "index.html"),
                  encoding="utf-8") as f:
            self.html = f.read()

    def test_i1_img_route_used(self):
        self.assertIn("attimg", self.html)
        self.assertIn("/api/asset?doc=", self.html)

    def test_i2_placeholder_protection(self):
        i = self.html.index("const inline = s =>")
        seg = self.html[i:i + 1600]
        self.assertIn("held", seg)          # 자리표시자 보관
        self.assertIn("\\u0000", seg)        # 마커로 치환 후 복원
        self.assertLess(seg.index("hold("), seg.index("linkifyIds("),
                        "첨부 HTML이 linkifyIds보다 먼저 보호돼야 한다")


class TestFileAttachments(unittest.TestCase):
    """일반 파일 첨부 + 첨부 태깅 (REQ-20260825-053)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="s9file-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_MACHINE": "testbox",
                   "S9_USER": "tester"}
        cls.env.pop("S9_SESSION", None)
        cls.cli("init")
        cls.cli("user", "add", "tester")

    @classmethod
    def cli(cls, *argv):
        r = subprocess.run([S9, *argv], capture_output=True, text=True,
                           env=cls.env, timeout=20, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise AssertionError(f"s9 {' '.join(argv)}: {r.stdout}{r.stderr}")
        return r.stdout

    def _tmpfile(self, name, content=b"x"):
        d = os.path.join(self.tmp, "state", "terminal", "uploads", "tester")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "wb") as f:
            f.write(content)
        return p

    def _doc(self, rid):
        import glob
        p = glob.glob(os.path.join(self.tmp, "vault", "**", rid + ".md"),
                      recursive=True)[0]
        with open(p, encoding="utf-8") as f:
            return f.read()

    # F1. [File: ...] 첨부도 문서 옆으로 이전되고 상대경로로 재작성
    def test_f1_generic_file_ingest(self):
        src = self._tmpfile("report.log", b"deploy failed at step 3\n")
        rid = self.cli("new", "request", "--title", "로그 첨부", "--summary", "s",
                       "--size", "S", "--goal", "g",
                       "--body", f"확인 바람\n[File: {src}]").split()[0]
        self.cli("assets", "ingest", rid)
        body = self._doc(rid)
        self.assertIn(f"[File: assets/{rid}/report.log]", body)
        self.assertFalse(os.path.exists(src))

    # F2. 첨부 문서에 attached 태그 + 내용 키워드가 붙는다
    def test_f2_attachment_tags(self):
        src = self._tmpfile("notes.md",
                            "깃 동기화 리모트 커밋 푸시 백업 계획".encode())
        rid = self.cli("new", "request", "--title", "무관한 제목", "--summary", "",
                       "--size", "S", "--goal", "g",
                       "--body", f"[File: {src}]").split()[0]
        self.cli("assets", "ingest", rid)
        meta = self._doc(rid).split("---")[1]
        tagline = [l for l in meta.splitlines() if l.startswith("tags:")][0]
        tags = json.loads(tagline.split(":", 1)[1].strip())
        self.assertIn("attached", tags)
        self.assertIn("sync", tags)        # 첨부 내용에서 파생된 주제 태그

    # F3. 바이너리는 내용 대신 파일명만 키워드로 (읽기 실패로 죽지 않는다)
    def test_f3_binary_safe(self):
        src = self._tmpfile("screenshot-dashboard.png", PNG)
        rid = self.cli("new", "request", "--title", "바이너리", "--summary", "",
                       "--size", "S", "--goal", "g",
                       "--body", f"[Image: {src}]").split()[0]
        self.cli("assets", "ingest", rid)
        meta = self._doc(rid).split("---")[1]
        tags = json.loads([l for l in meta.splitlines()
                           if l.startswith("tags:")][0].split(":", 1)[1].strip())
        self.assertIn("attached", tags)
        self.assertIn("dashboard", tags)   # 파일명 키워드


if __name__ == "__main__":
    unittest.main(verbosity=2)
