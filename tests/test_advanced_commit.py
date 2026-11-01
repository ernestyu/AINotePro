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
                 fail_update_for=None, update_error_state="all", fail_reads_after_update=False,
                 fail_read_for=None):
        self.storage = {note_id: dict(note) for note_id, note in notes.items()}
        self.update_calls = []
        self.undo_add_calls = []
        self.undo_merge_calls = []
        self.cancel_after_first = cancel_after_first
        self.fail_merge = fail_merge
        self.fail_update_for = set(fail_update_for or [])
        self.update_error_state = update_error_state
        self.fail_reads_after_update = fail_reads_after_update
        self.fail_read_for = set(fail_read_for or [])

    def get_note(self, note_id):
        if self.fail_reads_after_update and self.update_calls:
            raise RuntimeError("storage read failed")
        if note_id in self.fail_read_for:
            raise RuntimeError("initial read failed")
        return _Note(note_id, self.storage[note_id])

    def add_custom_undo_entry(self, label):
        self.undo_add_calls.append(label)
        return 42

    def update_note(self, note):
        self.update_calls.append(note.id)
        if note.id in self.fail_update_for:
            if self.update_error_state == "partial":
                self.storage[note.id]["A"] = note["A"]
            elif self.update_error_state == "all":
                self.storage[note.id] = dict(note)
            raise RuntimeError("update failed")
        self.storage[note.id] = dict(note)
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
        col = _Collection({1: _Note(1, {"Text": "one", "A": "old", "B": "old"}),
                           2: _Note(2, {"Text": "two", "A": "", "B": ""})})
        first, second = col.get_note(1), col.get_note(2)
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
        self.assertEqual(col.storage[1]["A"], "new A")
        self.assertEqual(col.storage[1]["B"], "new B")
        self.assertEqual(col.storage[2]["A"], "next A")
        self.assertEqual(col.storage[2]["B"], "next B")
        self.assertEqual(result.outcomes, [(1, "updated"), (2, "updated")])
        self.assertEqual(result.changes.merged,
                         ["update:1", "undo:42:1", "update:2", "undo:42:2"])

    def test_cancel_after_non_interruptible_first_submit_skips_later_notes(self):
        cancel = threading.Event()
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""}),
                           2: _Note(2, {"Text": "two", "A": "", "B": ""})}, cancel_after_first=cancel)
        first, second = col.get_note(1), col.get_note(2)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), cancel, _Changes,
        )
        self.assertEqual(col.update_calls, [1])
        self.assertEqual(result.outcomes, [(1, "updated"), (2, "cancelled")])
        self.assertEqual(col.storage[2]["A"], "")
        self.assertEqual(col.storage[2]["B"], "")

    def test_undo_api_absence_has_zero_note_updates(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""})})
        note = col.get_note(1)
        col.merge_undo_entries = None
        result = commit_validated_results(
            col, [(_snapshot(note), {"A": "a", "B": "b"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertIn("unavailable", result.fatal_error)
        self.assertEqual(col.update_calls, [])
        self.assertEqual(col.storage[1]["A"], "")

    def test_failed_undo_merge_reports_persisted_undo_uncertainty_and_stops(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""}),
                           2: _Note(2, {"Text": "two", "A": "", "B": ""})}, fail_merge=True)
        first, second = col.get_note(1), col.get_note(2)
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
        self.assertEqual(col.storage[1]["A"], "a")
        self.assertEqual(col.storage[2]["A"], "")

    def test_zero_target_observation_after_update_error_is_still_terminally_uncertain(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""}),
                           2: _Note(2, {"Text": "two", "A": "", "B": ""})},
                          fail_update_for={1}, update_error_state="none")
        first, second = col.get_note(1), col.get_note(2)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "commit-uncertain")])
        self.assertIn("no-targets-observed", result.fatal_error)
        self.assertEqual(col.storage[1]["A"], "")
        self.assertEqual(col.storage[2]["A"], "")

    def test_partial_target_observation_after_update_error_is_uncertain_and_stops(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""}),
                           2: _Note(2, {"Text": "two", "A": "", "B": ""})},
                          fail_update_for={1}, update_error_state="partial")
        first, second = col.get_note(1), col.get_note(2)
        result = commit_validated_results(
            col,
            [(_snapshot(first), {"A": "a", "B": "b"}, None),
             (_snapshot(second), {"A": "c", "B": "d"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "commit-uncertain")])
        self.assertEqual(result.fatal_status, "commit-uncertain")
        self.assertIn("partial-targets-observed", result.fatal_error)
        self.assertEqual(col.update_calls, [1])
        self.assertEqual(col.storage[1]["A"], "a")
        self.assertEqual(col.storage[1]["B"], "")
        self.assertEqual(col.storage[2]["A"], "")

    def test_all_target_and_read_failure_observations_are_explicitly_uncertain(self):
        for state, read_failure, expected in (
            ("all", False, "all-targets-observed"),
            ("none", True, "storage-read-failed"),
        ):
            with self.subTest(state=state, read_failure=read_failure):
                col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""})},
                                  fail_update_for={1}, update_error_state=state,
                                  fail_reads_after_update=read_failure)
                first = col.get_note(1)
                result = commit_validated_results(
                    col, [(_snapshot(first), {"A": "a", "B": "b"}, None)],
                    ("Text",), ("A", "B"), threading.Event(), _Changes,
                )
                self.assertEqual(result.outcomes, [(1, "commit-uncertain")])
                self.assertIn(expected, result.fatal_error)

    def test_same_value_update_error_is_not_mistaken_for_a_confirmed_no_write(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "same", "B": "same"})},
                          fail_update_for={1}, update_error_state="all")
        snapshot = _snapshot(col.get_note(1))
        result = commit_validated_results(
            col, [(snapshot, {"A": "same", "B": "same"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "commit-uncertain")])
        self.assertIn("same-as-snapshot", result.fatal_error)

    def test_final_read_failure_is_a_per_note_failure_with_zero_update_attempts(self):
        col = _Collection({1: _Note(1, {"Text": "one", "A": "", "B": ""})})
        snapshot = _snapshot(col.get_note(1))
        col.fail_read_for.add(1)
        result = commit_validated_results(
            col, [(snapshot, {"A": "a", "B": "b"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "commit-failed")])
        self.assertEqual(col.update_calls, [])

    def test_second_note_update_error_preserves_first_and_does_not_submit_later_notes(self):
        col = _Collection({
            1: _Note(1, {"Text": "one", "A": "", "B": ""}),
            2: _Note(2, {"Text": "two", "A": "", "B": ""}),
            3: _Note(3, {"Text": "three", "A": "", "B": ""}),
        }, fail_update_for={2}, update_error_state="partial")
        snapshots = [_snapshot(col.get_note(note_id)) for note_id in (1, 2, 3)]
        result = commit_validated_results(
            col,
            [(snapshots[0], {"A": "a1", "B": "b1"}, None),
             (snapshots[1], {"A": "a2", "B": "b2"}, None),
             (snapshots[2], {"A": "a3", "B": "b3"}, None)],
            ("Text",), ("A", "B"), threading.Event(), _Changes,
        )
        self.assertEqual(result.outcomes, [(1, "updated"), (2, "commit-uncertain")])
        self.assertEqual(col.update_calls, [1, 2])
        self.assertEqual(col.storage[1]["A"], "a1")
        self.assertEqual(col.storage[2]["A"], "a2")
        self.assertEqual(col.storage[3]["A"], "")


if __name__ == "__main__":
    unittest.main()
