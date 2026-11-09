"""Headless lifecycle tests for the Advanced non-QWidget commit owner."""
from __future__ import annotations

import sys
import threading
import types
import unittest
from unittest.mock import patch

from ainotepro.core.advanced_batch import BatchRunResult
from ainotepro.core.advanced_ledger import AdvancedBatchLedger
from ainotepro.core.advanced_text import build_snapshot
from ainotepro.ui.advanced_coordinator import (
    AdvancedCommitCoordinator, _ACTIVE_ADVANCED_COMMITS,
)


class Changes:
    def MergeFrom(self, _other):
        pass


class Note(dict):
    def __init__(self, note_id, **fields):
        super().__init__(fields)
        self.id = note_id

    def note_type(self):
        return {"id": 9, "flds": [{"name": "Text"}, {"name": "Out"}]}


class Collection:
    def __init__(self, note):
        self.note = note
        self.writes = 0
        self.undo_adds = 0

    def get_note(self, note_id):
        assert note_id == self.note.id
        return Note(note_id, **dict(self.note))

    def add_custom_undo_entry(self, _name):
        self.undo_adds += 1
        return 1

    def update_note(self, note):
        self.note = note
        self.writes += 1
        return Changes()

    def merge_undo_entries(self, _undo_id):
        return Changes()


class Tab:
    def __init__(self):
        self._advanced_run_id = 10
        self._advanced_closing = False
        self.finished = []

    def _advanced_coordinator_settled(self, _coordinator, summary):
        self.finished.append(summary)


def fixture():
    note = Note(1, Text="question", Out="")
    snapshot = build_snapshot(1, 9, ["Text", "Out"], dict(note), ["Text"], ["Out"])
    result = BatchRunResult(
        accepted=((snapshot, {"Out": "answer"}),),
        current_batch_ids=(), current_batch_pending=(), current_batch_requested_ids=(),
        not_started=(), stop_reason="complete", safe_error="",
        request_count=1, retry_count=0,
    )
    return note, result


def fake_modules(operation_hook=None, fail_submission=False):
    aqt = types.ModuleType("aqt")
    operations = types.ModuleType("aqt.operations")
    anki = types.ModuleType("anki")
    collection = types.ModuleType("anki.collection")
    aqt.mw = types.SimpleNamespace(reset=lambda: None)
    collection.OpChanges = Changes
    store = []

    class FakeCollectionOp:
        def __init__(self, parent, op):
            self.parent, self.op = parent, op

        def success(self, callback):
            self.success_callback = callback
            return self

        def failure(self, callback):
            self.failure_callback = callback
            return self

        def run_in_background(self, initiator):
            assert initiator is aqt.mw
            if operation_hook:
                operation_hook()
            if fail_submission:
                raise RuntimeError("queue failed")
            self.success_callback(self.op(store[0]))
    operations.CollectionOp = FakeCollectionOp
    aqt.operations = operations
    anki.collection = collection
    return {"aqt": aqt, "aqt.operations": operations,
            "anki": anki, "anki.collection": collection}, store


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(len(_ACTIVE_ADVANCED_COMMITS), 0)

    def test_success_uses_single_collectionop_and_settles(self):
        note, result = fixture()
        col = Collection(note)
        modules, store = fake_modules()
        store.append(col)
        tab = Tab()
        ledger = AdvancedBatchLedger.for_notes([1])
        with patch.dict(sys.modules, modules):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), threading.Event(), tab=tab)
            coordinator.start()
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertEqual(ledger.count("updated"), 1)
        self.assertEqual(col.writes, 1)
        self.assertEqual(col.undo_adds, 1)
        self.assertEqual(len(tab.finished), 1)
        self.assertEqual(len(_ACTIVE_ADVANCED_COMMITS), 0)

    def test_cancel_while_queued_produces_explicit_prewrite_status(self):
        note, result = fixture()
        col = Collection(note)
        cancel = threading.Event()
        modules, store = fake_modules(operation_hook=cancel.set)
        store.append(col)
        ledger = AdvancedBatchLedger.for_notes([1])
        with patch.dict(sys.modules, modules):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), cancel)
            coordinator.start()
        self.assertEqual(ledger.states[1], "cancelled")
        self.assertEqual(col.writes, 0)
        self.assertEqual(col.undo_adds, 0)

    def test_destroyed_tab_does_not_prevent_authoritative_commit(self):
        note, result = fixture()
        col = Collection(note)
        tab = Tab()
        def close_tab():
            tab._advanced_closing = True
        modules, store = fake_modules(operation_hook=close_tab)
        store.append(col)
        ledger = AdvancedBatchLedger.for_notes([1])
        with patch.dict(sys.modules, modules):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), threading.Event(), tab=tab)
            coordinator.start()
        self.assertEqual(col.writes, 1)
        self.assertEqual(ledger.states[1], "updated")
        self.assertEqual(tab.finished, [])

    def test_scheduling_exception_is_conservatively_uncertain(self):
        _, result = fixture()
        modules, store = fake_modules(fail_submission=True)
        ledger = AdvancedBatchLedger.for_notes([1])
        with patch.dict(sys.modules, modules):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), threading.Event())
            coordinator.start()
        self.assertEqual(ledger.states[1], "commit-uncertain")

    def test_cancel_before_queuing_discards_all_accepted(self):
        _, result = fixture()
        ledger = AdvancedBatchLedger.for_notes([1])
        cancel = threading.Event()
        cancel.set()
        coordinator = AdvancedCommitCoordinator(
            10, result, ledger, ("Text",), ("Out",), cancel)
        coordinator.start()
        self.assertEqual(ledger.states[1], "cancelled")
        self.assertEqual(len(_ACTIVE_ADVANCED_COMMITS), 0)


    def test_ui_observer_failure_still_releases_global_owner(self):
        _, result = fixture()
        ledger = AdvancedBatchLedger.for_notes([1])
        cancel = threading.Event()
        cancel.set()
        tab = Tab()
        callbacks = []
        def broken_observer(_coordinator, _summary):
            callbacks.append(1)
            raise ValueError("an observer must never strand the coordinator")
        tab._advanced_coordinator_settled = broken_observer
        coordinator = AdvancedCommitCoordinator(
            10, result, ledger, ("Text",), ("Out",), cancel, tab=tab)
        coordinator.start()
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertEqual(ledger.states[1], "cancelled")
        self.assertEqual(len(callbacks), 1)
        self.assertNotIn(coordinator, _ACTIVE_ADVANCED_COMMITS)
        coordinator._settle("duplicate completion")
        self.assertEqual(len(callbacks), 1)


    def test_success_result_ledger_exception_settles_conservatively(self):
        note, result = fixture()
        col = Collection(note)
        modules, store = fake_modules()
        store.append(col)
        ledger = AdvancedBatchLedger.for_notes([1])
        tab = Tab()
        with patch.object(ledger, "apply_commit_result", side_effect=ValueError("bad outcome")):
            with patch.dict(sys.modules, modules):
                coordinator = AdvancedCommitCoordinator(
                    10, result, ledger, ("Text",), ("Out",), threading.Event(), tab=tab)
                coordinator.start()
        self.assertEqual(col.writes, 1)
        self.assertEqual(ledger.states[1], "commit-uncertain")
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertNotIn(coordinator, _ACTIVE_ADVANCED_COMMITS)
        self.assertIn("could not be verified", tab.finished[0])
        coordinator._succeeded(object())
        self.assertEqual(len(tab.finished), 1)
        self.assertEqual(col.writes, 1)

    def test_malformed_success_callback_result_does_not_leak_owner(self):
        _, result = fixture()
        ledger = AdvancedBatchLedger.for_notes([1])
        ledger.stage_batch_result(result)
        coordinator = AdvancedCommitCoordinator(
            10, result, ledger, ("Text",), ("Out",), threading.Event())
        _ACTIVE_ADVANCED_COMMITS.add(coordinator)
        coordinator._submission_possible = True
        coordinator.phase = "COMMITTING"
        coordinator._succeeded(object())
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertEqual(ledger.states[1], "commit-uncertain")
        self.assertNotIn(coordinator, _ACTIVE_ADVANCED_COMMITS)

    def test_ledger_summary_exception_still_releases_owner(self):
        _, result = fixture()
        ledger = AdvancedBatchLedger.for_notes([1])
        cancel = threading.Event()
        cancel.set()
        tab = Tab()
        with patch.object(ledger, "summary", side_effect=ValueError("bad ledger")):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), cancel, tab=tab)
            coordinator.start()
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertNotIn(coordinator, _ACTIVE_ADVANCED_COMMITS)
        self.assertIn("Commit accounting unavailable", tab.finished[0])

    def test_success_callback_with_destroyed_tab_only_settles_once(self):
        note, result = fixture()
        col = Collection(note)
        modules, store = fake_modules()
        store.append(col)
        tab = Tab()
        def close_after_submission():
            # Only a tab destroyed after queueing can have committed writes.
            tab._advanced_closing = True
        modules, store = fake_modules(operation_hook=close_after_submission)
        store.append(col)
        ledger = AdvancedBatchLedger.for_notes([1])
        with patch.dict(sys.modules, modules):
            coordinator = AdvancedCommitCoordinator(
                10, result, ledger, ("Text",), ("Out",), threading.Event(), tab=tab)
            coordinator.start()
        self.assertEqual(coordinator.phase, "SETTLED")
        self.assertEqual(col.writes, 1)
        self.assertEqual(tab.finished, [])
        coordinator._failed(RuntimeError("late callback"))
        self.assertEqual(ledger.states[1], "updated")
        self.assertEqual(col.writes, 1)
        self.assertNotIn(coordinator, _ACTIVE_ADVANCED_COMMITS)


if __name__ == "__main__":
    unittest.main()
