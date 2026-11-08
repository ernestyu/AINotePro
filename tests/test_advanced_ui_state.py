"""Headless behavioral tests for Advanced draft and late-result state gates."""
from __future__ import annotations

import ast
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace

from ainotepro.core.advanced_batch import BatchRunResult
from ainotepro.core.advanced_text import reconcile_field_selection
from ainotepro.core.advanced_ledger import AdvancedBatchLedger
from ainotepro.ui.advanced_coordinator import AdvancedCommitCoordinator


SOURCE = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
TREE = ast.parse(SOURCE)
TAB = next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
WANTED = {
    "_on_advanced_field_selection_changed", "_finish_advanced_requests",
    "_advanced_coordinator_settled", "_update_advanced_progress",
    "_resolve_invalid_field", "_advanced_field_definition_is_current",
    "_invalid_advanced_field_entries", "_load_note_fields",
}
METHODS = [node for node in TAB.body if isinstance(node, ast.FunctionDef) and node.name in WANTED]
MODULE = ast.Module(body=[ast.ClassDef(name="StateMethods", bases=[], keywords=[],
                                       body=METHODS, decorator_list=[])], type_ignores=[])
SCOPE = {
    "Optional": __import__("typing").Optional,
    "Dict": __import__("typing").Dict,
    "AdvancedCommitCoordinator": AdvancedCommitCoordinator,
    "reconcile_field_selection": reconcile_field_selection,
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
        self._advanced_invalid_source_fields = set()
        self._advanced_invalid_destination_fields = set()
        self.advanced_source_fields = _Fields(["Text", "Scenario", "Out"], ["Text", "Scenario"])
        self.advanced_destination_fields = _Fields(["Text", "Scenario", "Out"], ["Out"])
        self.prompt_text = "user draft"
        self.load_count = 0
        self._advanced_results = []
        self._advanced_ledger = AdvancedBatchLedger.for_notes([1, 2])
        self._advanced_cancel = threading.Event()
        self._advanced_run_id = 1
        self._advanced_phase = "GENERATING"
        self._advanced_coordinator = None
        self._advanced_sources = ("Text",)
        self._advanced_destinations = ("Out",)
        self._advanced_progress = SimpleNamespace(setLabelText=lambda *_: None, setValue=lambda *_: None)
        self._advanced_closing = False
        self.finished = []
        self.commit_calls = []

    def _prompt_is_dirty(self):
        return self._dirty

    def _confirm_dynamic_default_regeneration(self):
        return False

    def _load_prompt_list(self):
        self.load_count += 1

    def _update_invalid_field_resolver(self):
        pass

    def _finish_advanced_ui(self, message):
        self.finished.append(message)

    def _commit_advanced_results(self, valid):
        self.commit_calls.append(valid)

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

    def test_changing_visible_fields_preserves_each_unresolved_source_and_destination(self):
        tab = _Tab()
        tab._dirty = False
        tab._advanced_field_selection = (["Text", "Missing Source"], ["Out", "Missing Destination"])
        tab._advanced_invalid_source_fields = {"Missing Source"}
        tab._advanced_invalid_destination_fields = {"Missing Destination"}
        tab.advanced_source_fields.selected = ["Text", "Scenario"]
        tab._on_advanced_field_selection_changed()
        self.assertEqual(tab._advanced_field_selection,
                         (["Text", "Scenario", "Missing Source"],
                          ["Out", "Missing Destination"]))
        self.assertEqual(tab._advanced_invalid_source_fields, {"Missing Source"})
        self.assertEqual(tab._advanced_invalid_destination_fields, {"Missing Destination"})

    def test_explicitly_deselecting_a_returned_invalid_field_resolves_only_that_field(self):
        tab = _Tab()
        tab._dirty = False
        tab.advanced_source_fields = _Fields(["Text", "Missing Source", "Out"], ["Text"])
        tab.advanced_destination_fields = _Fields(["Text", "Missing Source", "Out"], ["Out"])
        tab._last_advanced_fields = (["Text", "Missing Source"], ["Out"])
        tab._advanced_field_selection = (["Text", "Missing Source"], ["Out", "Missing Destination"])
        tab._advanced_invalid_source_fields = {"Missing Source"}
        tab._advanced_invalid_destination_fields = {"Missing Destination"}
        tab._on_advanced_field_selection_changed()
        self.assertEqual(tab._advanced_field_selection,
                         (["Text"], ["Out", "Missing Destination"]))
        self.assertEqual(tab._advanced_invalid_source_fields, set())
        self.assertEqual(tab._advanced_invalid_destination_fields, {"Missing Destination"})

    def test_resolver_menu_action_removes_only_the_chosen_unavailable_field(self):
        tab = _Tab()
        tab._active_prompt_name = "Custom"
        tab._advanced_field_selection = (["Text", "Missing Source"], ["Out", "Missing Destination"])
        tab._advanced_invalid_source_fields = {"Missing Source"}
        tab._advanced_invalid_destination_fields = {"Missing Destination"}
        tab._resolve_invalid_field("source", "Missing Source")
        self.assertEqual(tab._advanced_field_selection,
                         (["Text"], ["Out", "Missing Destination"]))
        self.assertEqual(tab._advanced_invalid_source_fields, set())
        self.assertEqual(tab._advanced_invalid_destination_fields, {"Missing Destination"})
        self.assertEqual(tab.advanced_source_fields.selected_fields(), ["Text", "Scenario"])
        self.assertEqual(tab.prompt_text, "user draft")

    def test_resolver_cancel_keeps_dynamic_default_draft_and_all_selections(self):
        tab = _Tab()
        tab._advanced_field_selection = (["Text", "Missing Source"], ["Out"])
        tab._advanced_invalid_source_fields = {"Missing Source"}
        tab._resolve_invalid_field("source", "Missing Source")
        self.assertEqual(tab._advanced_field_selection, (["Text", "Missing Source"], ["Out"]))
        self.assertEqual(tab._advanced_invalid_source_fields, {"Missing Source"})
        self.assertEqual(tab.prompt_text, "user draft")

    def test_resolver_entries_always_show_role_and_each_field(self):
        tab = _Tab()
        tab._advanced_invalid_source_fields = {"Z source", "A source"}
        tab._advanced_invalid_destination_fields = {"Out"}
        self.assertEqual(tab._invalid_advanced_field_entries(), [
            ("source", "A source"), ("source", "Z source"), ("destination", "Out"),
        ])


    def test_missing_fields_remain_checkable_in_existing_dropdowns(self):
        class Picker:
            def clear(self):
                self.names = []
            def addItems(self, names):
                self.names = names
            def findText(self, name):
                return self.names.index(name) if name in self.names else -1
            def setCurrentIndex(self, _index):
                pass
        class Note:
            def note_type(self):
                return {"id": 8, "flds": [
                    {"name": "Text"}, {"name": "Scenario"}, {"name": "Out"}]}
        tab = _Tab()
        tab._active_prompt_name = "Custom"
        tab._advanced_note_type_id = None
        tab._easy_field_selection = ("Text", "Out")
        tab.source_field_combo = Picker()
        tab.destination_field_combo = Picker()
        tab._selected_note_ids = lambda: [1]
        tab._advanced_field_selection = (
            ["Text", "Missing Source"], ["Out", "Missing Destination"])
        SCOPE["mw"] = SimpleNamespace(col=SimpleNamespace(
            get_note=lambda _id: Note()))
        self.assertTrue(tab._load_note_fields())
        self.assertEqual(tab.advanced_source_fields.names,
                         ["Text", "Scenario", "Out", "Missing Source"])
        self.assertEqual(tab.advanced_destination_fields.names,
                         ["Text", "Scenario", "Out", "Missing Destination"])
        self.assertEqual(tab.advanced_source_fields.selected_fields(),
                         ["Text", "Missing Source"])
        self.assertEqual(tab.advanced_destination_fields.selected_fields(),
                         ["Out", "Missing Destination"])
        tab.advanced_source_fields.selected = ["Text"]
        tab._on_advanced_field_selection_changed()
        self.assertEqual(tab._advanced_invalid_source_fields, set())
        self.assertEqual(tab._advanced_invalid_destination_fields,
                         {"Missing Destination"})
        self.assertEqual(tab._advanced_field_selection,
                         (["Text"], ["Out", "Missing Destination"]))

    def test_note_type_definition_check_detects_browser_selection_change(self):
        class Note:
            def __init__(self, type_id, fields):
                self.type_id, self.fields = type_id, fields
            def note_type(self):
                return {"id": self.type_id, "flds": [{"name": name} for name in self.fields]}

        tab = _Tab()
        tab._advanced_note_type_id = 7
        tab._advanced_field_names = ("Text", "Out")
        SCOPE["mw"] = SimpleNamespace(col=SimpleNamespace(get_note=lambda _note_id: Note(7, ["Text", "Out"])))
        self.assertTrue(tab._advanced_field_definition_is_current([1]))
        SCOPE["mw"] = SimpleNamespace(col=SimpleNamespace(get_note=lambda _note_id: Note(8, ["Text", "Out"])))
        self.assertFalse(tab._advanced_field_definition_is_current([1]))

    def test_cancelled_batch_does_not_schedule_commit(self):
        tab = _Tab()
        tab._advanced_cancel.set()
        result = BatchRunResult(
            accepted=(), current_batch_ids=(1, 2),
            current_batch_pending=(1, 2),
            current_batch_requested_ids=(1, 2), not_started=(),
            stop_reason="cancelled", safe_error="",
            request_count=1, retry_count=0,
        )
        tab._finish_advanced_requests((1, result))
        self.assertEqual(tab._advanced_phase, "SETTLED")
        self.assertEqual(tab._advanced_ledger.states, {1: "cancelled", 2: "cancelled"})
        self.assertIn("cancelled=2", tab.finished[0])

    def test_stale_worker_result_does_not_modify_ledger(self):
        tab = _Tab()
        result = BatchRunResult(
            accepted=(), current_batch_ids=(),
            current_batch_pending=(), current_batch_requested_ids=(),
            not_started=(1, 2), stop_reason="cancelled", safe_error="",
            request_count=0, retry_count=0,
        )
        tab._finish_advanced_requests((0, result))
        self.assertEqual(tab._advanced_phase, "GENERATING")
        self.assertEqual(tab._advanced_ledger.states, {1: "pending", 2: "pending"})

    def test_noncancel_worker_stop_with_no_accepted_sets_terminal_partition(self):
        tab = _Tab()
        result = BatchRunResult(
            accepted=(), current_batch_ids=(1,),
            current_batch_pending=(1,), current_batch_requested_ids=(1,),
            not_started=(2,), stop_reason="no-progress",
            safe_error="No new valid records.", request_count=3, retry_count=2,
        )
        tab._finish_advanced_requests((1, result))
        self.assertEqual(tab._advanced_ledger.states,
                         {1: "not-generated", 2: "not-started"})
        self.assertIn("not-generated=1", tab.finished[0])
        self.assertIn("not-started=1", tab.finished[0])


if __name__ == "__main__":
    unittest.main()
