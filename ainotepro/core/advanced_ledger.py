"""Deterministic, Qt-free terminal accounting for one Advanced batch."""
from __future__ import annotations

from dataclasses import dataclass, field


_PENDING = {"pending", "validated"}


@dataclass
class AdvancedBatchLedger:
    """Ensure every selected note has exactly one terminal batch outcome."""

    states: dict[int, str]
    details: list[str] = field(default_factory=list)

    @classmethod
    def for_notes(cls, note_ids):
        return cls({int(note_id): "pending" for note_id in note_ids})

    def record_worker(self, note_id: int, category: str | None, detail: str | None) -> None:
        if note_id not in self.states or self.states[note_id] != "pending":
            return
        if category:
            self.states[note_id] = category
            if detail:
                self.details.append(f"Note {note_id}: {detail}")
        else:
            self.states[note_id] = "validated"

    def cancel_pending(self) -> None:
        for note_id, state in self.states.items():
            if state in _PENDING:
                self.states[note_id] = "cancelled"

    def mark_pending(self, status: str, detail: str | None = None) -> None:
        for note_id, state in self.states.items():
            if state in _PENDING:
                self.states[note_id] = status
        if detail:
            self.details.append(detail)

    def apply_commit_result(self, result) -> None:
        """Apply commit outcomes and classify every not-submitted validated note."""
        for note_id, status in result.outcomes:
            if note_id in self.states and self.states[note_id] == "validated":
                self.states[note_id] = status
        remaining = [note_id for note_id, state in self.states.items() if state in _PENDING]
        if result.fatal_error:
            self.details.append(result.fatal_error)
            # A fatal status without a corresponding per-note outcome means no
            # validated note was entered (for example undo unavailable). If a
            # note already has that terminal state, the rest were deliberately
            # not submitted after the unsafe condition was discovered.
            if result.fatal_status not in {status for _note_id, status in result.outcomes}:
                for note_id in remaining:
                    self.states[note_id] = result.fatal_status or "commit-uncertain"
            else:
                for note_id in remaining:
                    self.states[note_id] = "not-submitted"
        elif remaining:
            self.mark_pending("commit-task-failed", "Commit returned without a terminal result for every note.")

    def add_issue(self, category: str, detail: str) -> None:
        self.details.append(f"{category}: {detail}")

    def count(self, status: str) -> int:
        return sum(state == status for state in self.states.values())

    def summary(self, prefix: str) -> str:
        counts: dict[str, int] = {}
        for state in self.states.values():
            counts[state] = counts.get(state, 0) + 1
        updated = counts.pop("updated", 0)
        summary = f"{prefix} Updated {updated} notes."
        if counts:
            summary += "\n\nResults: " + ", ".join(
                f"{status}={count}" for status, count in sorted(counts.items())
            )
        if self.details:
            summary += "\n" + "\n".join(self.details[:8])
        return summary
