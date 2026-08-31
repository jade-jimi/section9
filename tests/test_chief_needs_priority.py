"""Needs-you priority ordering (REQ-20260831-008-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefNeedsPriority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()

    def test_needs_lane_is_sorted_before_render(self):
        lane_build = self.source.index("rows.forEach(r => { if (!r.release_owned) lanes[chiefLane(r)].push(r); });")
        sort = self.source.index("lanes.needs.sort(chiefNeedsPriorityCompare);", lane_build)
        render = self.source.index("const jiraLanes", sort)
        self.assertLess(lane_build, sort)
        self.assertLess(sort, render)

    def test_priority_rank_covers_operational_and_jira_names(self):
        start = self.source.index("function chiefPriorityRank")
        end = self.source.index("function chiefPriorityLabel", start)
        rank = self.source[start:end]
        for name in ("critical", "highest", "urgent", "high", "medium", "low", "lowest"):
            self.assertIn(name, rank)
        self.assertIn("return 5", rank)

    def test_equal_priority_uses_recent_change_then_stable_id(self):
        start = self.source.index("function chiefNeedsPriorityCompare")
        end = self.source.index("function chiefWorkCard", start)
        comparator = self.source[start:end]
        self.assertIn("chiefChangedTime(b) - chiefChangedTime(a)", comparator)
        self.assertIn("localeCompare", comparator)

    def test_needs_rows_show_the_priority_label(self):
        start = self.source.index("function chiefAccordionRows")
        end = self.source.index("function chiefTrailStep", start)
        rows = self.source[start:end]
        self.assertIn('lane === "needs"', rows)
        self.assertIn("chiefPriorityLabel(row)", rows)
        self.assertIn("chief-row-priority", rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
