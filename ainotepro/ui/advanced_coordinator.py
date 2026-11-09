"""Lifetime-safe final Advanced commit, independent of the Text tab's QWidget.

An active coordinator is held until the background CollectionOp returns.
Only it receives authoritative commit callbacks. TextTab is an optional,
weakly referenced observer which may disappear without losing the result.
"""
from __future__ import annotations

import weakref

from ..core.advanced_commit import commit_validated_results

_ACTIVE_ADVANCED_COMMITS: set["AdvancedCommitCoordinator"] = set()
_CONTEXT_HELP = "超出模型上下文或输出限制时，请减小 Batch Size。"


class AdvancedCommitCoordinator:
    def __init__(self, run_id, batch_result, ledger, sources, destinations,
                 cancel_event, *, tab=None, collection_parent=None):
        self.run_id = run_id
        self.batch_result = batch_result
        self.ledger = ledger
        self.sources = tuple(sources)
        self.destinations = tuple(destinations)
        self.cancel_event = cancel_event
        self._tab_ref = weakref.ref(tab) if tab is not None else lambda: None
        self._collection_parent = collection_parent
        self.phase = "FINALIZING"
        self._settled = False
        self._submission_possible = False

    def start(self):
        _ACTIVE_ADVANCED_COMMITS.add(self)
        tab = self._tab_ref()
        if (self.cancel_event.is_set() or
                (tab is not None and getattr(tab, "_advanced_closing", False))):
            self.ledger.stage_batch_result(self.batch_result, cancelled=True)
            self._settle("Generation cancelled.")
            return
        self.ledger.stage_batch_result(self.batch_result)
        if not self.batch_result.accepted:
            self._settle(self._generation_message())
            return

        if self.cancel_event.is_set():
            self.ledger.stage_batch_result(self.batch_result, cancelled=True)
            self._settle("Generation cancelled.")
            return

        try:
            from aqt import mw
            from aqt.operations import CollectionOp
            from anki.collection import OpChanges

            def operation(col):
                records = [(snapshot, values, None)
                           for snapshot, values in self.batch_result.accepted]
                return commit_validated_results(
                    col, records, self.sources, self.destinations,
                    self.cancel_event, OpChanges,
                )

            # A live application-level parent, never the possibly destroyed tab.
            parent = self._collection_parent or mw
            op = CollectionOp(parent=parent, op=operation)
            op.success(self._succeeded).failure(self._failed)
        except Exception:
            self.ledger.mark_commit_failure(submission_possible=False)
            self.ledger.add_issue("commit", "Could not prepare Anki CollectionOp.")
            self._settle("Advanced commit could not start.")
            return

        # The submission boundary is conservative: if run_in_background
        # raises, the operation might already be queued. Never claim no write.
        if self.cancel_event.is_set():
            self.ledger.stage_batch_result(self.batch_result, cancelled=True)
            self._settle("Generation cancelled.")
            return
        self.phase = "COMMITTING"
        self._submission_possible = True
        try:
            op.run_in_background(initiator=parent)
        except Exception:
            self._failed(RuntimeError("CollectionOp submission failed"))

    def _succeeded(self, result):
        if self._settled:
            return
        try:
            # A delivered CollectionOp result may itself be malformed or the
            # ledger may raise while applying it. The operation has already
            # run: all not-yet-classified accepted notes remain uncertain.
            self.ledger.apply_commit_result(result)
        except Exception:
            try:
                self.ledger.mark_commit_failure(submission_possible=True)
                self.ledger.add_issue(
                    "commit-result", "Could not interpret Anki commit result; "
                    "unclassified writes may already be persisted.")
            except Exception:
                # Even a broken ledger must not retain the coordinator forever.
                print("[AINotePro] Advanced commit ledger recovery failed.")
            self._settle("Advanced commit result could not be verified.")
            return
        try:
            if self.ledger.count("updated"):
                try:
                    from aqt import mw
                    mw.reset()
                except Exception:
                    self.ledger.add_issue("ui-refresh-failed", "Reopen the note to verify.")
        finally:
            # No UI/ledger diagnostic exception may prevent terminal cleanup.
            self._settle(self._generation_message())

    def _failed(self, _exc):
        if self._settled:
            return
        try:
            self.ledger.mark_commit_failure(submission_possible=self._submission_possible)
            self.ledger.add_issue("commit", "Anki commit callback failed; persistence may be uncertain.")
        finally:
            self._settle("Advanced commit failed.")

    def _generation_message(self):
        result = self.batch_result
        names = {
            "complete": "Advanced generation complete.",
            "no-progress": "Stopped after three requests without a new valid result.",
            "context-or-output-limit": "LLM context/output limit reported.",
            "auth": "LLM authentication or permission failure.",
            "invalid-model-or-endpoint": "LLM model or endpoint is unavailable.",
            "cancelled": "Generation cancelled.",
            "worker-failed": "Advanced generation worker failed.",
        }
        message = names.get(result.stop_reason, "Advanced generation stopped.")
        if result.safe_error:
            message += " " + result.safe_error
        if result.stop_reason == "context-or-output-limit":
            message += "\n" + _CONTEXT_HELP
        return message

    def _settle(self, message):
        if self._settled:
            return
        self._settled = True
        self.phase = "SETTLED"
        try:
            result = self.batch_result
            prefix = (
                f"{message}\nSelected {len(self.ledger.states)}; "
                f"validated {result.accepted_count}; "
                f"requests {result.request_count}; retries {result.retry_count}."
            )
            try:
                summary = self.ledger.summary(prefix)
                updated = self.ledger.count("updated")
            except Exception:
                # Keep the unknown persistence outcome visible even if ledger
                # presentation fails. The authoritative commit is never retried.
                summary = prefix + "\nCommit accounting unavailable; inspect Anki before retrying."
                updated = "unknown"
            print("[AINotePro] Advanced commit settled "
                  f"updated={updated} "
                  f"validated={result.accepted_count} "
                  f"requests={result.request_count} retries={result.retry_count}")
            tab = self._tab_ref()
            if tab is not None and not getattr(tab, "_advanced_closing", False):
                try:
                    if tab._advanced_run_id == self.run_id:
                        tab._advanced_coordinator_settled(self, summary)
                except Exception:
                    # Any UI-only failure, not just a destroyed native QWidget,
                    # must not affect the authoritative settled result.
                    print("[AINotePro] Advanced UI observer notification failed.")
        finally:
            # The coordinator is retained by a process-global strong-ref set.
            # A UI callback is untrusted and may never prevent its release.
            _ACTIVE_ADVANCED_COMMITS.discard(self)
