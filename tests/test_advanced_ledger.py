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


    def test_generation_partition_and_prewrite_cancel(self):
        from ainotepro.core.advanced_batch import BatchRunResult
        ledger = AdvancedBatchLedger.for_notes(range(1, 6))
        result = BatchRunResult(
            accepted=((SimpleNamespace(note_id=1), {"Out": "ok"}),),
            current_batch_ids=(1, 2, 3), current_batch_pending=(2, 3),
            current_batch_requested_ids=(1, 2, 3), not_started=(4, 5),
            stop_reason="no-progress", safe_error="", request_count=4, retry_count=3,
        )
        ledger.stage_batch_result(result)
        self.assertEqual(ledger.states, {
            1: "validated", 2: "not-generated", 3: "not-generated",
            4: "not-started", 5: "not-started",
        })
        ledger.apply_commit_result(SimpleNamespace(
            outcomes=[], fatal_error=None, fatal_status="cancelled-before-write",
        ))
        self.assertEqual(ledger.states[1], "cancelled")
        self.assertEqual(ledger.states[2], "not-generated")

    def test_submitted_failure_is_not_mistaken_for_no_write(self):
        from ainotepro.core.advanced_batch import BatchRunResult
        result = BatchRunResult(
            accepted=((SimpleNamespace(note_id=1), {"Out": "yes"}),),
            current_batch_ids=(), current_batch_pending=(),
            current_batch_requested_ids=(), not_started=(),
            stop_reason="complete", safe_error="", request_count=1, retry_count=0,
        )
        ledger = AdvancedBatchLedger.for_notes([1])
        ledger.stage_batch_result(result)
        ledger.mark_commit_failure(submission_possible=True)
        self.assertEqual(ledger.states[1], "commit-uncertain")

    def test_invalid_partition_is_rejected(self):
        from ainotepro.core.advanced_batch import BatchRunResult
        ledger = AdvancedBatchLedger.for_notes([1, 2])
        result = BatchRunResult(
            accepted=((SimpleNamespace(note_id=1), {"Out": "good"}),),
            current_batch_ids=(1,), current_batch_pending=(1,),
            current_batch_requested_ids=(1,), not_started=(2,),
            stop_reason="no-progress", safe_error="", request_count=3, retry_count=2,
        )
        with self.assertRaises(ValueError):
            ledger.stage_batch_result(result)


    def test_cancel_after_undo_start_preserves_prior_conflict_and_reports_empty_undo(self):
        from ainotepro.core.advanced_batch import BatchRunResult
        ledger = AdvancedBatchLedger.for_notes([1, 2])
        run = BatchRunResult(
            accepted=((SimpleNamespace(note_id=1), {"Out": "x"}),
                      (SimpleNamespace(note_id=2), {"Out": "y"})),
            current_batch_ids=(), current_batch_pending=(),
            current_batch_requested_ids=(), not_started=(),
            stop_reason="complete", safe_error="", request_count=1,
            retry_count=0,
        )
        ledger.stage_batch_result(run)
        ledger.apply_commit_result(SimpleNamespace(
            outcomes=[(1, "conflict")],
            fatal_error="An empty Undo entry may remain.",
            fatal_status="cancelled-after-undo-start",
        ))
        self.assertEqual(ledger.states, {1: "conflict", 2: "cancelled"})
        self.assertIn("empty Undo", ledger.summary("Done"))


if __name__ == "__main__":
    unittest.main()
