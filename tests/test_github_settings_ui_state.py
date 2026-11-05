"""Execute real GitHub settings state methods with a minimal Qt-like fake UI."""
from __future__ import annotations

import ast
import types
import unittest
from pathlib import Path

from ainotepro.services.github_prompts import validate_settings


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ainotepro" / "ui" / "github_prompt_dialog.py"


class Widget:
    def __init__(self, text=""):
        self.text_value = text
        self.enabled = True
        self.visible = True
        self.placeholder = ""
        self.checked = False

    def text(self):
        return self.text_value

    def clear(self):
        self.text_value = ""

    def setEnabled(self, value):
        self.enabled = value

    def setVisible(self, value):
        self.visible = value

    def setPlaceholderText(self, value):
        self.placeholder = value

    def setText(self, value):
        self.text_value = value

    def blockSignals(self, _value):
        return False

    def setChecked(self, value):
        self.checked = value

    def isChecked(self):
        return self.checked

    def setFocus(self):
        pass


class Timer:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def attach_real_methods(fake):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "GitHubPromptSettingsDialog")
    names = {
        "_show_status", "_repository_edited", "_refresh_token_status",
        "_enable_token_replacement", "_removal_changed",
    }
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
               and n.name in names]
    if len(methods) != len(names):
        raise AssertionError("Missing GitHub Settings UI state methods")
    program = ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[]))
    namespace = {"validate_settings": validate_settings}
    exec(compile(program, str(SOURCE), "exec"), namespace)
    for name in names:
        setattr(fake, name, types.MethodType(namespace[name], fake))


class GitHubSettingsStateTests(unittest.TestCase):
    def new_dialog(self, token_map, *, fail_repository=None):
        fake = types.SimpleNamespace(
            repository=Widget("owner/a"),
            token=Widget(), token_status=Widget(),
            replace_token=Widget(), forget_token=Widget(),
            _status_timer=Timer(), _credential_status="checking",
            _checked_repository=None,
        )
        lookup_calls = []
        def lookup(repo):
            lookup_calls.append(repo)
            if repo == fail_repository:
                raise RuntimeError("locked system keyring")
            return token_map.get(repo, "")
        fake._credential_lookup = lookup
        attach_real_methods(fake)
        return fake, lookup_calls

    def test_repo_a_b_a_status_follows_actual_credential_store(self):
        dialog, calls = self.new_dialog({
            "owner/a": "a-secret", "owner/b": "b-secret",
        })
        for repo, expected in (
            ("owner/a", "saved"), ("owner/b", "saved"),
            ("owner/c", "missing"), ("owner/a", "saved"),
        ):
            dialog.repository.setText(repo)
            dialog._repository_edited(repo)
            self.assertEqual(dialog._credential_status, "checking")
            self.assertFalse(dialog.token.enabled)
            dialog._refresh_token_status()
            self.assertEqual(dialog._credential_status, expected)
            self.assertIn(
                "Saved" if expected == "saved" else "Not saved",
                dialog.token_status.text(),
            )
            self.assertEqual(dialog.token.enabled, expected == "missing")
            self.assertEqual(dialog.replace_token.visible, expected == "saved")
        self.assertEqual(calls, ["owner/a", "owner/b", "owner/c", "owner/a"])

    def test_locked_store_is_not_mislabeled_missing(self):
        dialog, calls = self.new_dialog(
            {"owner/a": "secret"}, fail_repository="owner/b",
        )
        dialog.repository.setText("owner/b")
        dialog._repository_edited("owner/b")
        dialog._refresh_token_status()
        self.assertEqual(dialog._credential_status, "error")
        self.assertFalse(dialog.token.enabled)
        self.assertFalse(dialog.replace_token.visible)
        self.assertIn("Cannot access", dialog.token_status.text())
        self.assertNotIn("Not saved", dialog.token_status.text())

    def test_replace_removal_only_for_the_checked_repository(self):
        dialog, _calls = self.new_dialog({
            "owner/a": "a-secret", "owner/b": "b-secret",
        })
        dialog._refresh_token_status()
        dialog._enable_token_replacement()
        self.assertTrue(dialog.token.enabled)
        self.assertFalse(dialog.replace_token.enabled)
        dialog.token.setText("replacement")
        dialog.repository.setText("owner/b")
        dialog._repository_edited("owner/b")
        self.assertEqual(dialog.token.text(), "")
        dialog._refresh_token_status()
        self.assertFalse(dialog.token.enabled)
        self.assertTrue(dialog.replace_token.enabled)
        dialog._removal_changed(True)
        self.assertFalse(dialog.token.enabled)
        self.assertIn("Will be removed", dialog.token_status.text())
        dialog._removal_changed(False)
        self.assertIn("Saved", dialog.token_status.text())


if __name__ == "__main__":
    unittest.main()
