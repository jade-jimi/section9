"""Needs-you verification and human close gate (REQ-20260831-007-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefResolutionAction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefStartResolution")
        end = cls.source.index("async function chiefStartRelease", start)
        cls.resolution = cls.source[start:end]
        drawer_start = cls.source.index("function renderChiefDetail")
        drawer_end = cls.source.index("async function chiefCreateWork", drawer_start)
        cls.drawer = cls.source[drawer_start:drawer_end]

    def test_needs_you_primary_action_starts_resolution(self):
        self.assertIn('nextLane === "needs" ? "Verify & resolve"', self.source)
        self.assertIn('if (action === "needs") { chiefStartResolution(id,title); return; }',
                      self.source)
        self.assertIn("data-chief-resolve=", self.drawer)

    def test_order_returns_one_of_three_bounded_outcomes(self):
        for outcome in ("outcome: close_ready", "outcome: pr_required", "outcome: blocked"):
            self.assertIn(outcome, self.resolution)
        self.assertIn("current cost/usage or billing evidence", self.resolution)
        self.assertIn("whether the production resource is intentionally active", self.resolution)
        self.assertIn("never merge production", self.resolution)

    def test_existing_live_session_is_monitored_not_duplicated(self):
        self.assertIn("session/status?work_id=", self.resolution)
        self.assertIn("already has a live session", self.resolution)
        self.assertIn("chiefPollRun(id,prior.run_id)", self.resolution)

    def test_close_requires_close_ready_req_and_confirmation(self):
        self.assertIn('resolution === "close_ready"', self.drawer)
        self.assertIn('/^REQ-\\d{8}-\\d{2}$/.test', self.source)
        self.assertIn("Complete + close Jira", self.drawer)
        self.assertIn('kind:"confirm"', self.resolution)
        self.assertIn('chiefPost("complete"', self.resolution)
        self.assertIn("do not transition Jira to Done", self.resolution)

    def test_drawer_shows_session_and_report_controls(self):
        self.assertIn("Act on this work", self.drawer)
        self.assertIn("Open verification report", self.drawer)
        self.assertIn("Open T3 Code", self.drawer)
        self.assertIn("loadChiefResolutionRun()", self.drawer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
