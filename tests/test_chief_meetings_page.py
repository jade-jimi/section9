"""Meeting preparation page and durable calendar boundary (REQ-20260831-020-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefMeetingsPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefMeetingDatePart")
        end = cls.source.index("function chiefReleasePageRank", start)
        cls.meetings = cls.source[start:end]

    def test_meetings_is_first_class_chief_page(self):
        self.assertIn('data-chief-nav="meetings">Meetings', self.source)
        self.assertIn('"brief","meetings","work"', self.source)
        self.assertIn('chiefDaily === "meetings"', self.source)
        self.assertIn("renderChiefMeetingsPage()", self.source)

    def test_page_keeps_calendar_source_truth_visible(self):
        self.assertIn("Calendar connection required", self.meetings)
        self.assertIn("Calendar source cannot be read", self.meetings)
        self.assertIn("Calendar snapshot is stale", self.meetings)
        self.assertIn("will not call an unreachable source an empty calendar", self.meetings)

    def test_each_meeting_has_history_relations_and_one_click_prep(self):
        self.assertIn("Latest briefing", self.meetings)
        self.assertIn("What to carry forward", self.meetings)
        self.assertIn("Relations", self.meetings)
        self.assertIn("data-chief-meeting-prepare", self.meetings)
        self.assertIn("Prepare with", self.meetings)
        self.assertIn("Open briefing", self.meetings)

    def test_calendar_refresh_is_claude_connector_but_briefing_uses_selected_model(self):
        self.assertIn('engine:"claude",fresh:true', self.meetings)
        self.assertIn('engine:chiefEngine,fresh:true', self.meetings)
        self.assertIn("Refresh calendar · Claude", self.meetings)
        self.assertIn("T3 Code", self.meetings)

    def test_external_sources_are_read_only(self):
        self.assertIn("Do not modify calendar, Jira, repositories, cloud, Confluence or Teams", self.meetings)
        self.assertIn("Do not mutate the calendar, Jira, cloud, Confluence or Teams", self.meetings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
