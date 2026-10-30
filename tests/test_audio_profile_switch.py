"""Headless regression tests for Audio Profile switching.

Only selected TTSTab methods are extracted from the production source AST,
so these tests need neither Anki nor Qt. They check transition and persistence
logic, not visual rendering or live TTS provider behavior.
"""
from __future__ import annotations

import ast
import copy
from enum import IntFlag
from pathlib import Path
import unittest


class Buttons(IntFlag):
    Save = 1
    Discard = 2
    Cancel = 4


class MessageBox:
    StandardButton = Buttons
    response = Buttons.Cancel
    calls = 0

    @classmethod
    def question(cls, *_args):
        cls.calls += 1
        return cls.response


WARNINGS = []


def load_profile_methods():
    source_path = Path(__file__).resolve().parents[1] / "ainotepro" / "ui" / "tts_tab.py"
    source = source_path.read_text(encoding="utf-8")
    assert 'self.profile_combo.currentIndexChanged.connect(self._on_profile_selection_changed)' in source
    assert '("Load", self.load_profile)' not in source
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TTSTab")
    names = {"_restore_profile_selection", "_confirm_profile_switch",
             "_on_profile_selection_changed", "_activate_profile"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    module = ast.Module(body=[ast.ClassDef(name="ProfileMethods", bases=[], keywords=[],
                                          body=methods, decorator_list=[])], type_ignores=[])
    namespace = {"copy": copy, "QMessageBox": MessageBox, "showWarning": WARNINGS.append}
    exec(compile(ast.fix_missing_locations(module), str(source_path), "exec"), namespace)
    return namespace["ProfileMethods"]


ProfileMethods = load_profile_methods()


class Combo:
    def itemData(self, index):
        return {0: None, 1: "a", 2: "b"}.get(index)


class Config:
    def __init__(self):
        self.revision = "r0"
        self.fail = False
        self.writes = []

    def replace_audio(self, audio, expected_revision):
        if self.fail:
            raise RuntimeError("concurrent Audio update")
        if expected_revision != self.revision:
            raise RuntimeError("stale revision")
        self.writes.append(copy.deepcopy(audio))
        self.revision += "x"
        return self.revision


class Tab(ProfileMethods):
    def __init__(self):
        self._audio = {
            "profiles": {
                "a": {"name": "Alpha", "provider": "edge_tts", "value": 1},
                "b": {"name": "Beta", "provider": "kokoro_gradio", "value": 2},
            },
            "last_profile_id": "a",
        }
        self._profile_id = "a"
        self._draft = copy.deepcopy(self._audio["profiles"]["a"])
        self._saved = copy.deepcopy(self._draft)
        self._revision = "r0"
        self._loading = False
        self.profile_combo = Combo()
        self.cfg = Config()
        self.display_name = "Alpha"
        self.applies = 0
        self.saves = []

    def _is_dirty(self):
        return self._draft != self._saved

    def _refresh_profiles(self, name=None):
        self.display_name = name

    def _apply_draft(self):
        self.applies += 1

    def _save(self, profile_id, profile):
        self.saves.append((profile_id, copy.deepcopy(profile)))
        audio = copy.deepcopy(self._audio)
        audio["profiles"][profile_id] = copy.deepcopy(profile)
        audio["last_profile_id"] = profile_id
        self._revision = self.cfg.replace_audio(audio, expected_revision=self._revision)
        self._audio = audio
        self._profile_id = profile_id
        self._draft = copy.deepcopy(profile)
        self._saved = copy.deepcopy(profile)
        self._refresh_profiles(profile["name"])
        return True


class AudioProfileSwitchTests(unittest.TestCase):
    def setUp(self):
        MessageBox.response = Buttons.Cancel
        MessageBox.calls = 0
        WARNINGS.clear()
        self.tab = Tab()

    def make_dirty(self):
        self.tab._draft["value"] = 42

    def test_clean_selection_loads_and_persists_immediately(self):
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab._profile_id, "b")
        self.assertEqual(self.tab._draft["value"], 2)
        self.assertEqual(self.tab._audio["last_profile_id"], "b")
        self.assertEqual(self.tab.applies, 1)
        self.assertEqual(MessageBox.calls, 0)

    def test_save_changes_to_previous_profile_not_target(self):
        self.make_dirty()
        MessageBox.response = Buttons.Save
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab.saves[0][0], "a")
        self.assertEqual(self.tab._audio["profiles"]["a"]["value"], 42)
        self.assertEqual(self.tab._audio["profiles"]["b"]["value"], 2)
        self.assertEqual(self.tab._profile_id, "b")
        self.assertEqual(self.tab._audio["last_profile_id"], "b")
        self.assertEqual(len(self.tab.cfg.writes), 2)

    def test_discard_changes_and_load_target(self):
        self.make_dirty()
        MessageBox.response = Buttons.Discard
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab._audio["profiles"]["a"]["value"], 1)
        self.assertEqual(self.tab._profile_id, "b")
        self.assertEqual(len(self.tab.cfg.writes), 1)

    def test_cancel_restores_selection_and_keeps_draft(self):
        self.make_dirty()
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab.display_name, "Alpha")
        self.assertEqual(self.tab._profile_id, "a")
        self.assertEqual(self.tab._draft["value"], 42)
        self.assertEqual(len(self.tab.cfg.writes), 0)

    def test_failed_switch_restores_old_profile(self):
        self.tab.cfg.fail = True
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab.display_name, "Alpha")
        self.assertEqual(self.tab._profile_id, "a")
        self.assertEqual(self.tab.applies, 0)
        self.assertEqual(self.tab._audio["last_profile_id"], "a")
        self.assertTrue(WARNINGS)

    def test_typed_name_and_same_selection_do_not_load(self):
        self.tab._on_profile_selection_changed(-1)
        self.tab._on_profile_selection_changed(1)
        self.assertEqual(self.tab.applies, 0)
        self.assertEqual(len(self.tab.cfg.writes), 0)

    def test_unsaved_unattached_draft_cannot_be_saved_into_target(self):
        self.make_dirty()
        self.tab._profile_id = None
        MessageBox.response = Buttons.Save
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab._draft["value"], 42)
        self.assertEqual(self.tab._profile_id, None)
        self.assertEqual(len(self.tab.cfg.writes), 0)
        self.assertTrue(WARNINGS)

    def test_save_failure_keeps_previous_draft(self):
        self.make_dirty()
        self.tab.cfg.fail = True
        MessageBox.response = Buttons.Save
        self.tab._on_profile_selection_changed(2)
        self.assertEqual(self.tab._draft["value"], 42)
        self.assertEqual(self.tab._audio["profiles"]["a"]["value"], 1)
        self.assertEqual(self.tab.display_name, "Alpha")
        self.assertEqual(self.tab._profile_id, "a")
        self.assertTrue(WARNINGS)


if __name__ == "__main__":
    unittest.main()
