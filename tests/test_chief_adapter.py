"""Chief adapter regression tests (REQ-20260829-001-wfow).

Section9 is the presentation shell. Only named Chief contracts may cross the loopback adapter;
the browser must never receive a generic user-controlled proxy.
"""

import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from portpool import free_port, wait_server


HERE = os.path.dirname(os.path.abspath(__file__))
S9 = os.path.join(HERE, "..", "bin", "s9")


class FakeChief(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls = []

    def log_message(self, *_args):
        pass

    def send_body(self, code, ctype, body):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.calls.append(("GET", self.path, None))
        if self.path == "/api/work":
            return self.send_body(200, "application/json", json.dumps({
                "projects": [{"id": "argon"}], "portfolio": [{"id": "REQ-1"}],
                "releases": [{"id": "argon-live"}], "sources": {"reqs": {"status": "ok"}},
            }))
        if self.path == "/api/now":
            return self.send_body(200, "application/json", json.dumps({"counts": {"working": 2}}))
        if self.path.startswith("/api/work-session/status?"):
            return self.send_body(200, "application/json", json.dumps({"status": "running"}))
        if self.path == "/api/chat/sessions":
            return self.send_body(200, "application/json", json.dumps({"sessions": [{"name": "argon"}]}))
        if self.path.startswith("/api/project-sessions"):
            return self.send_body(200, "application/json", json.dumps({"projects": [{"id": "argon", "sessions": []}]}))
        if self.path.startswith("/api/project-session/messages"):
            return self.send_body(200, "application/json", json.dumps({"thread_id": "t-1", "messages": []}))
        if self.path.startswith("/api/document"):
            return self.send_body(200, "text/html; charset=utf-8", "<h1>Durable document</h1>")
        if self.path.startswith("/api/chat/messages?"):
            return self.send_body(200, "application/json", json.dumps({"name": "argon", "messages": []}))
        if self.path == "/api/chief-chat/messages":
            return self.send_body(200, "application/json", json.dumps({"name": "chief", "messages": []}))
        if self.path.startswith("/refdoc?"):
            return self.send_body(200, "text/html; charset=utf-8", "<h1>Rendered report</h1>")
        self.send_body(404, "application/json", '{"error":"not found"}')

    def do_POST(self):
        size = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(size) or b"{}")
        self.calls.append(("POST", self.path, body))
        if self.path in {"/api/sync", "/api/work-session/start", "/api/work/create", "/api/work/done",
                         "/api/work/investigate", "/api/project-session/start", "/api/project-session/message", "/api/chief-chat/session",
                         "/api/chief-chat/message", "/api/order",
                         "/api/release/autopilot/ensure"}:
            result = {
                "ok": True, "path": self.path, "received": body,
                "test": self.headers.get("X-Chief-Test") == "1",
            }
            if self.path == "/api/project-session/start":
                result.update(thread_id="thread-test-1", title=body.get("title"),
                              state="idle", provider=body.get("engine"))
            if self.path == "/api/project-session/message":
                result.update(sent=True, state="requested")
            return self.send_body(200, "application/json", json.dumps(result))
        self.send_body(404, "application/json", '{"error":"not found"}')


class TestChiefAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake_port = free_port()
        cls.fake = http.server.ThreadingHTTPServer(("127.0.0.1", cls.fake_port), FakeChief)
        cls.fake_thread = threading.Thread(target=cls.fake.serve_forever, daemon=True)
        cls.fake_thread.start()

        cls.tmp = tempfile.mkdtemp(prefix="s9-chief-adapter-")
        cls.env = {**os.environ, "S9_ROOT": cls.tmp, "S9_USER": "tester",
                   "S9_REWORK_WATCH": "off",
                   "S9_CHIEF_API": f"http://127.0.0.1:{cls.fake_port}"}
        cls.env.pop("S9_SESSION", None)
        subprocess.run([S9, "init"], env=cls.env, check=True, capture_output=True, timeout=15)
        cls.port = free_port()
        cls.server = subprocess.Popen(
            [S9, "serve", "--host", "127.0.0.1", "--port", str(cls.port)], env=cls.env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_server(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.fake.shutdown()
        cls.fake.server_close()

    @classmethod
    def call(cls, path, payload=None, test=False):
        url = f"http://127.0.0.1:{cls.port}{path}"
        request = urllib.request.Request(url) if payload is None else urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     **({"X-Chief-Test": "1"} if test else {})})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers.get_content_type(), response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers.get_content_type(), error.read()

    @classmethod
    def new_request(cls, title, body):
        made = subprocess.run(
            [S9, "new", "request", "--title", title, "--goal", "Observable result",
             "--project", "argon", "--body", body], env=cls.env,
            check=True, capture_output=True, text=True, timeout=10)
        return made.stdout.split()[0]

    def test_work_and_now_are_live_chief_reads(self):
        code, ctype, raw = self.call("/api/chief/work")
        self.assertEqual((code, ctype), (200, "application/json"))
        self.assertEqual(json.loads(raw)["portfolio"][0]["id"], "REQ-1")
        code, _ctype, raw = self.call("/api/chief/now")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["counts"]["working"], 2)

    def test_report_preserves_html_and_allowlisted_query(self):
        code, ctype, raw = self.call("/api/chief/report?f=report.md&embed=1&evil=x")
        self.assertEqual((code, ctype), (200, "text/html"))
        self.assertIn(b"Rendered report", raw)
        self.assertIn(("GET", "/refdoc?f=report.md&embed=1", None), FakeChief.calls)

    def test_document_reader_preserves_html_and_only_path_query(self):
        code, ctype, raw = self.call("/api/chief/document?path=%2Ftmp%2FREQ.md&evil=x")
        self.assertEqual((code, ctype), (200, "text/html"))
        self.assertIn(b"Durable document", raw)
        self.assertIn(("GET", "/api/document?path=%2Ftmp%2FREQ.md", None), FakeChief.calls)

    def test_session_start_forwards_exact_json_to_fixed_route(self):
        payload = {"work_id": "REQ-1", "engine": "t3"}
        code, _ctype, raw = self.call("/api/chief/session/start", payload)
        result = json.loads(raw)
        self.assertEqual(code, 200)
        self.assertEqual(result["path"], "/api/work-session/start")
        self.assertEqual(result["received"], payload)

    def test_manual_work_creation_is_a_named_jira_backed_route(self):
        payload = {"project": "argon", "title": "Check freshness", "goal": "Prove the feed is current"}
        code, _ctype, raw = self.call("/api/chief/work/create", payload)
        result = json.loads(raw)
        self.assertEqual(code, 200)
        self.assertEqual(result["path"], "/api/work/create")
        self.assertEqual(result["received"], payload)

    def test_project_chat_and_orders_are_named_routes(self):
        code, _ctype, raw = self.call("/api/chief/chat/sessions")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["sessions"][0]["name"], "argon")
        code, _ctype, raw = self.call("/api/chief/order", {"target": "argon", "text": "check"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["path"], "/api/order")

    def test_project_sessions_are_named_routes(self):
        code, _ctype, raw = self.call("/api/chief/project-sessions?project=argon&refresh=1&evil=x")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["projects"][0]["id"], "argon")
        self.assertIn(("GET", "/api/project-sessions?project=argon&refresh=1", None), FakeChief.calls)
        code, _ctype, raw = self.call(
            "/api/chief/project-session/start", {"project": "argon", "fresh": True})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["path"], "/api/project-session/start")
        code, _ctype, raw = self.call("/api/chief/project-session/messages?thread_id=t-1&evil=x")
        self.assertEqual(code, 200)
        self.assertIn(("GET", "/api/project-session/messages?thread_id=t-1", None), FakeChief.calls)
        code, _ctype, raw = self.call(
            "/api/chief/project-session/message", {"thread_id": "t-1", "text": "continue"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["path"], "/api/project-session/message")

    def test_board_start_uses_linked_jira_work_session_then_transitions(self):
        request_id = self.new_request("Start linked work", "Jira BDA-9999")
        code, _ctype, raw = self.call(
            "/api/work/start", {"id": request_id, "engine": "codex"})
        result = json.loads(raw)

        self.assertEqual(code, 200)
        self.assertEqual(result["status"], "in-progress")
        self.assertEqual(result["engine"], "codex")
        self.assertIn(("POST", "/api/work-session/start", {
            "work_id": "BDA-9999", "engine": "codex", "order": result["order"]}),
            FakeChief.calls)
        shown = subprocess.run([S9, "show", request_id, "--meta"], env=self.env,
                               check=True, capture_output=True, text=True).stdout
        self.assertIn("status: in-progress", shown)

    def test_board_start_without_jira_starts_project_session_with_documents(self):
        request_id = self.new_request("Start native work", "No external ticket yet")
        code, _ctype, raw = self.call(
            "/api/work/start", {"id": request_id, "engine": "t3"})
        result = json.loads(raw)

        self.assertEqual(code, 200)
        self.assertEqual(result["thread_id"], "thread-test-1")
        self.assertIn(("POST", "/api/project-session/start", {
            "project": "argon", "title": "Start native work", "engine": "t3", "fresh": True}),
            FakeChief.calls)
        message_call = next(call for call in reversed(FakeChief.calls)
                            if call[0:2] == ("POST", "/api/project-session/message"))
        self.assertEqual(message_call[2]["thread_id"], "thread-test-1")
        self.assertIn(request_id, message_call[2]["text"])
        self.assertIn("projects/argon/CONTEXT.md", message_call[2]["text"])

    def test_board_start_rejects_unknown_engine_without_transition(self):
        request_id = self.new_request("Reject bad engine", "Remain open")
        code, _ctype, raw = self.call(
            "/api/work/start", {"id": request_id, "engine": "mystery"})

        self.assertEqual(code, 400)
        self.assertIn("t3, codex, or claude", json.loads(raw)["error"])
        shown = subprocess.run([S9, "show", request_id, "--meta"], env=self.env,
                               check=True, capture_output=True, text=True).stdout
        self.assertIn("status: open", shown)

    def test_dry_run_provenance_header_reaches_chief(self):
        code, _ctype, raw = self.call("/api/chief/session/start",
                                      {"work_id": "REQ-1", "engine": "t3"}, test=True)
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(raw)["test"])

    def test_no_generic_chief_proxy_route_exists(self):
        code, _ctype, _raw = self.call("/api/chief/proxy?url=http://example.com")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
