"""Permanent saved-detail drawer and optional deep runs (REQ-20260831-005-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefDetailDrawer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function renderChiefDetail")
        end = cls.source.index("async function chiefCreateWork", start)
        cls.drawer = cls.source[start:end]

    def test_hero_has_instant_open_details_action(self):
        self.assertIn("data-chief-open-details", self.source)
        self.assertIn('class="chief-next-title" data-chief-open-details=', self.source)
        open_fn = self.source[self.source.index("function openChiefDetails"):
                              self.source.index("function closeChiefDetails")]
        self.assertIn("renderChiefDetail()", open_fn)
        self.assertIn("loadChiefDeepRuns()", open_fn)
        self.assertNotIn('chiefPost("deepDetailsStart"', open_fn)

    def test_every_brief_lane_row_has_compact_details_action(self):
        rows = self.source[self.source.index("function chiefAccordionRows"):
                           self.source.index("function chiefTrailStep")]
        self.assertIn('class="chief-row-details" data-chief-open-details=', rows)
        self.assertIn('aria-label="Open saved details for', rows)

    def test_selected_card_is_enriched_by_work_id_lookup(self):
        self.assertIn("work/detail?work_id=", self.drawer)
        self.assertIn("data.item", self.drawer)
        self.assertIn("data.flow", self.drawer)
        open_fn = self.source[self.source.index("function openChiefDetails"):
                              self.source.index("function closeChiefDetails")]
        self.assertIn("chiefData && chiefData.portfolio", open_fn)
        self.assertIn("chiefData && chiefData.done", open_fn)
        self.assertIn("renderChiefDetail()", open_fn)
        self.assertIn("loadChiefSelectedDetail()", open_fn)

    def test_all_detail_groups_and_not_recorded_are_rendered(self):
        for label in ("Project", "Jira", "Jira status", "Work status", "Assignee",
                      "Source", "Updated", "Owner", "Goal", "Outcome", "What changed",
                      "Why now", "Impact", "Next checkpoint", "Checklist", "Evidence",
                      "Release", "Relations trail", "Documents", "Freshness"):
            self.assertIn(label, self.drawer)
        self.assertIn('"Not recorded"', self.source)

    def test_deepen_is_explicit_and_uses_fixed_contract(self):
        self.assertIn("data-chief-deepen-form", self.drawer)
        self.assertIn('data-chief-deep-provider="codex"', self.drawer)
        self.assertIn('data-chief-deep-provider="claude"', self.drawer)
        self.assertIn("Terra · medium", self.drawer)
        self.assertIn("Sonnet 5 · medium", self.drawer)
        self.assertNotIn("chief-deep-question", self.drawer)
        self.assertNotIn("chief-deep-repo", self.drawer)
        self.assertNotIn("chief-deep-branch", self.drawer)
        self.assertIn("Generate standard detail report", self.drawer)
        self.assertIn('deepDetailsStart:["api/chief/work/deep-details/start","/work/deep-details/start"]', self.source)
        self.assertIn('chiefPost("deepDetailsStart",{work_id:chiefDetailState.work_id,provider:chiefDetailState.provider})', self.drawer)

    def test_no_implementation_or_completion_implication(self):
        self.assertIn("does not implement, merge, deploy, complete, or close", self.drawer)
        start = self.drawer[self.drawer.index("async function startChiefDeepDetails"):]
        self.assertNotIn('chiefPost("complete"', start)
        self.assertNotIn('status:"done"', start)

    def test_saved_runs_poll_and_link_reports(self):
        self.assertIn("work/deep-details?work_id=", self.drawer)
        self.assertIn("setTimeout(loadChiefDeepRuns,2600)", self.drawer)
        self.assertIn("r.report_ready && r.run_id", self.drawer)
        self.assertIn("session/report?id=", self.drawer)

    def test_drawer_close_escape_focus_and_scroll_contract(self):
        self.assertIn('role="dialog"', self.source)
        self.assertNotIn('id="chief-detail-layer" class="chief-detail-layer" role="dialog" aria-modal', self.source)
        self.assertIn("chiefDetailReturn", self.drawer)
        self.assertIn("back.focus()", self.drawer)
        self.assertIn('e.key === "Escape" && chiefDetailState.open', self.source)
        body = re.search(r"\.chief-detail-body\{([^}]*)\}", self.source)
        self.assertIsNotNone(body)
        self.assertIn("overflow-y:auto", body.group(1))
        self.assertIn('document.body.style.overflow = "hidden"', self.drawer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
