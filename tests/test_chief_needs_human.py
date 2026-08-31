"""Needs-you means explicit Jade attention, not every review state."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefNeedsHuman(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_review_and_blocked_use_backend_human_signal(self):
        start = self.source.index("function chiefLane")
        end = self.source.index("function chiefProjectKey", start)
        lane = self.source[start:end]
        self.assertIn('row && row.needs_human ? "needs" : "progress"', lane)

    def test_release_owned_rows_are_still_removed_before_lane_assignment(self):
        self.assertIn("if (!r.release_owned) lanes[chiefLane(r)].push(r)", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
