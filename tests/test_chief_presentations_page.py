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
        self.assertIn('chiefPresentationState = "all"', self.source)
        self.assertIn("chiefPresentationDeclaredReady(b)", self.presentations)
        self.assertIn("+09:00", self.presentations)

    def test_story_keeps_the_speaking_sequence_and_honest_boundary(self):
        labels = ["Problem", "Solution performed", "Result / evidence", "Remaining boundary"]
        offsets = [self.presentations.index(f'["{label}"') for label in labels]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("this does not prove that none remains", self.presentations)
        self.assertIn("esc(value || fallback)", self.presentations)

    def test_ready_requires_complete_narrative_primary_ppt_and_html_companion(self):
        ready = self.presentations[
            self.presentations.index("function chiefPresentationReady"):
            self.presentations.index("function chiefPresentationMissing")
        ]
        self.assertIn("chiefPresentationDeclaredReady(row)", ready)
        self.assertIn("row.problem && row.solution && row.result && row.remaining", ready)
        self.assertIn("row.pptx_path || row.pptx_file", ready)
        self.assertIn("row.report_file", ready)
        self.assertIn("PPT + HTML ready", self.presentations)
        self.assertIn("Needs brief", self.presentations)

    def test_powerpoint_download_is_primary_while_html_and_source_remain_readable(self):
        links = self.presentations[
            self.presentations.index("function chiefPresentationLinks"):
            self.presentations.index("function chiefPresentationCard")
        ]
        self.assertIn("row.pptx_path || row.pptx_file", links)
        self.assertIn("artifact?path=", links)
        self.assertIn("Download PowerPoint", links)
        self.assertIn("download", links)
        self.assertIn("Read presentation", links)
        self.assertIn("Read source report", links)

    def test_generation_uses_ppt_and_html_labels_and_keeps_selected_engine(self):
        self.assertIn("data-chief-report-open", self.presentations)
        self.assertIn("report?f=", self.presentations)
        self.assertIn("document?path=", self.presentations)
        self.assertIn("data-chief-presentation-action", self.presentations)
        self.assertIn("data-chief-presentation-engine", self.presentations)
        self.assertIn('chiefPost("projectSessionStart"', self.presentations)
        self.assertIn('chiefPost("projectSessionMessage"', self.presentations)
        self.assertIn("/home/jade/EE the.thmx", self.presentations)
        self.assertIn("actual slide master, slide layouts, Open Sans fonts", self.presentations)
        self.assertIn("before/after plots for real numeric comparisons", self.presentations)
        self.assertIn("Never fabricate data", self.presentations)
        self.assertIn("PRESENTATION-${key}.pptx", self.presentations)
        self.assertIn("pptx_path", self.presentations)
        self.assertIn('project:"meeting-reports"', self.presentations)
        self.assertIn("/home/jade/section9-chief/projects/meeting-reports/assets/PRESENTATION-", self.presentations)
        self.assertIn("/home/jade/chief/reports/PRESENTATION-", self.presentations)
        self.assertIn("/home/jade/chief/presentations/${key}.json", self.presentations)
        self.assertIn("This is read/report-only", self.presentations)
        self.assertIn('"Refresh PPT + HTML" : "Create PPT + HTML"', self.presentations)

    def test_page_copy_promises_ee_master_and_only_evidence_backed_visuals(self):
        self.assertIn("PowerPoint-first completed work", self.presentations)
        self.assertIn("supplied EE master", self.presentations)
        self.assertIn("evidence-backed plots", self.presentations)
        self.assertIn("honest diagrams", self.presentations)
        self.assertIn("EE-master PPT decks ready", self.presentations)
        self.assertIn("numeric plots only use cited data", self.presentations)
        self.assertIn('"Deck ready"', self.presentations)
        self.assertIn('"Needs output"', self.presentations)

    def test_visual_language_uses_marks_lines_depth_and_mobile_reflow(self):
        self.assertIn("chief-presentation-seal", self.presentation_css)
        self.assertIn("border-bottom", self.presentation_css)
        self.assertIn("box-shadow", self.presentation_css)
        self.assertNotIn("border-left", self.presentation_css)
        self.assertIn(".chief-presentation-story{grid-template-columns:1fr", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
