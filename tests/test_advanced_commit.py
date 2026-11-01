"""Mocked collection tests for the Advanced single-note commit boundary."""
from __future__ import annotations

import threading
import unittest

from ainotepro.core.advanced_commit import commit_validated_results
from ainotepro.core.advanced_text import build_snapshot


class _Changes:
    def __init__(self, label="root"):
        self.label = label
        self.merged = []

    def MergeFrom(self, other):
        self.merged.append(other.label)


class _Note(dict):
    def __init__(self, note_id, fields):
        super().__init__(fields)
        self.id = note_id

    def note_type(self):
        return {"id": 7, "flds": [{"name": "Text"}, {"name": "A"}, {"name": "B"}]}


class _Collection:
    def __init__(self, notes, *, cancel_after_first=None, fail_merge=False,
                 fail_update_for=None, persist_update_error=True):
        self.notes = notes
        self.original_notes = {note_id: dict(note) for note_id, note in notes.items()}
        self.update_calls = []
        self.undo_add_calls = []
        self.undo_merge_calls = []
        self.cancel_after_first = cancel_after_first
        self.fail_merge = fail_merge
        self.fail_update_for = set(fail_update_for or [])
        self.persist_update_error = persist_update_error

    def get_note(self, note_id):
        return self.notes[note_id]

    def add_custom_undo_entry(self, label):
        self.undo_add_calls.append(label)
        return 42

    def update_note(self, note):
        self.update_calls.append(note.id)
        if note.id in self.fail_update_for:
            if not self.persist_update_error:
                note.clear()
                note.update(self.original_notes[note.id])
            raise RuntimeError("update failed")
        if self.cancel_after_first is not None and len(self.update_calls) == 1:
            self.cancel_after_first.set()
        return _Changes(f"update:{note.id}")

    def merge_undo_entries(self, undo_id):
        self.undo_merge_calls.append(undo_id)
        if self.fail_merge:
            raise RuntimeError("merge failed")
        return _Changes(f"undo:{undo_id}:{len(self.undo_merge_calls)}")


def _snapshot(note):
    return build_snapshot(note.id, 7, ["Text", "A", "B"], dict(note), ["Text"], ["A", "B"])


class AdvancedCommitTests(unittest.TestCase):
    def test_each_note_is_updated_once_and_all_op_changes_are_aggregated(self):
        first = _Note(1, {"Text": "one", "A": "old", "B": "old"})
        second = _Note(2, {"Text": "two", "A": "", "B": ""})
        col = _Collection({1: first, 2: second})
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "new A", "B": "new B"}, None),
             (_snapshot(second), {"A": "next A", "B": "next B"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertIsNone(result.fatal_error)
        self.assertEqual(col.update_calls, [1, 2])
        self.assertEqual(col.undo_add_calls, ["AINotePro advanced text generation"])
        self.assertEqual(col.undo_merge_calls, [42, 42])
        self.assertEqual(first["A"], "new A")
        self.assertEqual(first["B"], "new B")
        self.assertEqual(second["A"], "next A")
        self.assertEqual(second["B"], "next B")
        self.assertEqual(result.outcomes, [(1, "updated"), (2, "updated")])
        self.assertEqual(result.changes.merged,
                         ["update:1", "undo:42:1", "update:2", "undo:42:2"])

    def test_cancel_after_non_interruptible_first_submit_skips_later_notes(self):
        cancel = threading.Event()
        first = _Note(1, {"Text": "one", "A": "", "B": ""})
        second = _Note(2, {"Text": "two", "A": "", "B": ""})
        col = _Collection({1: first, 2: second}, cancel_after_first=cancel)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), cancel, _Changes,
        )
        self.assertEqual(col.update_calls, [1])
        self.assertEqual(result.outcomes, [(1, "updated"), (2, "cancelled")])
        self.assertEqual(second["A"], "")
        self.assertEqual(second["B"], "")

    def test_undo_api_absence_has_zero_note_updates(self):
        note = _Note(1, {"Text": "one", "A": "", "B": ""})
        col = _Collection({1: note})
        col.merge_undo_entries = None
        result = commit_validated_results(
            col, [(_snapshot(note), {"A": "a", "B": "b"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertIn("unavailable", result.fatal_error)
        self.assertEqual(col.update_calls, [])
        self.assertEqual(note["A"], "")

    def test_failed_undo_merge_reports_persisted_undo_uncertainty_and_stops(self):
        first = _Note(1, {"Text": "one", "A": "", "B": ""})
        second = _Note(2, {"Text": "two", "A": "", "B": ""})
        col = _Collection({1: first, 2: second}, fail_merge=True)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(col.update_calls, [1])
        self.assertEqual(result.outcomes, [(1, "persisted-undo-uncertain")])
        self.assertEqual(result.fatal_status, "persisted-undo-uncertain")
        self.assertIn("may be persisted", result.fatal_error)
        self.assertEqual(first["A"], "a")
        self.assertEqual(second["A"], "")

    def test_confirmed_nonpersistent_update_failure_is_isolated_from_later_notes(self):
        first = _Note(1, {"Text": "one", "A": "", "B": ""})
        second = _Note(2, {"Text": "two", "A": "", "B": ""})
        col = _Collection({1: first, 2: second}, fail_update_for={1}, persist_update_error=False)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertIsNone(result.fatal_error)
        self.assertEqual(result.outcomes, [(1, "commit-failed"), (2, "updated")])
        self.assertEqual(first["A"], "")
        self.assertEqual(second["A"], "c")

    def test_persistent_update_error_is_explicitly_uncertain_and_stops(self):
        first = _Note(1, {"Text": "one", "A": "", "B": ""})
        second = _Note(2, {"Text": "two", "A": "", "B": ""})
        col = _Collection({1: first, 2: second}, fail_update_for={1}, persist_update_error=True)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "commit-uncertain")])
        self.assertEqual(result.fatal_status, "commit-uncertain")
        self.assertEqual(col.update_calls, [1])
        self.assertEqual(first["A"], "a")
        self.assertEqual(second["A"], "")


if __name__ == "__main__":
    unittest.main()
