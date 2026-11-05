"""Exercise the real Text-tab library Import/Load methods without a Qt runtime.

Extracting the methods from the source AST ensures this test calls the actual
user-facing handlers, not a rewritten version of their logic.
"""
from __future__ import annotations

import ast
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ainotepro.config import manager
from ainotepro.config.audio_profiles import default_profile
from ainotepro.core.prompt_bundle import make_bundle, parse_bundle


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = ROOT / "ainotepro" / "ui" / "text_tab.py"
METHOD_NAMES = ("_on_import_prompt", "_github_loaded", "_finish_library_import")


def load_ui_methods(namespace):
    tree = ast.parse(UI_SOURCE.read_text(encoding="utf-8-sig"))
    widget = next(node for node in tree.body
                  if isinstance(node, ast.ClassDef) and node.name == "TextTab")
    methods = [node for node in widget.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name in METHOD_NAMES]
    if len(methods) != len(METHOD_NAMES):
        raise AssertionError("Missing one or more library UI handlers")
    module = ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[]))
    exec(compile(module, str(UI_SOURCE), "exec"), namespace)


class LibraryImportUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        changes = [
            patch.object(manager, "USER_FILES_DIR", self.root),
            patch.object(manager, "CONFIG_FILE", os.path.join(self.root, "user_config.json")),
            patch.object(manager, "LEGACY_USER_DATA_DIR",
                         os.path.join(self.root, "missing-legacy")),
        ]
        for p in changes:
            p.start()
            self.addCleanup(p.stop)
        self.store = manager.ConfigManager()
        self.messages = []
        self.refreshes = []
        self.path = os.path.join(self.root, "import.json")
        self.mirror_path = os.path.join(self.root, "gen_text", "prompt.json")

        def write_mirror(path, data):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)

        self.env = {
            "ConfigManager": lambda: self.store,
            "parse_bundle": parse_bundle,
            "QFileDialog": types.SimpleNamespace(
                getOpenFileName=lambda *args: (self.path, "JSON")),
            "PROMPT_FILE": self.mirror_path,
            "_write_json_file": write_mirror,
            "showInfo": lambda message: self.messages.append(("info", message)),
            "showWarning": lambda message: self.messages.append(("warning", message)),
            "json": json,
            "os": os,
        }
        load_ui_methods(self.env)
        self.widget = types.SimpleNamespace(
            _advanced_closing=False,
            _prompt_is_dirty=lambda: False,
            _audio_ready_for_library_transfer=lambda: True,
            _confirm_leave_prompt=lambda: True,
            _library_changed=lambda stats: self.refreshes.append(stats),
            _prompt_merge_summary=lambda stats: (
                f"Easy: {stats['easy']['added']}; Audio: {stats['audio_profiles']['added']}"
            ),
        )
        for name in METHOD_NAMES:
            setattr(self.widget, name, types.MethodType(self.env[name], self.widget))

        self.library = make_bundle(
            {"New easy": "Simple test"},
            {"New advanced": "{Text}"},
            [default_profile("New imported voice")],
        )
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump(self.library, stream)

    def _verify_committed(self):
        saved = self.store.library_snapshot()
        self.assertIn("New easy", saved["prompts"]["easy"])
        self.assertIn("New advanced", saved["prompts"]["advanced"])
        self.assertIn("New imported voice",
                      [p["name"] for p in saved["audio_profiles"]])
        return saved

    def test_local_import_uses_nested_easy_and_reports_success(self):
        self.widget._on_import_prompt()
        self._verify_committed()
        with open(self.mirror_path, "r", encoding="utf-8") as stream:
            mirror = json.load(stream)
        self.assertIn("New easy", mirror)
        self.assertNotIn("prompts", mirror)
        self.assertEqual([k for k, _ in self.messages], ["info"])
        self.assertEqual(len(self.refreshes), 1)

    def test_github_load_uses_nested_easy_and_is_idempotent(self):
        self.widget._github_loaded(self.library)
        first = self._verify_committed()
        self.widget._github_loaded(self.library)
        self.assertEqual(first, self.store.library_snapshot())
        self.assertEqual(len(self.refreshes), 2)
        self.assertEqual([k for k, _ in self.messages], ["info", "info"])

    def test_mirror_write_failure_does_not_claim_import_failed(self):
        def fail(*args):
            raise OSError("simulated legacy mirror error")
        self.env["_write_json_file"] = fail
        self.widget._github_loaded(self.library)
        self._verify_committed()
        self.assertEqual(len(self.messages), 1)
        kind, message = self.messages[0]
        self.assertEqual(kind, "warning")
        self.assertIn("imported successfully", message)
        self.assertIn("main configuration is already saved", message)
        self.assertNotIn("Could not import", message)

    def test_editor_refresh_failure_does_not_claim_import_failed(self):
        self.widget._library_changed = lambda stats: (_ for _ in ()).throw(
            RuntimeError("simulated view update failure")
        )
        self.widget._on_import_prompt()
        self._verify_committed()
        self.assertEqual(len(self.messages), 1)
        kind, message = self.messages[0]
        self.assertEqual(kind, "warning")
        self.assertIn("imported successfully", message)
        self.assertIn("Reopen AINotePro", message)

    def test_invalid_audio_prevents_any_commit(self):
        invalid = json.loads(json.dumps(self.library))
        invalid["audio_profiles"][0]["provider_configs"]["edge_tts"]["voices"][0]["speed"] = 999
        before = self.store.library_snapshot()
        self.widget._github_loaded(invalid)
        self.assertEqual(before, self.store.library_snapshot())
        self.assertEqual(self.messages[0][0], "warning")
        self.assertIn("Could not import the GitHub library", self.messages[0][1])
        self.assertEqual(len(self.refreshes), 0)


if __name__ == "__main__":
    unittest.main()
