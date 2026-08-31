"""Whole-project release control with optional staging (REQ-20260831-014-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefReleasePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefReleasePageRank")
        end = cls.source.index("function chiefTrailStep", start)
        cls.release = cls.source[start:end]

    def test_release_is_a_first_class_chief_page(self):
        self.assertIn('data-chief-nav="release"', self.source)
        self.assertIn('chiefDaily === "release"', self.source)
        self.assertIn("renderChiefReleasePage()", self.source)
        self.assertIn("Move each project", self.release)

    def test_project_card_shows_path_and_included_work(self):
        self.assertIn("chief-release-project", self.release)
        self.assertIn("chief-release-path", self.release)
        self.assertIn("row.included_work", self.release)
        self.assertIn("Included work", self.release)
        self.assertIn("provider PR records", self.release)

    def test_staging_is_conditional_and_actionable(self):
        gate = self.source[self.source.index("function chiefReleaseGate"):
                           self.source.index("function chiefReleaseHTML")]
        self.assertIn('row && row.staging && typeof row.staging === "object"', gate)
        self.assertIn("stagingPassed", gate)
        self.assertIn('"verify_staging"', gate)
        self.assertIn("staging pending", self.release)
        self.assertIn("optional staging proves the exact dev source", self.release)

    def test_whole_project_actions_keep_production_human(self):
        gate = self.source[self.source.index("function chiefReleaseGate"):
                           self.source.index("function chiefReleaseHTML")]
        self.assertIn('"merge_dev","Verify + integrate all to dev"', gate)
        self.assertIn('"prepare_prod","Create dev → production PR"', gate)
        self.assertIn('"verify","Recheck release blockers"', gate)
        self.assertIn('"verify","Refresh release evidence"', gate)
        self.assertIn("Review dev → production PR", self.release)
        self.assertIn("page visits never start an agent or merge production", self.release)
        self.assertIn("Raun Nohavitza + Jayson Son", self.release)

    def test_release_owned_work_leaves_brief_working_lane(self):
        self.assertIn("if (!r.release_owned) lanes[chiefLane(r)].push(r)", self.source)

    def test_release_page_has_explicit_source_refresh(self):
        self.assertIn("Check Jira + PR sources", self.release)
        self.assertIn("data-chief-sync", self.release)

    def test_compact_preview_and_full_page_share_one_gate_function(self):
        compact_start = self.source.index("function chiefReleaseGate")
        page_start = self.source.index("function chiefReleasePageRank")
        compact = self.source[compact_start:page_start]
        self.assertIn("const gate = chiefReleaseGate(row)", compact)
        self.assertIn("const gate = chiefReleaseGate(row)", self.release)
        gate = self.source[self.source.index("function chiefReleaseGate"):
                           self.source.index("function chiefReleaseHTML")]
        choices = gate[gate.index("const runChoices"):]
        self.assertLess(choices.index("featureOpen.length"), choices.index("acceptanceOpen"))
        self.assertIn("data-chief-release-engine", compact)
        self.assertIn("Open Release", compact)


if __name__ == "__main__":
    unittest.main(verbosity=2)
