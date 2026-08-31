"""Persisted per-project session provider (REQ-20260831-015-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefProjectEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("function chiefReleaseProjectCard")
        end = cls.source.index("function renderChiefReleasePage", start)
        cls.card = cls.source[start:end]

    def test_release_card_shows_all_project_provider_choices(self):
        self.assertIn("chief-release-project-engine", self.card)
        self.assertIn(">Model</span>", self.card)
        self.assertIn("Object.entries(CHIEF_ENGINES)", self.card)
        self.assertIn("data-chief-project-engine", self.card)
        self.assertIn("aria-pressed", self.card)
        self.assertNotIn(">T3 Code</button>", self.card)

    def test_selection_uses_named_persistence_route(self):
        self.assertIn('projectEngine:["api/chief/project/engine","/project/engine"]',
                      self.source)
        start = self.source.index("async function chiefSetProjectEngine")
        end = self.source.index("const chiefDetailText", start)
        setter = self.source[start:end]
        self.assertIn('chiefPost("projectEngine",{project,engine})', setter)
        self.assertIn("row.engine = engine", setter)

    def test_release_action_uses_project_engine_not_global_only(self):
        self.assertIn("registeredProject && registeredProject.engine", self.card)
        self.assertIn("data-chief-release-engine", self.card)
        self.assertIn("chiefRelease.dataset.chiefReleaseEngine || chiefEngine", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
