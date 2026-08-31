"""Human-triggered recommendation session (REQ-20260831-012-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefApplyRecommendation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefApplyRecommendation")
        end = cls.source.index("async function chiefCompleteVerifiedWork", start)
        cls.apply = cls.source[start:end]
        drawer_start = cls.source.index("function renderChiefDetail")
        drawer_end = cls.source.index("async function chiefCreateWork", drawer_start)
        cls.drawer = cls.source[drawer_start:drawer_end]

    def test_drawer_shows_exact_recommendation_and_apply_button(self):
        self.assertIn("Recorded recommendation", self.drawer)
        self.assertIn("data-chief-apply-recommendation", self.drawer)
        self.assertIn("Apply recommendation with", self.drawer)
        self.assertIn("detail.next_checkpoint || next.next || work.next", self.drawer)

    def test_apply_requires_explicit_confirmation_and_selected_engine(self):
        self.assertIn('kind:"confirm"', self.apply)
        self.assertIn("Apply with session", self.apply)
        self.assertIn("chiefEngineValue(engine)", self.apply)
        self.assertIn('chiefPost("session",{work_id:id,engine,order})', self.apply)

    def test_session_revalidates_and_can_refuse_stale_recommendation(self):
        self.assertIn("revalidating that it is still correct", self.apply)
        self.assertIn("perform no mutation", self.apply)
        self.assertIn("outcome: recommendation_changed", self.apply)

    def test_allowed_and_excluded_action_boundaries_are_explicit(self):
        for phrase in ("Jira priority, due date, evidence comment", "Chief hold/snooze/status",
                       "work-order, report and checkpoint/timer updates", "PR and verified integration to dev"):
            self.assertIn(phrase, self.apply)
        for phrase in ("Never perform destructive cloud/data/resource actions",
                       "Never transition Jira to Done", "merge/deploy production",
                       "publish Confluence", "send Teams messages"):
            self.assertIn(phrase, self.apply)
        self.assertNotIn('chiefPost("complete"', self.apply)

    def test_live_session_is_monitored_and_result_is_published(self):
        self.assertIn("already has a live session", self.apply)
        self.assertIn("chiefPollRun(id,prior.run_id)", self.apply)
        self.assertIn("Publish a concise report through the Chief artifact registry", self.apply)
        for outcome in ("outcome: applied", "outcome: recommendation_changed", "outcome: blocked"):
            self.assertIn(outcome, self.apply)


if __name__ == "__main__":
    unittest.main(verbosity=2)
