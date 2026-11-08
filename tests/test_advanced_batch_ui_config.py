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
        self.assertEqual(_get_default_config()["text"]["advanced_batch_size"], 10)
        instance = object.__new__(ConfigManager)
        raw = {"text": {"field_mode": "advanced", "prompts": {"A": "B"}},
               "audio": {"provider": "edge_tts"}}
        def replace_raw(callback):
            callback(raw)
        with patch.object(instance, "_replace_raw", replace_raw):
            for value in (False, True, 0, 21, 1.5, "10", None):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    instance.update_text_fields({"advanced_batch_size": value})
            instance.update_text_fields({"advanced_batch_size": 20})
        self.assertEqual(raw["text"]["advanced_batch_size"], 20)
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
        self.assertIn('range(1, 21)', SOURCE)
        self.assertIn('self.batch_size_combo.setFixedWidth(65)', SOURCE)
        self.assertIn('max_workers = 1', SOURCE)


if __name__ == "__main__":
    unittest.main()
