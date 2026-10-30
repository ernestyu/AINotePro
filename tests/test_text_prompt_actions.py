"""Headless regression tests for Text prompt actions (no Anki/Qt needed)."""
import ast
import copy
from enum import IntFlag
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
assert "online_button" not in SOURCE
assert "self.new_button" in SOURCE and "self.save_as_button" in SOURCE
assert 'data.get("Default") != _load_prompts()["Default"]' in SOURCE

STORE = {}
WARNINGS, INFOS, LAST_USED = [], [], []


def load_prompts():
    return copy.deepcopy(STORE)


def save_prompts(data):
    if data.get("Default") != STORE["Default"]:
        raise ValueError("Default protected")
    STORE.clear()
    STORE.update(copy.deepcopy(data))


class Buttons(IntFlag):
    Yes = 1
    No = 2
    Save = 4
    Discard = 8
    Cancel = 16


class MessageBox:
    StandardButton = Buttons
    response = Buttons.Cancel
    offered = []

    @classmethod
    def question(cls, _parent, _title, _message, buttons, *_args):
        cls.offered.append(buttons)
        return cls.response


class InputDialog:
    next_name = ""
    accepted = True

    @classmethod
    def getText(cls, *_args, **_kwargs):
        return cls.next_name, cls.accepted


class Editor:
    def __init__(self):
        self.value = ""
    def toPlainText(self):
        return self.value
    def setPlainText(self, text):
        self.value = text
    def clear(self):
        self.value = ""
    def setFocus(self):
        pass


class Combo:
    def __init__(self):
        self.items = ["Default", "Alpha", "Beta"]
        self.current = "Default"
        self.index = 0
    def itemText(self, index):
        return self.items[index]
    def findText(self, name):
        return self.items.index(name) if name in self.items else -1
    def setCurrentIndex(self, index):
        self.index = index
        self.current = self.items[index] if index >= 0 else ""
    def setEditText(self, name):
        self.current = name


class Button:
    def __init__(self):
        self.enabled = True
    def setEnabled(self, enabled):
        self.enabled = enabled


names = {
    "_restore_prompt_selector", "_update_prompt_actions", "_prompt_is_dirty",
    "_confirm_leave_prompt", "_on_prompt_selection_changed", "_load_prompt_by_name",
    "_valid_new_prompt_name", "_set_new_prompt_draft", "_on_new_prompt",
    "_save_prompt_to_name", "_on_save_prompt", "_on_save_as_prompt", "_on_delete_prompt",
}
tree = ast.parse(SOURCE)
tab_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TextTab")
methods = [n for n in tab_node.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in methods} == names
subset = ast.Module(body=[ast.ClassDef(name="PromptMethods", bases=[], keywords=[],
                                       body=methods, decorator_list=[])], type_ignores=[])
scope = {
    "QMessageBox": MessageBox, "QInputDialog": InputDialog,
    "showWarning": WARNINGS.append, "showInfo": INFOS.append,
    "_load_prompts": load_prompts, "_save_prompts": save_prompts,
    "_set_last_used_prompt": LAST_USED.append,
    "Optional": __import__("typing").Optional,
}
exec(compile(ast.fix_missing_locations(subset), "<text prompt methods>", "exec"), scope)
PromptMethods = scope["PromptMethods"]


class Tab(PromptMethods):
    def __init__(self):
        self.prompt_edit = Editor()
        self.prompt_list_combo = Combo()
        self.save_button = Button()
        self.delete_button = Button()
        self._is_updating_prompt_combo = False
        self._active_prompt_name = "Default"
        self._new_prompt_name = None
        self._saved_prompt_text = STORE["Default"]
        self.prompt_edit.value = STORE["Default"]
        self.all_prompts = load_prompts()
        self.provider_saves = 0
        self._update_prompt_actions()
    def _refresh_prompt_combo_after_save(self, name):
        self.prompt_list_combo.items = list(self.all_prompts)
        self.prompt_list_combo.current = name
    def _save_current_provider_config(self):
        self.provider_saves += 1


class TextPromptActionTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        STORE.update({"Default": "Original", "Alpha": "Alpha original", "Beta": "Beta original"})
        WARNINGS.clear()
        INFOS.clear()
        LAST_USED.clear()
        MessageBox.response = Buttons.Cancel
        MessageBox.offered.clear()
        InputDialog.next_name = "New Prompt"
        InputDialog.accepted = True
        self.tab = Tab()

    def test_default_cannot_save_or_delete(self):
        self.tab.prompt_edit.value = "Changed Default"
        self.tab._on_save_prompt()
        self.tab._on_delete_prompt()
        self.assertEqual(STORE["Default"], "Original")
        self.assertFalse(self.tab.save_button.enabled)
        self.assertFalse(self.tab.delete_button.enabled)

    def test_save_as_from_default_creates_copy(self):
        InputDialog.next_name = "Default Copy"
        self.tab.prompt_edit.value = "Custom"
        self.tab._on_save_as_prompt()
        self.assertEqual(STORE["Default"], "Original")
        self.assertEqual(STORE["Default Copy"], "Custom")
        self.assertEqual(self.tab._active_prompt_name, "Default Copy")

    def test_new_creates_blank_unsaved_draft(self):
        InputDialog.next_name = "Brand New"
        self.tab._on_new_prompt()
        self.assertEqual(self.tab.prompt_edit.value, "")
        self.assertEqual(self.tab._new_prompt_name, "Brand New")
        self.assertEqual(self.tab.prompt_list_combo.index, -1)
        self.assertNotIn("Brand New", STORE)
        self.assertTrue(self.tab.save_button.enabled)

    def test_save_new_then_update_same_prompt(self):
        self.tab._on_new_prompt()
        self.tab.prompt_edit.value = "First"
        self.tab._on_save_prompt()
        self.assertEqual(STORE["New Prompt"], "First")
        self.tab.prompt_edit.value = "Updated"
        MessageBox.response = Buttons.Yes
        self.tab._on_save_prompt()
        self.assertEqual(STORE["New Prompt"], "Updated")
        self.assertEqual(STORE["Default"], "Original")

    def test_save_as_rejects_existing_name(self):
        InputDialog.next_name = "Alpha"
        self.tab._on_save_as_prompt()
        self.assertEqual(STORE["Alpha"], "Alpha original")
        self.assertTrue(WARNINGS)

    def test_new_rejects_existing_name_case_insensitive(self):
        InputDialog.next_name = "alpha"
        self.tab._on_new_prompt()
        self.assertIsNone(self.tab._new_prompt_name)
        self.assertTrue(WARNINGS)

    def test_dirty_switch_save_updates_original_only(self):
        self.tab._load_prompt_by_name("Alpha")
        self.tab.prompt_edit.value = "Changed Alpha"
        MessageBox.response = Buttons.Save
        self.tab._on_prompt_selection_changed(2)
        self.assertEqual(STORE["Alpha"], "Changed Alpha")
        self.assertEqual(STORE["Beta"], "Beta original")
        self.assertEqual(self.tab._active_prompt_name, "Beta")
        self.assertEqual(self.tab.prompt_list_combo.current, "Beta")

    def test_dirty_switch_cancel_keeps_original_draft(self):
        self.tab._load_prompt_by_name("Alpha")
        self.tab.prompt_edit.value = "Uncommitted"
        self.tab._on_prompt_selection_changed(2)
        self.assertEqual(self.tab._active_prompt_name, "Alpha")
        self.assertEqual(self.tab.prompt_edit.value, "Uncommitted")
        self.assertEqual(self.tab.prompt_list_combo.current, "Alpha")
        self.assertEqual(STORE["Alpha"], "Alpha original")

    def test_dirty_default_switch_only_discard_or_cancel(self):
        self.tab.prompt_edit.value = "Unsaved Default"
        self.tab._on_prompt_selection_changed(1)
        self.assertEqual(self.tab._active_prompt_name, "Default")
        self.assertFalse(MessageBox.offered[-1] & Buttons.Save)
        MessageBox.response = Buttons.Discard
        self.tab._on_prompt_selection_changed(1)
        self.assertEqual(self.tab._active_prompt_name, "Alpha")
        self.assertEqual(STORE["Default"], "Original")

    def test_delete_saved_prompt_returns_to_default(self):
        self.tab._load_prompt_by_name("Alpha")
        MessageBox.response = Buttons.Yes
        self.tab._on_delete_prompt()
        self.assertNotIn("Alpha", STORE)
        self.assertEqual(self.tab._active_prompt_name, "Default")
        self.assertEqual(self.tab.prompt_edit.value, "Original")

    def test_unsaved_new_draft_switch_can_save_first(self):
        self.tab._on_new_prompt()
        self.tab.prompt_edit.value = "New draft content"
        MessageBox.response = Buttons.Save
        self.tab._on_prompt_selection_changed(1)
        self.assertEqual(STORE["New Prompt"], "New draft content")
        self.assertEqual(self.tab._active_prompt_name, "Alpha")


if __name__ == "__main__":
    unittest.main()
