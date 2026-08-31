"""Production-complete Ready work uses one evidence-backed close action (REQ-20260831-041-wfow)."""

import json
import os
import shutil
import subprocess
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


class ChiefProductionDone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()

    def _run_action_guard(self, rows):
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            self.skipTest("node is unavailable")
        start = self.source.index("function chiefProductionAction")
        end = self.source.index("function chiefProductionEvidenceText", start)
        helper = self.source[start:end]
        script = (
            "const chiefNorm = v => String(v || '').trim().toLowerCase().replace(/[\\s-]+/g, '_');\n"
            + helper
            + f"\nconst rows = {json.dumps(rows)};"
            + "\nconsole.log(JSON.stringify(rows.map(row => Boolean(chiefProductionAction(row, 'ready')))));"
        )
        result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_only_server_issued_open_jira_action_is_eligible(self):
        evidence = {
            "release_id": "argon-2026-08-31",
            "feature_prs": [{"id": 1093, "state": "MERGED", "merged_at": "2026-08-30T12:00:00Z"}],
            "production_pr": {"id": 1101, "state": "MERGED", "merged_at": "2026-08-31T12:00:00Z"},
            "verified_at": "2026-09-01T00:00:00+09:00",
        }
        eligible = {
            "id": "REQ-20260831-03", "jira": "BDA-3038", "jira_status": "Open",
            "production_complete": True,
            "production_action": {"id": "claim_production_done", "label": "Claim production done + close Jira",
                                  "endpoint": "/api/work/done", "evidence": evidence,
                                  "body": {"id": "REQ-20260831-03", "jira": "BDA-3038", "sync_jira": True,
                                           "production_action": "claim_production_done",
                                           "production_evidence_fingerprint": "proof-1"}},
        }
        unrelated_release = {
            "id": "REQ-20260831-04", "jira": "BDA-9999", "jira_status": "Open",
            "production_complete": False, "release": {"status": "released"},
            "production_action": None,
        }
        self.assertEqual(self._run_action_guard([eligible, unrelated_release]), [True, False])

    def test_missing_evidence_terminal_jira_and_non_req_are_not_actionable(self):
        incomplete = {
            "id": "REQ-20260831-03", "jira": "BDA-3038", "jira_status": "Open",
            "production_complete": True,
            "production_action": {"id": "claim_production_done", "evidence": {}},
        }
        terminal = {
            "id": "REQ-20260831-03", "jira": "BDA-3038", "jira_status": "Done",
            "production_complete": True,
            "production_action": {"id": "claim_production_done", "evidence": {
                "feature_prs": [{"id": 1093}], "production_pr": {"id": 1101}, "verified_at": "now"}},
        }
        raw_jira = {
            "id": "BDA-3038", "jira": "BDA-3038", "jira_status": "Open",
            "production_complete": True,
            "production_action": {"id": "claim_production_done", "evidence": {
                "feature_prs": [{"id": 1093}], "production_pr": {"id": 1101}, "verified_at": "now"}},
        }
        self.assertEqual(self._run_action_guard([incomplete, terminal, raw_jira]), [False, False, False])

    def test_ready_row_replaces_start_work_with_exact_claim_label(self):
        start = self.source.index("function chiefAccordionRows")
        end = self.source.index("function chiefPresentationInstant", start)
        rows = self.source[start:end]
        self.assertIn("chiefProductionAction(row,lane)", rows)
        self.assertIn("Claim production done + close Jira", rows)
        self.assertIn('productionAction ? productionAction.id', rows)

    def test_claim_reuses_verified_complete_endpoint_with_evidence(self):
        start = self.source.index("async function chiefClaimProductionDone")
        end = self.source.index("async function chiefStartRelease", start)
        claim = self.source[start:end]
        self.assertIn('chiefPost("complete"', claim)
        self.assertIn("const payload = {...action.body}", claim)
        self.assertIn('chiefPost("complete",payload)', claim)
        self.assertNotIn("production_evidence:evidence", claim)
        self.assertIn("Final human gate", claim)
        self.assertIn("It will not merge or deploy anything", claim)

    def test_click_dispatches_claim_before_generic_ready_start(self):
        click = self.source[self.source.index('const chiefAct = e.target.closest("[data-chief-action]")'):
                            self.source.index("const chiefRelease =", self.source.index('const chiefAct = e.target.closest("[data-chief-action]")'))]
        claim = click.index('action === "claim_production_done"')
        generic = click.index('action === "ready" || action === "progress"')
        self.assertLess(claim, generic)
        self.assertIn("chiefClaimProductionDone(row,title)", click)

    def test_terminal_production_card_is_presented_as_done_evidence(self):
        start = self.source.index("function chiefAccordionRows")
        end = self.source.index("function chiefPresentationInstant", start)
        rows = self.source[start:end]
        self.assertIn('lane === "done" && row.production_complete ? "Production done"', rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
