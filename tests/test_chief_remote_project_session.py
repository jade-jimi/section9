"""Remote-host T3 project session affordance (REQ-20260831-027-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefRemoteProjectSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefSessionsHTML")
        end = cls.source.index("function chiefProjectKey", start)
        cls.sessions = cls.source[start:end]

    def test_remote_project_session_is_enabled_when_project_selected(self):
        button = self.sessions[self.sessions.index('class="chief-new-session"'):
                               self.sessions.index('</button>', self.sessions.index('class="chief-new-session"'))]
        self.assertNotIn("!chiefProject || remoteHost", button)
        self.assertIn('!chiefProject ?', button)
        self.assertIn("in ${remoteHost}'s own T3 service", button)
        self.assertIn("session${remoteHost ? ` · ${esc(remoteHost)}`", button)


if __name__ == "__main__":
    unittest.main(verbosity=2)
