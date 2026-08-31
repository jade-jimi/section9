"""Expandable Chief Brief lane contract (REQ-20260831-004-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class BriefLaneExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefAccordionRows")
        end = cls.source.index("function chiefTrailStep", start)
        cls.rows = cls.source[start:end]

    def test_default_is_three_and_expanded_is_all(self):
        self.assertIn("const expanded = Boolean(chiefLaneExpanded[lane])", self.rows)
        self.assertIn("expanded ? rows : rows.slice(0,3)", self.rows)
        self.assertIn("rows.length - 3", self.rows)

    def test_toggle_labels_and_accessibility(self):
        self.assertIn("Show remaining ${hidden}", self.rows)
        self.assertIn("Show less", self.rows)
        self.assertIn('aria-expanded="${expanded}"', self.rows)
        self.assertIn('aria-controls="${listId}"', self.rows)

    def test_no_toggle_for_three_or_fewer(self):
        self.assertRegex(self.rows, r"\$\{hidden \? `<button[\s\S]*?` : \"\"\}")

    def test_state_is_in_memory_per_lane(self):
        self.assertEqual(self.source.count("let chiefLaneExpanded ="), 1)
        state = self.source[self.source.index("let chiefLaneExpanded ="):
                            self.source.index("const CHIEF_ENGINES")]
        for lane in ("needs", "ready", "progress", "done"):
            self.assertIn(f"{lane}:false", state)
        self.assertNotIn("localStorage", state)

    def test_toggle_preserves_details_and_restores_focus(self):
        click = self.source[self.source.index('const laneToggle = e.target.closest'):
                            self.source.index('const boardStart = e.target.closest')]
        self.assertIn("e.stopPropagation()", click)
        self.assertIn("chiefLaneOpen[lane] = parent.open", click)
        self.assertIn("renderChief()", click)
        self.assertIn("requestAnimationFrame", click)
        self.assertIn("data-chief-lane-details", self.source)

    def test_normal_document_flow_has_no_internal_scroll(self):
        body = re.search(r"\.chief-accordion-body\{([^}]*)\}", self.source)
        listing = re.search(r"\.chief-accordion-list\{([^}]*)\}", self.source)
        self.assertIsNotNone(body)
        self.assertIsNotNone(listing)
        for rule in (body.group(1), listing.group(1)):
            self.assertIn("max-height:none", rule)
            self.assertIn("overflow:visible", rule)
            self.assertNotIn("overflow:auto", rule)


if __name__ == "__main__":
    unittest.main(verbosity=2)
