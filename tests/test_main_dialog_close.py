"""Headless behavior tests for the MainDialog/TextTab close gate."""
import ast
from pathlib import Path
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "ainotepro/ainotepro_gui.py").read_text()
TREE = ast.parse(SOURCE)
DIALOG = next(node for node in TREE.body if isinstance(node, ast.ClassDef)
              and node.name == "AiNoteProConfigDialog")
WANTED = {"_prepare_dialog_close", "_on_close"}
METHODS = [node for node in DIALOG.body if isinstance(node, ast.FunctionDef)
           and node.name in WANTED]
MODULE = ast.Module(body=[ast.ClassDef(name="CloseMethods", bases=[], keywords=[],
                                       body=METHODS, decorator_list=[])], type_ignores=[])
SCOPE = {}
exec(compile(ast.fix_missing_locations(MODULE), "<dialog close methods>", "exec"), SCOPE)
CloseMethods = SCOPE["CloseMethods"]


class _Text:
    def __init__(self, *, can_close=True, save_settings=True, prepare_close=True):
        self.can_close_result = can_close
        self.save_settings_result = save_settings
        self.prepare_close_result = prepare_close
        self.calls = []

    def can_close(self):
        self.calls.append("can_close")
        return self.can_close_result

    def save_settings(self):
        self.calls.append("save_settings")
        return self.save_settings_result

    def prepare_close(self, **kwargs):
        self.calls.append(("prepare_close", kwargs))
        return self.prepare_close_result


class _Audio:
    def __init__(self, can_close=True):
        self.can_close_result = can_close
        self.calls = 0

    def can_close(self):
        self.calls += 1
        return self.can_close_result


class _Dialog(CloseMethods):
    def __init__(self, text, audio):
        self.tabs = {"Text": text, "Audio": audio}
        self.accepted = 0

    def accept(self):
        self.accepted += 1


class MainDialogCloseTests(unittest.TestCase):
    def test_rejected_prompt_draft_leaves_task_and_other_close_checks_untouched(self):
        text, audio = _Text(can_close=False), _Audio()
        self.assertFalse(_Dialog(text, audio)._prepare_dialog_close())
        self.assertEqual(text.calls, ["can_close"])
        self.assertEqual(audio.calls, 0)

    def test_audio_or_settings_rejection_does_not_mark_text_task_closing(self):
        text, audio = _Text(), _Audio(can_close=False)
        self.assertFalse(_Dialog(text, audio)._prepare_dialog_close())
        self.assertEqual(text.calls, ["can_close"])
        text, audio = _Text(save_settings=False), _Audio()
        self.assertFalse(_Dialog(text, audio)._prepare_dialog_close())
        self.assertEqual(text.calls, ["can_close", "save_settings"])

    def test_close_cancels_text_callbacks_only_after_all_close_guards_pass(self):
        text, audio = _Text(), _Audio()
        dialog = _Dialog(text, audio)
        dialog._on_close()
        self.assertEqual(text.calls, [
            "can_close", "save_settings", ("prepare_close", {"confirmed": True}),
        ])
        self.assertEqual(audio.calls, 1)
        self.assertEqual(dialog.accepted, 1)


if __name__ == "__main__":
    unittest.main()
