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
        css_start = cls.source.index(".chief-meetings-page{")
        css_end = cls.source.index("@media(max-width:900px)", css_start)
        cls.meeting_css = cls.source[css_start:css_end]

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

    def test_automatic_prep_state_is_visible_per_event(self):
        self.assertIn("Auto prep scheduled", self.meetings)
        self.assertIn("Preparing automatically", self.meetings)
        self.assertIn("Prep needs attention", self.meetings)
        self.assertIn("Brief ready · ping sent", self.meetings)
        self.assertIn("Calendar refresh daily", self.meetings)
        self.assertIn("Local prep check every ${automation.poll_minutes || 10}m", self.meetings)

    def test_external_sources_are_read_only(self):
        self.assertIn("Do not modify calendar, Jira, repositories", self.meetings)
        self.assertIn("or Teams", self.meetings)
        self.assertIn("Do not mutate the calendar, Jira, cloud, Confluence or Teams", self.meetings)

    def test_expanded_meeting_shows_only_explicit_related_completed_outcomes(self):
        self.assertIn("related_presentations", self.meetings)
        self.assertIn("Related completed outcomes", self.meetings)
        self.assertIn("Problem", self.meetings)
        self.assertIn("Solution", self.meetings)
        self.assertIn("chiefShort(row.problem", self.meetings)
        self.assertIn("chiefShort(row.solution", self.meetings)

    def test_related_outcome_actions_use_existing_presentation_routes_and_engine(self):
        self.assertIn("chiefPresentationLinks(row,\"Read source\")", self.meetings)
        self.assertIn("Download PowerPoint", self.source)
        self.assertIn("Read presentation", self.source)
        self.assertIn("Read source", self.meetings)
        self.assertIn('data-chief-presentation-action="generate"', self.meetings)
        self.assertIn("data-chief-presentation-engine", self.meetings)
        self.assertIn("Create PPT + HTML with", self.meetings)

    def test_no_explicit_outcomes_is_honest_and_low_noise(self):
        self.assertIn("No completed outcomes are explicitly linked to this meeting yet.", self.meetings)
        self.assertIn("chief-meeting-outcomes-empty", self.meetings)

    def test_meeting_prep_generates_only_explicitly_related_outcome_decks(self):
        self.assertIn("Record the meeting's explicit projects and Jira keys first", self.meetings)
        self.assertIn("never infer from the meeting title", self.meetings)
        self.assertIn("real cited plots when numeric evidence exists", self.meetings)
        self.assertIn("presentations (id/title/project/jira/pptx_path", self.meetings)

    def test_outcome_visual_language_uses_lines_type_depth_and_mobile_reflow(self):
        outcome_css = self.meeting_css[
            self.meeting_css.index(".chief-meeting-outcomes{"):
            self.meeting_css.index(".chief-meeting-side{", self.meeting_css.index(".chief-meeting-outcomes{"))
        ]
        self.assertIn("border-top", outcome_css)
        self.assertIn("box-shadow", outcome_css)
        self.assertNotIn("border-left", outcome_css)
        self.assertNotIn("background:var(", outcome_css)
        self.assertIn(".chief-meeting-outcome{grid-template-columns:1fr", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
