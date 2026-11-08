"""Batch Size storage isolation and minimal Advanced-only UI wiring."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from ainotepro.config.manager import ConfigManager, _get_default_config


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")


class AdvancedBatchConfigTests(unittest.TestCase):
    def test_default_and_strict_range(self):
        self.assertEqual(_get_default_config()["text"]["advanced_batch_size"], 1)
        instance = object.__new__(ConfigManager)
        raw = {"text": {"field_mode": "advanced", "prompts": {"A": "B"}},
               "audio": {"provider": "edge_tts"}}
        def replace_raw(callback):
            callback(raw)
        with patch.object(instance, "_replace_raw", replace_raw):
            for value in (False, True, 0, -1, 100, 1.5, "10", None):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    instance.update_text_fields({"advanced_batch_size": value})
            instance.update_text_fields({"advanced_batch_size": 99})
        self.assertEqual(raw["text"]["advanced_batch_size"], 99)
        self.assertEqual(raw["text"]["prompts"], {"A": "B"})
        self.assertEqual(raw["audio"], {"provider": "edge_tts"})

    def test_advanced_only_compact_control_and_single_easy_worker(self):
        tree = ast.parse(SOURCE)
        tab = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == "TextTab")
        method = next(x for x in tab.body if isinstance(x, ast.FunctionDef)
                      and x.name == "_update_field_mode_widgets")
        body = ast.get_source_segment(SOURCE, method)
        self.assertIn("self.image_checkbox.setVisible(not advanced)", body)
        self.assertIn("self.batch_size_combo.setVisible(advanced)", body)
        self.assertIn("self.batch_size_label.setVisible(advanced)", body)
        self.assertIn('range(1, 11)', SOURCE)
        self.assertIn('self.batch_size_combo.setEditable(True)', SOURCE)
        self.assertIn('self.batch_size_combo.lineEdit().setMaxLength(2)', SOURCE)
        self.assertIn('QIntValidator(1, 99', SOURCE)
        self.assertIn('self.batch_size_combo.setFixedWidth(65)', SOURCE)
        self.assertNotIn('resolve_invalid_fields_button', SOURCE)
        self.assertIn('max_workers = 1', SOURCE)

    def test_user_entered_value_is_saved_and_invalid_values_restore(self):
        tree = ast.parse(SOURCE)
        tab_class = next(node for node in tree.body
                         if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method_names = {"_commit_batch_size", "_restore_batch_size",
                        "_on_batch_size_activated"}
        methods = [node for node in tab_class.body if isinstance(node, ast.FunctionDef)
                   and node.name in method_names]
        module = ast.Module(body=[ast.ClassDef(name="BatchEditor", bases=[],
                            keywords=[], body=methods, decorator_list=[])], type_ignores=[])
        warnings = []
        scope = {"showWarning": warnings.append}
        exec(compile(ast.fix_missing_locations(module), "<batch editor>", "exec"), scope)
        class Combo:
            def __init__(self):
                self.text = "1"
            def currentText(self):
                return self.text
            def setCurrentText(self, value):
                self.text = value
            def blockSignals(self, _blocked):
                pass
            def lineEdit(self):
                return self
        class Config:
            def __init__(self):
                self.saved = []
                self.fail = False
            def update_text_fields(self, values):
                if self.fail:
                    raise OSError("unavailable")
                self.saved.append(values)
        tab = scope["BatchEditor"]()
        tab.batch_size_combo = Combo()
        tab.cfg = Config()
        tab._saved_batch_size = 1
        for value in ("50", "99", "11", "2"):
            tab.batch_size_combo.text = value
            self.assertTrue(tab._commit_batch_size())
            self.assertEqual(tab._saved_batch_size, int(value))
            self.assertEqual(tab.batch_size_combo.text, value)
        self.assertEqual(tab.cfg.saved, [{"advanced_batch_size": v}
                                         for v in (50, 99, 11, 2)])
        for invalid in ("0", "100", "-1", "1.5", "x", "", "１２"):
            tab.batch_size_combo.text = invalid
            self.assertFalse(tab._commit_batch_size())
            self.assertEqual(tab.batch_size_combo.text, "2")
        self.assertEqual(len(warnings), 7)
        tab.cfg.fail = True
        tab.batch_size_combo.text = "42"
        self.assertFalse(tab._commit_batch_size())
        self.assertEqual(tab._saved_batch_size, 2)
        self.assertEqual(tab.batch_size_combo.text, "2")
        self.assertIn("Could not save", warnings[-1])

    def test_field_selector_handles_unavailable_items_without_resolve_widget(self):
        self.assertIn("missing_source = [name for name in saved_source", SOURCE)
        self.assertIn("names + missing_source, source, set(destination)", SOURCE)
        self.assertIn("names + missing_destination, destination, set(source)", SOURCE)
        self.assertIn("uncheck to remove", SOURCE)


if __name__ == "__main__":
    unittest.main()
