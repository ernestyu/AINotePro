import unittest
from types import SimpleNamespace

from ainotepro.core.advanced_ledger import AdvancedBatchLedger


class AdvancedLedgerTests(unittest.TestCase):
    def test_every_selected_note_receives_one_terminal_outcome_after_mixed_results(self):
        ledger = AdvancedBatchLedger.for_notes([1, 2, 3, 4, 5])
        ledger.record_worker(1, None, None)
        ledger.record_worker(2, "provider-failed", "timeout")
        ledger.record_worker(3, "json-failed", "bad JSON")
        ledger.record_worker(4, None, None)
        ledger.apply_commit_result(SimpleNamespace(
            outcomes=[(1, "updated"), (4, "conflict")], fatal_error=None, fatal_status=None,
        ))
        self.assertEqual(ledger.states, {
            1: "updated", 2: "provider-failed", 3: "json-failed", 4: "conflict",
            5: "commit-task-failed",
        })

    def test_fatal_uncertain_commit_marks_unsubmitted_validated_notes_explicitly(self):
        ledger = AdvancedBatchLedger.for_notes([1, 2, 3])
        for note_id in (1, 2, 3):
            ledger.record_worker(note_id, None, None)
        ledger.apply_commit_result(SimpleNamespace(
            outcomes=[(1, "commit-uncertain")], fatal_error="storage unknown",
            fatal_status="commit-uncertain",
        ))
        self.assertEqual(ledger.states, {
            1: "commit-uncertain", 2: "not-submitted", 3: "not-submitted",
        })
        self.assertIn("not-submitted=2", ledger.summary("Done"))

    def test_cancel_changes_only_pending_or_validated_notes(self):
        ledger = AdvancedBatchLedger.for_notes([1, 2, 3])
        ledger.record_worker(1, "provider-failed", "timeout")
        ledger.record_worker(2, None, None)
        ledger.cancel_pending()
        self.assertEqual(ledger.states, {1: "provider-failed", 2: "cancelled", 3: "cancelled"})


if __name__ == "__main__":
    unittest.main()
