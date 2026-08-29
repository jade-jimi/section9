"""Chief session launchers share one explicit three-engine selector (REQ-20260829-006-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefSessionBrainSelector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefStartWork")
        end = cls.source.index("async function chiefManualSync", start)
        cls.control = cls.source[start:end]

    def test_selector_defines_exact_backend_values(self):
        block = self.source[self.source.index("const CHIEF_ENGINES"):self.source.index("const chiefEngineValue")]
        for value in ("t3", "codex", "claude"):
            self.assertRegex(block, rf"\b{value}\s*:")
        self.assertNotRegex(block, r"\b(?:chief|auto|default)\s*:")

    def test_t3_is_safe_default_and_selection_persists(self):
        self.assertIn('return "t3"', self.source)
        self.assertIn('localStorage.getItem("chief-session-engine")', self.source)
        self.assertIn('localStorage.setItem("chief-session-engine",chiefEngine)', self.source)

    def test_work_and_release_send_selected_engine(self):
        self.assertIn('chiefPost("session",{work_id:id,engine,order})', self.control)
        self.assertIn('{release_id:id,engine,explicit_start:true}', self.control)
        self.assertIn('{release_id:id,action,engine}', self.control)
        self.assertNotRegex(self.control, re.compile(r'engine\s*:\s*["\'](?:t3|codex|claude)["\']'))

    def test_picker_is_single_select_and_keyboard_native(self):
        picker = self.source[self.source.index("function chiefEnginePickerHTML"):
                             self.source.index("async function chiefPollRun")]
        self.assertIn('role="group"', picker)
        self.assertIn('aria-pressed=', picker)
        self.assertIn('data-chief-engine=', picker)
        self.assertIn('<button type="button"', picker)

    def test_project_session_label_uses_current_engine(self):
        self.assertIn('data-chief-launch-engine="${esc(chiefEngine)}"', self.source)
        self.assertIn('New ${esc(CHIEF_ENGINES[chiefEngine].label)} session', self.source)

    def test_new_project_conversation_sends_engine_after_durable_work(self):
        self.assertIn('projectSessionStart:["api/chief/project-session/start","/project-session/start"]', self.source)
        self.assertIn('chiefPost("projectSessionStart",{project,title:', self.source)
        self.assertIn(',engine,fresh:true}', self.source)
        self.assertIn('Jira: ${made.jira}', self.source)
        self.assertIn('Chief request: ${made.request_id}', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
