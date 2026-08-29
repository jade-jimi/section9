"""Raw Board start-work UI contract (REQ-20260829-021-wfow)."""

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "index.html")


def function_body(source, name):
    start = source.index(f"function {name}")
    brace = source.index("{", start)
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:pos]
    raise AssertionError(f"unterminated function {name}")


class BoardStartAction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WEB, encoding="utf-8") as handle:
            cls.source = handle.read()
        cls.card = function_body(cls.source, "cardHTML")
        cls.start = cls.source[cls.source.index("async function boardStartWork"):
                               cls.source.index("function cardHTML")]

    def test_only_open_requests_get_start_action(self):
        self.assertIn('isReq && r.status === "open"', self.card)
        self.assertIn('data-board-start=', self.card)
        self.assertIn('Start work', self.card)

    def test_context_action_remains_distinct_and_context_only(self):
        self.assertIn('data-pick=', self.card)
        self.assertIn('이어 말하기 <span>context only</span>', self.card)
        self.assertIn('context only — 이어 말하기', self.card)

    def test_selected_engine_reaches_atomic_start_endpoint(self):
        self.assertIn('const engine = chiefEngineValue(chiefEngine)', self.start)
        self.assertIn('fetch("/api/work/start"', self.start)
        self.assertIn('JSON.stringify({id,engine})', self.start)

    def test_board_has_one_shared_engine_selector(self):
        picker = function_body(self.source, "boardEnginePickerHTML")
        self.assertIn('role="group"', picker)
        self.assertIn('data-chief-engine=', picker)
        self.assertIn('aria-pressed=', picker)
        board = function_body(self.source, "renderBoard")
        self.assertEqual(board.count("boardEnginePickerHTML()"), 1)
        self.assertIn('tab === "chief" ? renderChief() : render()', self.source)

    def test_busy_success_and_error_are_explicit(self):
        for state in ('status:"starting"', 'status:"started"', 'status:"error"'):
            self.assertIn(state, self.start)
        self.assertIn('aria-busy="${startBusy}"', self.card)
        self.assertIn('Starting…', self.card)
        self.assertIn('role="alert"', self.card)
        self.assertIn('Could not start:', self.card)

    def test_start_click_is_handled_before_card_open(self):
        click = self.source[self.source.index('document.addEventListener("click", async e =>'):
                            self.source.index('const doc = e.target.closest("[data-doc]")')]
        self.assertLess(click.index('data-board-start'), click.index('data-pick'))
        self.assertIn('e.stopPropagation(); await boardStartWork', click)

    def test_compact_action_row_has_no_left_status_stripe(self):
        match = re.search(r"\.board-card-actions\{([^}]*)\}", self.source)
        self.assertIsNotNone(match)
        self.assertNotIn("border-left", match.group(1))
        self.assertIn("border-top", match.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
