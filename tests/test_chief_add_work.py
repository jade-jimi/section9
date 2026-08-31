"""Add-work project selection and Jira-backed creation (REQ-20260831-025-wfow)."""

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefAddWork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        start = cls.source.index("async function chiefChooseWorkProject")
        end = cls.source.index("function chiefSessionProject", start)
        cls.creation = cls.source[start:end]
        brief_start = cls.source.index("function renderChief(){")
        brief_end = cls.source.index("async function refreshChief", brief_start)
        cls.brief = cls.source[brief_start:brief_end]

    def test_all_projects_add_work_opens_project_chooser(self):
        self.assertIn('kind:"choose"', self.creation)
        self.assertIn("Which project owns this work?", self.creation)
        self.assertIn("project = await chiefChooseWorkProject(startSession)", self.creation)
        self.assertIn('chiefNorm(project.status) !== "closed"', self.creation)
        self.assertIn('chiefNorm(project.id) !== "unfiled"', self.creation)

    def test_add_work_is_not_disabled_without_scope(self):
        marker = self.brief[self.brief.index("data-chief-add-work"):
                            self.brief.index("</button>", self.brief.index("data-chief-add-work"))]
        self.assertNotIn("disabled", marker)
        self.assertIn("Choose a project, then add Jira-backed work", marker)

    def test_creation_remains_jira_backed_before_session(self):
        self.assertIn('chiefPost("createWork",{project,title,goal})', self.creation)
        self.assertIn("if (!made.jira || !made.request_id)", self.creation)
        self.assertLess(self.creation.index('chiefPost("createWork"'),
                        self.creation.index('chiefPost("projectSessionStart"'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
