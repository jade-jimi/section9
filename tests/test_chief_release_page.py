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
        self.assertIn('row.staging && typeof row.staging === "object"', self.release)
        self.assertIn("stagingPassed", self.release)
        self.assertIn('"verify_staging"', self.release)
        self.assertIn("staging pending", self.release)
        self.assertIn("optional staging proves the exact dev source", self.release)

    def test_whole_project_actions_keep_production_human(self):
        self.assertIn('"merge_dev","Verify + integrate all to dev"', self.release)
        self.assertIn('"prepare_prod","Create dev → production PR"', self.release)
        self.assertIn('"verify","Recheck release blockers"', self.release)
        self.assertIn('"verify","Refresh release evidence"', self.release)
        self.assertIn("Review dev → production PR", self.release)
        self.assertIn("page visits never start an agent or merge production", self.release)
        self.assertIn("Raun Nohavitza + Jayson Son", self.release)

    def test_release_owned_work_leaves_brief_working_lane(self):
        self.assertIn("if (!r.release_owned) lanes[chiefLane(r)].push(r)", self.source)

    def test_release_page_has_explicit_source_refresh(self):
        self.assertIn("Check Jira + PR sources", self.release)
        self.assertIn("data-chief-sync", self.release)


if __name__ == "__main__":
    unittest.main(verbosity=2)
