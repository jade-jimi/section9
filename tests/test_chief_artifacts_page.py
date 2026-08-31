"""Curated project artifact library (REQ-20260831-010-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefArtifactsPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefArtifactSize")
        end = cls.source.index("function chiefTrailStep", start)
        cls.artifacts = cls.source[start:end]

    def test_artifacts_is_a_first_class_chief_page(self):
        self.assertIn('data-chief-nav="artifacts"', self.source)
        self.assertIn('"artifacts"]', self.source)
        self.assertIn('chiefDaily === "artifacts"', self.source)
        self.assertIn("renderChiefArtifacts()", self.source)

    def test_page_groups_server_curated_items_by_project(self):
        self.assertIn("chief-artifact-groups", self.artifacts)
        self.assertIn("chief-artifact-group-head", self.artifacts)
        self.assertIn("group.title", self.artifacts)
        self.assertIn("group.items.slice(0,8)", self.artifacts)
        self.assertIn("newest first", self.artifacts)

    def test_search_kind_filters_and_registry_refresh_exist(self):
        self.assertIn("data-chief-artifact-search", self.artifacts)
        self.assertIn("data-chief-artifact-kind", self.artifacts)
        self.assertIn("data-chief-artifact-refresh", self.artifacts)
        self.assertIn('chiefGet("artifacts")', self.artifacts)

    def test_registered_files_open_in_existing_report_reader(self):
        self.assertIn("data-chief-report-open", self.artifacts)
        self.assertIn("artifact?path=", self.artifacts)
        self.assertIn("chief-artifact-thumb", self.artifacts)
        self.assertIn('loading="lazy"', self.artifacts)

    def test_page_explains_curated_not_scanned_semantics(self):
        self.assertIn("explicitly published", self.artifacts)
        self.assertIn("not scanning the filesystem", self.artifacts)
        self.assertIn("Request files, status JSON, logs", self.artifacts)

    def test_unavailable_registry_entries_remain_visible(self):
        self.assertIn("chief-artifact-card unavailable", self.artifacts)
        self.assertIn("Registered file is unavailable", self.artifacts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
