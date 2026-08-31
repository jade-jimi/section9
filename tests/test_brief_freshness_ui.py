"""Chief Brief freshness and attention UI contract (REQ-20260831-003-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class BriefFreshnessUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefSetAttention")
        end = cls.source.index("async function chiefCreateWork", start)
        cls.attention = cls.source[start:end]
        start = cls.source.index("function renderChief")
        end = cls.source.index("async function refreshChief", start)
        cls.brief = cls.source[start:end]

    def test_checked_and_changed_are_separate(self):
        self.assertIn("flow.freshness", self.brief)
        self.assertIn("freshness.changed_at", self.brief)
        self.assertIn("freshness.checked_at", self.brief)
        self.assertIn("Last changed", self.brief)
        self.assertIn("Last checked", self.brief)

    def test_stale_and_unreachable_sources_are_named(self):
        self.assertIn("freshness.sources", self.brief)
        self.assertIn("sourceIssues", self.brief)
        for status in ("unreachable", "failed", "error", "offline"):
            self.assertIn(f'"{status}"', self.brief)
        self.assertIn("Supporting sources:", self.brief)

    def test_attention_actions_use_fixed_contract_and_refresh(self):
        self.assertIn('attention:["api/chief/work/attention","/work/attention"]', self.source)
        self.assertIn('const payload = {work_id:workId,action}', self.attention)
        self.assertIn('payload.hours = 24', self.attention)
        self.assertIn('chiefPost("attention",payload)', self.attention)
        self.assertIn('await refreshChief(true)', self.attention)

    def test_attention_never_completes_work(self):
        self.assertNotIn('chiefPost("complete"', self.attention)
        self.assertNotIn('status:"done"', self.attention)
        self.assertIn("the work remains open", self.attention)

    def test_next_step_stays_primary_and_hero_reason_is_secondary(self):
        primary = 'nextSemantics.next || nextSemantics.goal || nextSemantics.why ||'
        self.assertIn(primary, self.brief)
        self.assertIn("{...flowMatch,...flowNext}", self.brief)
        self.assertIn('class="chief-hero-reason"', self.brief)
        self.assertIn("Why this surfaced", self.brief)
        self.assertLess(self.brief.index(primary), self.brief.index('class="chief-hero-reason"'))

    def test_snooze_state_uses_backend_active_flag_not_date_parse(self):
        self.assertIn("attention.active && snoozedUntil", self.brief)
        self.assertNotIn("Date.parse(snoozedUntil)", self.brief)

    def test_busy_error_focus_and_accessible_labels_exist(self):
        self.assertIn("chiefAttentionState.busy", self.brief)
        self.assertIn('role="alert"', self.brief)
        self.assertIn("Attention was not updated", self.brief)
        self.assertIn("without marking it done", self.brief)
        self.assertIn("requestAnimationFrame", self.attention)

    def test_release_prefers_meaningful_summary_and_timestamps(self):
        release = self.source[self.source.index("function chiefReleaseHTML"):
                              self.source.index("function chiefReportHTML")]
        self.assertIn("row.display_summary || nextActionText", release)
        self.assertIn("row.last_changed_at", release)
        self.assertIn("row.last_checked_at", release)
        self.assertIn("chief-release-timing", release)
        self.assertIn('["building","blocked"].includes(state) && open > 0', release)
        self.assertIn("chiefReleaseOpenCount", self.brief)

    def test_actionable_releases_are_sorted_before_compact_slice(self):
        self.assertIn("const releasePriority = row =>", self.brief)
        self.assertIn('open > 0) return 0', self.brief)
        self.assertIn("releasePriority(a.row) - releasePriority(b.row)", self.brief)
        self.assertLess(self.brief.index("compactReleases.slice(0,3)"),
                        self.brief.index("const releaseNeedsDev"))

    def test_mobile_freshness_wraps_without_alert_surface(self):
        mobile = re.search(r"@media\(max-width:600px\)\{([\s\S]*?)\n\}", self.source)
        self.assertIsNotNone(mobile)
        self.assertIn(".chief-freshness", mobile.group(1))
        freshness = re.search(r"\.chief-freshness\{([^}]*)\}", self.source)
        self.assertIsNotNone(freshness)
        self.assertNotIn("background:", freshness.group(1))
        self.assertNotIn("border-left", freshness.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
