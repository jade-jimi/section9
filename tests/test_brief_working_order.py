"""Active agent work stays visible in Chief Brief (REQ-20260831-030-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class BriefWorkingOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        helper_start = cls.source.index("function chiefProgressCompare")
        cls.helper = cls.source[helper_start:cls.source.index("function chiefWorkCard", helper_start)]
        brief_start = cls.source.index("function renderChief(){")
        cls.brief = cls.source[brief_start:cls.source.index("async function refreshChief", brief_start)]

    def test_active_backend_session_run_sorts_first(self):
        self.assertIn("chiefRunActive(a && a.session_run)", self.helper)
        self.assertIn("chiefRunActive(b && b.session_run)", self.helper)
        self.assertIn("Number(bActive) - Number(aActive)", self.helper)

    def test_equal_activity_sorts_newest_then_stably(self):
        self.assertIn("chiefChangedTime(b) - chiefChangedTime(a)", self.helper)
        self.assertIn("localeCompare", self.helper)

    def test_working_lane_uses_order_before_three_row_render(self):
        assignment = self.brief.index("lanes.progress.sort(chiefProgressCompare)")
        rendering = self.brief.index('chiefAccordionRows(jiraLanes.progress,"progress")')
        self.assertLess(assignment, rendering)


if __name__ == "__main__":
    unittest.main(verbosity=2)
