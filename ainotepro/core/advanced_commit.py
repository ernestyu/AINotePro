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


def _merge_changes(target: Any, incoming: Any) -> None:
    """Accumulate every update's OpChanges for CollectionOp notifications."""
    if incoming is None:
        raise ValueError("Anki update returned no OpChanges")
    merge = getattr(target, "MergeFrom", None)
    if not callable(merge):
        raise TypeError("OpChanges does not provide MergeFrom()")
    merge(incoming)


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
    ``merge_undo_entries()`` is required after every update, so a missing or
    failed undo contract stops the batch rather than reporting an unsafe write
    as success. The surrounding CollectionOp provides the serialized execution
    context; this function must not be called from a provider/Qt worker.
    """
    changes = changes_factory()
    outcomes: list[tuple[int, str]] = []
    add_undo = getattr(col, "add_custom_undo_entry", None)
    merge_undo = getattr(col, "merge_undo_entries", None)
    if not callable(add_undo) or not callable(merge_undo):
        return AdvancedCommitResult(
            changes, outcomes,
            "Anki undo grouping API is unavailable; no Advanced results were written.",
        )
    if cancel_event.is_set():
        return AdvancedCommitResult(changes, outcomes)
    try:
        undo_id = add_undo("AINotePro advanced text generation")
    except Exception as exc:
        return AdvancedCommitResult(
            changes, outcomes,
            f"Could not create Anki undo group; no Advanced results were written: {exc}",
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
            _merge_changes(changes, col.update_note(note))
            # Anki's supported custom undo API merges this note update into the
            # entry created above. Do not claim success if this step fails.
            _merge_changes(changes, merge_undo(undo_id))
            outcomes.append((snapshot.note_id, "updated"))
        except Exception as exc:
            outcomes.append((snapshot.note_id, "commit-failed"))
            return AdvancedCommitResult(
                changes, outcomes,
                f"Commit for note {snapshot.note_id} could not be verified: {exc}. "
                "No later notes were submitted; inspect Anki before retrying.",
            )
    return AdvancedCommitResult(changes, outcomes)
