"""Headless behavioral tests for Advanced draft and late-result state gates."""
from __future__ import annotations

import ast
from enum import IntFlag
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace

from ainotepro.core.advanced_commit import AdvancedCommitResult


SOURCE = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
TREE = ast.parse(SOURCE)
TAB = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
WANTED = {
    "_on_advanced_field_selection_changed", "_collect_advanced_result",
    "_finish_advanced_requests", "_handle_advanced_commit_result", "_advanced_summary",
}
METHODS = [node for node in TAB.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
MODULE = ast.Module(body=[ast.ClassDef(name="StateMethods", bases=[], keywords=[],
                                       body=METHODS, decorator_list=[])], type_ignores=[])
SCOPE = {
    "Optional": __import__("typing").Optional,
    "Dict": __import__("typing").Dict,
    "AdvancedCommitResult": AdvancedCommitResult,
    "mw": SimpleNamespace(reset=lambda: None),
}
exec(compile(ast.fix_missing_locations(MODULE), "<advanced state methods>", "exec"), SCOPE)
StateMethods = SCOPE["StateMethods"]


class _Fields:
    def __init__(self, names, selected):
        self.names = list(names)
        self.selected = list(selected)
        self.disabled = set()

    def selected_fields(self):
        return list(self.selected)

    def count(self):
        return len(self.names)

    def itemText(self, index):
        return self.names[index]

    def set_fields(self, names, selected, disabled):
        self.names = list(names)
        self.selected = list(selected)
        self.disabled = set(disabled)

    def set_disabled_fields(self, disabled):
        self.disabled = set(disabled)


class _Tab(StateMethods):
    def __init__(self):
        self._field_mode = "advanced"
        self._active_prompt_name = "Default"
        self._dirty = True
        self._last_advanced_fields = (["Text"], ["Out"])
        self._advanced_field_selection = (["Text"], ["Out"])
        self.advanced_source_fields = _Fields(["Text", "Scenario", "Out"], ["Text", "Scenario"])
        self.advanced_destination_fields = _Fields(["Text", "Scenario", "Out"], ["Out"])
        self.prompt_text = "user draft"
        self.load_count = 0
        self._advanced_results = []
        self._advanced_cancel = threading.Event()
        self._advanced_run_id = 1
        self._advanced_closing = False
        self.finished = []
        self.commit_calls = []

    def _prompt_is_dirty(self):
        return self._dirty

    def _confirm_dynamic_default_regeneration(self):
        return False

    def _load_prompt_list(self):
        self.load_count += 1

    def _finish_advanced_ui(self, message):
        self.finished.append(message)

    def _commit_advanced_results(self, valid, failures):
        self.commit_calls.append((valid, failures))

    def _save_current_provider_config(self):
        raise RuntimeError("settings disk unavailable")

    def isVisible(self):
        return True


class AdvancedUiStateTests(unittest.TestCase):
    def test_cancelled_dynamic_default_selection_restores_original_selection_and_draft(self):
        tab = _Tab()
        tab._on_advanced_field_selection_changed()
        self.assertEqual(tab.advanced_source_fields.selected_fields(), ["Text"])
        self.assertEqual(tab.advanced_destination_fields.selected_fields(), ["Out"])
        self.assertEqual(tab._advanced_field_selection, (["Text"], ["Out"]))
        self.assertEqual(tab.prompt_text, "user draft")
        self.assertEqual(tab.load_count, 0)

    def test_discarded_dynamic_default_selection_regenerates_after_selection_changes(self):
        tab = _Tab()
        tab._discarded_dynamic_default = False

        def discard():
            tab._discarded_dynamic_default = True
            return True

        tab._confirm_dynamic_default_regeneration = discard
        tab._on_advanced_field_selection_changed()
        self.assertEqual(tab._advanced_field_selection, (["Text", "Scenario"], ["Out"]))
        self.assertEqual(tab.load_count, 1)
        self.assertFalse(tab._discarded_dynamic_default)

    def test_late_result_and_finish_after_cancel_cannot_schedule_commit(self):
        tab = _Tab()
        tab._advanced_cancel.set()
        result = (1, type("Snapshot", (), {"note_id": 1})(), {"Out": "value"}, None, None)
        tab._collect_advanced_result(result)
        tab._finish_advanced_requests((1, "Generation cancelled.", None))
        self.assertEqual(tab._advanced_results, [])
        self.assertEqual(tab.commit_calls, [])
        self.assertEqual(tab.finished, ["Generation cancelled. No uncommitted results were written."])

    def test_stale_worker_result_is_ignored_before_it_reaches_commit_queue(self):
        tab = _Tab()
        stale = (0, type("Snapshot", (), {"note_id": 1})(), {"Out": "value"}, None, None)
        tab._collect_advanced_result(stale)
        self.assertEqual(tab._advanced_results, [])

    def test_terminal_worker_failure_is_counted_without_scheduling_commit(self):
        tab = _Tab()
        tab._finish_advanced_requests((1, "worker broke", "worker-failed"))
        self.assertEqual(tab.commit_calls, [])
        self.assertIn("worker-failed=1", tab.finished[0])

    def test_provider_config_save_failure_preserves_commit_outcome_and_finishes_ui(self):
        tab = _Tab()
        result = AdvancedCommitResult(SimpleNamespace(), [(1, "updated")])
        failures = []
        tab._handle_advanced_commit_result(result, failures)
        self.assertEqual(len(tab.finished), 1)
        self.assertIn("Updated 1 notes", tab.finished[0])
        self.assertIn("settings-save-failed=1", tab.finished[0])
        self.assertEqual(failures[0][0], "settings-save-failed")


if __name__ == "__main__":
    unittest.main()
