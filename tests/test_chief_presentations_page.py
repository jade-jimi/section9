"""Completed-work Presentations page (REQ-20260831-032-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefPresentationsPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefPresentationInstant")
        end = cls.source.index("function chiefArtifactSize", start)
        cls.presentations = cls.source[start:end]
        css_start = cls.source.index("/* Completed work, shaped into an honest speaking sequence. */")
        css_end = cls.source.index("/* Curated artifact library", css_start)
        cls.presentation_css = cls.source[css_start:css_end]

    def test_presentations_is_a_first_class_chief_page(self):
        self.assertIn('data-chief-nav="presentations"', self.source)
        self.assertIn('"presentations","artifacts"', self.source)
        self.assertIn('chiefDaily === "presentations"', self.source)
        self.assertIn("renderChiefPresentations()", self.source)

    def test_page_consumes_completed_work_and_groups_newest_first(self):
        self.assertIn("chiefData && chiefData.presentations", self.presentations)
        self.assertIn("chiefPresentationInstant(b) - chiefPresentationInstant(a)", self.presentations)
        self.assertIn("const groups = new Map()", self.presentations)
        self.assertIn("newest first", self.presentations)
        self.assertIn("data-chief-presentation-project", self.presentations)
        self.assertIn('chiefPresentationState = "ready"', self.source)
        self.assertIn("+09:00", self.presentations)

    def test_story_keeps_the_speaking_sequence_and_honest_boundary(self):
        labels = ["Problem", "Solution performed", "Result / evidence", "Remaining boundary"]
        offsets = [self.presentations.index(f'["{label}"') for label in labels]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("this does not prove that none remains", self.presentations)
        self.assertIn("esc(value || fallback)", self.presentations)

    def test_ready_requires_complete_narrative_and_readable_artifact(self):
        ready = self.presentations[
            self.presentations.index("function chiefPresentationReady"):
            self.presentations.index("function chiefPresentationMissing")
        ]
        self.assertIn("declaredReady", ready)
        self.assertIn("row.problem && row.solution && row.result && row.remaining", ready)
        self.assertIn("row.report_file || row.source_path", ready)
        self.assertIn("Presentation ready", self.presentations)
        self.assertIn("Needs brief", self.presentations)

    def test_reports_open_in_reader_and_generation_keeps_selected_engine(self):
        self.assertIn("data-chief-report-open", self.presentations)
        self.assertIn("report?f=", self.presentations)
        self.assertIn("document?path=", self.presentations)
        self.assertIn("data-chief-presentation-action", self.presentations)
        self.assertIn("data-chief-presentation-engine", self.presentations)
        self.assertIn('chiefPost("projectSessionStart"', self.presentations)
        self.assertIn('chiefPost("projectSessionMessage"', self.presentations)
        self.assertIn("/home/jade/EE the.thmx", self.presentations)
        self.assertIn('project:"meeting-reports"', self.presentations)
        self.assertIn("/home/jade/section9-chief/projects/meeting-reports/assets/PRESENTATION-", self.presentations)
        self.assertIn("/home/jade/chief/reports/PRESENTATION-", self.presentations)
        self.assertIn("/home/jade/chief/presentations/${key}.json", self.presentations)
        self.assertIn("This is read/report-only", self.presentations)
        self.assertIn('ready ? "Create presentation page"', self.presentations)

    def test_visual_language_uses_marks_lines_depth_and_mobile_reflow(self):
        self.assertIn("chief-presentation-seal", self.presentation_css)
        self.assertIn("border-bottom", self.presentation_css)
        self.assertIn("box-shadow", self.presentation_css)
        self.assertNotIn("border-left", self.presentation_css)
        self.assertIn(".chief-presentation-story{grid-template-columns:1fr", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
