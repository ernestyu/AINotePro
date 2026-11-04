"""Headless Note Type preflight and Text/Audio wiring regression tests."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from ainotepro.core.batch_note_types import validate_batch_note_types


ROOT = Path(__file__).resolve().parents[1]


class Note:
    def __init__(self, type_id, name, fields, *, template=None):
        self._type = {"id": type_id, "name": name,
                      "flds": [{"name": field} for field in fields]}
        self.template = template

    def note_type(self):
        return self._type


class BatchNoteTypeTests(unittest.TestCase):
    def test_uniform_note_type_accepts_multiple_notes(self):
        notes = {i: Note(10, "Basic", ["Text", "Audio"]) for i in range(1, 102)}
        self.assertEqual(validate_batch_note_types(list(notes), notes.__getitem__,
                                                   ["Text", "Audio"]), 10)

    def test_different_card_templates_with_same_note_type_are_allowed(self):
        notes = {
            1: Note(10, "Basic and Reversed", ["Front", "Back"], template="Card 1"),
            2: Note(10, "Basic and Reversed", ["Front", "Back"], template="Card 2"),
        }
        self.assertEqual(validate_batch_note_types([1, 2], notes.__getitem__,
                                                   ["Front", "Back"]), 10)

    def test_distinct_note_types_with_identical_fields_are_rejected(self):
        notes = {1: Note(10, "Basic", ["Text", "Out"]),
                 2: Note(11, "Custom Basic", ["Text", "Out"])}
        with self.assertRaisesRegex(ValueError, "different Note Types.*No generation started"):
            validate_batch_note_types([1, 2], notes.__getitem__, ["Text", "Out"])

    def test_mismatch_at_end_of_batch_is_rejected(self):
        notes = {i: Note(10, "Basic", ["Text", "Out"]) for i in range(1, 51)}
        notes[51] = Note(11, "Cloze", ["Text", "Out"])
        with self.assertRaisesRegex(ValueError, "note 51"):
            validate_batch_note_types(list(notes), notes.__getitem__, ["Text", "Out"])

    def test_stale_destination_field_is_rejected(self):
        notes = {1: Note(10, "Basic", ["Text", "Out"])}
        with self.assertRaisesRegex(ValueError, "missing field.*Audio"):
            validate_batch_note_types([1], notes.__getitem__, ["Text", "Audio"])

    def test_inconsistent_schema_is_rejected(self):
        notes = {1: Note(10, "Basic", ["Text", "Out"]),
                 2: Note(10, "Basic", ["Out", "Text"])}
        with self.assertRaisesRegex(ValueError, "inconsistent field definitions"):
            validate_batch_note_types([1, 2], notes.__getitem__, ["Text", "Out"])

    def test_unreadable_note_fails_closed(self):
        notes = {1: Note(10, "Basic", ["Text", "Out"])}
        with self.assertRaisesRegex(ValueError, "Could not inspect selected note 2"):
            validate_batch_note_types([1, 2], notes.__getitem__, ["Text", "Out"])

    def test_empty_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, "No notes selected"):
            validate_batch_note_types([], lambda _id: None)

    def test_preflight_is_before_easy_text_ocr_batch_and_side_effects(self):
        source = (ROOT / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        start = source.index("    def on_generate_text")
        end = source.index("    def _start_advanced_generation", start)
        body = source[start:end]
        check = body.index("validate_batch_note_types(")
        self.assertLess(check, body.index("self._confirm_write_risk("))
        self.assertLess(check, body.index("self._model_selection_changed()"))
        self.assertLess(check, body.index("if self.image_checkbox"))
        self.assertLess(check, body.index("create_undo_checkpoint("))

    def test_preflight_is_before_audio_batch_and_confirmation(self):
        source = (ROOT / "ainotepro/ui/tts_tab.py").read_text(encoding="utf-8")
        start = source.index("    def on_generate_tts")
        end = source.index("    def _count(", start)
        body = source[start:end]
        check = body.index("validate_batch_note_types(")
        self.assertLess(check, body.index("self._confirm_write_risk("))
        self.assertLess(check, body.index("self._snapshot ="))


if __name__ == "__main__":
    unittest.main()
