"""Chief must default to the Codex provider inside T3 Code (REQ-20260829-003-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefCodexDefault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefStartWork")
        end = cls.source.index("async function chiefManualSync", start)
        cls.control = cls.source[start:end]

    def test_work_sessions_explicitly_choose_codex(self):
        self.assertIn('chiefPost("session",{work_id:id,engine:"codex",order})', self.control)

    def test_release_sessions_explicitly_choose_codex(self):
        self.assertGreaterEqual(self.control.count('engine:"codex"'), 3)

    def test_chief_control_does_not_use_saved_t3_default(self):
        self.assertNotRegex(self.control, re.compile(r'engine\s*:\s*["\']t3["\']'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
