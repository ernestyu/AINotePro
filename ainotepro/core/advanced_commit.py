"""Anki-facing Advanced Text commit protocol, kept Qt-independent for tests.

The caller must invoke :func:`commit_validated_results` from a serialized
``CollectionOp``.  This module intentionally does not import Anki: tests pass
small collection/OpChanges doubles, while the UI supplies Anki's real types.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .advanced_text import snapshot_matches


@dataclass
class AdvancedCommitResult:
    """CollectionOp-compatible result and per-note outcomes."""

    changes: Any
    outcomes: list[tuple[int, str]]
    fatal_error: str | None = None
    fatal_status: str | None = None


def _merge_changes(target: Any, incoming: Any) -> None:
    """Accumulate every update's OpChanges for CollectionOp notifications."""
    if incoming is None:
        raise ValueError("Anki update returned no OpChanges")
    merge = getattr(target, "MergeFrom", None)
    if not callable(merge):
        raise TypeError("OpChanges does not provide MergeFrom()")
    merge(incoming)


def _persistence_after_update_error(col: Any, snapshot: Any,
                                    destinations: tuple[str, ...],
                                    values: dict[str, str]) -> bool | None:
    """Return whether a failed update is observably persisted, or ``None``.

    A raising backend call can occur after persistence.  A re-read can prove a
    changed target value was *not* retained, but cannot prove anything when the
    generated values equal the snapshot's existing targets or the re-read
    itself fails.  Those cases deliberately remain indeterminate.
    """
    if not any(snapshot.raw_values[name] != values[name] for name in destinations):
        return None
    try:
        note = col.get_note(snapshot.note_id)
        return all(name in note and note[name] == values[name] for name in destinations)
    except Exception:
        return None


def commit_validated_results(
    col: Any,
    valid_results: Iterable[tuple[Any, dict[str, str], Any]],
    sources: tuple[str, ...],
    destinations: tuple[str, ...],
    cancel_event: Any,
    changes_factory: Callable[[], Any],
) -> AdvancedCommitResult:
    """Commit complete per-note results without yielding collection ownership.

    A single custom undo entry is created before any update. Each note is
    re-read, checked, populated with *all* destination values and updated once.
    ``merge_undo_entries()`` is required after every update. A merge failure
    after a successful ``update_note()`` is *not* a rollback: the note may
    already be durable while its undo state is unknown. That condition is
    reported as ``persisted-undo-uncertain`` and stops the batch. The
    surrounding CollectionOp provides the serialized execution context; this
    function must not be called from a provider/Qt worker.
    """
    changes = changes_factory()
    outcomes: list[tuple[int, str]] = []
    add_undo = getattr(col, "add_custom_undo_entry", None)
    merge_undo = getattr(col, "merge_undo_entries", None)
    if not callable(add_undo) or not callable(merge_undo):
        return AdvancedCommitResult(
            changes, outcomes,
            "Anki undo grouping API is unavailable; no Advanced results were written.",
            "undo-unavailable",
        )
    if cancel_event.is_set():
        return AdvancedCommitResult(changes, outcomes)
    try:
        undo_id = add_undo("AINotePro advanced text generation")
    except Exception as exc:
        return AdvancedCommitResult(
            changes, outcomes,
            f"Could not create Anki undo group; no Advanced results were written: {exc}",
            "undo-create-failed",
        )

    for snapshot, values, _error in valid_results:
        # This is the final cancellation gate before the no-yield re-read,
        # comparison, field assignment and supported Anki update call.
        if cancel_event.is_set():
            outcomes.append((snapshot.note_id, "cancelled"))
            continue
        try:
            note = col.get_note(snapshot.note_id)
            note_type = note.note_type()
            names = [field["name"] for field in note_type["flds"]]
            raw = {name: note[name] for name in set(sources + destinations) if name in note}
            if not snapshot_matches(note_type["id"], names, raw, snapshot, sources, destinations):
                outcomes.append((snapshot.note_id, "conflict"))
                continue
            if cancel_event.is_set():
                outcomes.append((snapshot.note_id, "cancelled"))
                continue
            for name in destinations:
                note[name] = values[name]
        except Exception as exc:
            persisted = _persistence_after_update_error(col, snapshot, destinations, values)
            if persisted is False:
                outcomes.append((snapshot.note_id, "commit-failed"))
                continue
            outcomes.append((snapshot.note_id, "commit-uncertain"))
            return AdvancedCommitResult(
                changes, outcomes,
                f"Commit for note {snapshot.note_id} raised an error and persistence could not "
                f"be ruled out: {exc}. No later notes were submitted; this was not rolled back.",
                "commit-uncertain",
            )
        try:
            _merge_changes(changes, col.update_note(note))
        except Exception as exc:
            persisted = _persistence_after_update_error(col, snapshot, destinations, values)
            if persisted is False:
                outcomes.append((snapshot.note_id, "commit-failed"))
                continue
            outcomes.append((snapshot.note_id, "commit-uncertain"))
            return AdvancedCommitResult(
                changes, outcomes,
                f"Commit for note {snapshot.note_id} raised an error and persistence could not "
                f"be ruled out: {exc}. No later notes were submitted; this was not rolled back.",
                "commit-uncertain",
            )
        try:
            # A successful update has already been submitted. If this merge
            # raises, Anki has not promised a rollback; never label it failed.
            _merge_changes(changes, merge_undo(undo_id))
        except Exception as exc:
            outcomes.append((snapshot.note_id, "persisted-undo-uncertain"))
            return AdvancedCommitResult(
                changes, outcomes,
                f"Note {snapshot.note_id} was updated before Anki Undo grouping failed: {exc}. "
                "Its data may be persisted and Undo state is uncertain; it was not rolled back. "
                "No later notes were submitted; inspect Anki before retrying or undoing.",
                "persisted-undo-uncertain",
            )
        outcomes.append((snapshot.note_id, "updated"))
    return AdvancedCommitResult(changes, outcomes)
