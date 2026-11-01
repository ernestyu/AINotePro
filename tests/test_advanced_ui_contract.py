"""Static safety checks for the Anki-bound Advanced UI path.

The Qt/Anki runtime is intentionally not imported by the repository test
environment, so this covers structural guarantees that are otherwise only
exercisable in a live Anki profile.
"""
from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")


class AdvancedUiContractTests(unittest.TestCase):
    def test_advanced_dispatch_precedes_easy_ocr_path(self):
        start = SOURCE.index("    def on_generate_text")
        ocr = SOURCE.index("if self.image_checkbox", start)
        advanced = SOURCE.index("if self._field_mode == \"advanced\"", start)
        self.assertLess(advanced, ocr)

    def test_final_commit_uses_collection_op_and_single_note_update(self):
        start = SOURCE.index("    def _commit_advanced_results")
        end = SOURCE.index("    def _finish_advanced_ui", start)
        body = SOURCE[start:end]
        self.assertIn("CollectionOp", body)
        self.assertIn("snapshot_matches", body)
        self.assertIn("changes = col.update_note(note)", body)
        self.assertNotIn("update_field_content", body)
        self.assertNotIn("await ", body)

    def test_advanced_selection_and_prompt_namespaces_are_separate(self):
        self.assertIn("CheckableFieldCombo", SOURCE)
        self.assertIn("advanced_prompts", (Path(__file__).resolve().parents[1] / "ainotepro/config/manager.py").read_text())
        self.assertIn("self.image_checkbox.setVisible(not advanced)", SOURCE)


if __name__ == "__main__":
    unittest.main()
