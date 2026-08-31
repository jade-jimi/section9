"""Queued work remains visible and startable in Chief Brief (REQ-20260831-030-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class BriefReadyLane(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        rows_start = cls.source.index("function chiefAccordionRows")
        cls.rows = cls.source[rows_start:cls.source.index("function chiefArtifactSize", rows_start)]
        brief_start = cls.source.index("function renderChief(){")
        cls.brief = cls.source[brief_start:cls.source.index("async function refreshChief", brief_start)]
        create_start = cls.source.index("async function chiefCreateWork")
        cls.creation = cls.source[create_start:cls.source.index("function chiefSessionProject", create_start)]

    def test_ready_is_a_first_class_accordion_lane(self):
        self.assertIn('data-chief-lane-details="ready"', self.brief)
        self.assertIn("<b>Ready</b>", self.brief)
        self.assertIn("jiraLanes.ready.length", self.brief)
        self.assertIn('chiefAccordionRows(jiraLanes.ready,"ready")', self.brief)

    def test_ready_is_not_counted_as_working_or_needs_you(self):
        lane_start = self.source.index("function chiefLane")
        lane = self.source[lane_start:self.source.index("function chiefProjectKey", lane_start)]
        self.assertIn('return "ready"', lane)
        self.assertIn("${lanes.needs.length} need you; ${lanes.progress.length} are moving.", self.brief)

    def test_ready_rows_offer_start_work_through_existing_action_flow(self):
        self.assertIn('lane === "ready" ? "Start work"', self.rows)
        click = self.source[self.source.index('const chiefAct = e.target.closest("[data-chief-action]")'):
                            self.source.index('const chiefRelease =', self.source.index('const chiefAct = e.target.closest("[data-chief-action]")'))]
        self.assertIn('action === "ready" || action === "progress"', click)
        self.assertIn("chiefStartWork(id,title)", click)
        self.assertIn("async function chiefStartWork(id,title,engine=chiefEngine)", self.source)

    def test_newest_ready_work_is_in_the_three_row_window(self):
        self.assertIn("lanes.ready.sort", self.brief)
        self.assertIn("chiefChangedTime(b) - chiefChangedTime(a)", self.brief)
        self.assertIn("expanded ? rows : rows.slice(0,3)", self.rows)

    def test_active_working_session_stays_in_the_three_row_window(self):
        comparator = self.source[self.source.index("function chiefProgressCompare"):
                                 self.source.index("function chiefWorkCard")]
        self.assertIn("chiefRunActive(a && a.session_run)", comparator)
        self.assertIn("Number(bActive) - Number(aActive)", comparator)
        self.assertIn("lanes.progress.sort(chiefProgressCompare)", self.brief)

    def test_add_work_opens_ready_without_expanding_the_backlog(self):
        open_lane = self.creation.index("chiefLaneOpen.ready = true")
        collapse_lane = self.creation.index("chiefLaneExpanded.ready = false")
        refresh = self.creation.index("await refreshChief(true)")
        self.assertLess(open_lane, refresh)
        self.assertLess(collapse_lane, refresh)
        self.assertIn("if (!startSession)", self.creation)

    def test_ready_open_state_is_preserved_like_other_lanes(self):
        self.assertIn("ready:false", self.source)
        self.assertIn("ready:null", self.source)
        self.assertIn("const readyOpen = chiefLaneOpen.ready", self.brief)
        self.assertIn("jiraLanes.ready.length > 0", self.brief)


if __name__ == "__main__":
    unittest.main(verbosity=2)
