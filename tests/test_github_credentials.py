"""Credential storage tests; never touch real OS vaults or genuine tokens."""
from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ainotepro.services import github_credentials as credentials


class CredentialStoreTests(unittest.TestCase):
    def test_credentials_are_scoped_per_repository_and_case_insensitive(self):
        with patch.object(credentials.sys, "platform", "darwin"), \
             patch.object(credentials, "_mac_set") as store, \
             patch.object(credentials, "_mac_get", return_value="github_pat_abc") as read, \
             patch.object(credentials, "_mac_delete") as remove:
            credentials.set_token("ErnestYu/My-Library", "github_pat_abc")
            self.assertEqual(credentials.get_token("ernestyu/my-library"),
                             "github_pat_abc")
            credentials.delete_token("ernestyu/my-library")
        store.assert_called_once_with("ernestyu/my-library", "github_pat_abc")
        read.assert_called_once_with("ernestyu/my-library")
        remove.assert_called_once_with("ernestyu/my-library")

    def test_windows_uses_native_credentials(self):
        with patch.object(credentials.sys, "platform", "win32"), \
             patch.object(credentials, "_windows_set") as store, \
             patch.object(credentials, "_windows_get", return_value="ghp_example") as read:
            credentials.set_token("Owner/Repo", "ghp_example")
            self.assertEqual(credentials.get_token("owner/repo"), "ghp_example")
        store.assert_called_once_with("owner/repo", "ghp_example")
        read.assert_called_once_with("owner/repo")

    def test_malformed_repository_or_token_is_rejected_before_store(self):
        with patch.object(credentials, "_mac_set") as store, \
             patch.object(credentials.sys, "platform", "darwin"):
            for repository in ("", "name", "../repo", "owner/repo/extra"):
                with self.subTest(repository=repository), self.assertRaises(ValueError):
                    credentials.set_token(repository, "github_pat_good")
            for token in ("", "bad token", "hello\nworld", "bad;token"):
                with self.subTest(token=token), self.assertRaises(ValueError):
                    credentials.set_token("owner/repo", token)
        store.assert_not_called()

    def test_linux_secret_goes_to_stdin_not_process_arguments(self):
        call_args = []

        def invoke(args, **kwargs):
            call_args.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(credentials.shutil, "which", return_value="/usr/bin/secret-tool"), \
             patch.object(credentials.subprocess, "run", side_effect=invoke), \
             patch.object(credentials.sys, "platform", "linux"):
            credentials.set_token("Owner/Repo", "github_pat_example")
        args, kwargs = call_args[0]
        self.assertEqual(kwargs["input"], "github_pat_example")
        self.assertNotIn("github_pat_example", args)
        self.assertEqual(args[-2:], ["repository", "owner/repo"])
        self.assertEqual(args[1], "store")

    def test_missing_linux_token_is_normal(self):
        with patch.object(credentials.shutil, "which", return_value="/usr/bin/secret-tool"), \
             patch.object(credentials.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1, stdout="", stderr="")), \
             patch.object(credentials.sys, "platform", "linux"):
            self.assertEqual(credentials.get_token("owner/repo"), "")

    def test_linux_locked_keyring_reports_error(self):
        with patch.object(credentials.shutil, "which", return_value="/usr/bin/secret-tool"), \
             patch.object(credentials.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1, stdout="",
                                                       stderr="Keyring locked")), \
             patch.object(credentials.sys, "platform", "linux"):
            with self.assertRaisesRegex(credentials.CredentialStoreError, "keyring"):
                credentials.get_token("owner/repo")

    def test_linux_no_secret_tool_fails_without_plaintext_fallback(self):
        with patch.object(credentials.shutil, "which", return_value=None), \
             patch.object(credentials.sys, "platform", "linux"):
            with self.assertRaisesRegex(credentials.CredentialStoreError, "secret-tool"):
                credentials.set_token("owner/repo", "github_pat_example")

    def test_ui_reads_credentials_and_never_writes_token_to_config(self):
        source = (Path(__file__).resolve().parents[1] /
                  "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        dialog = (Path(__file__).resolve().parents[1] /
                  "ainotepro/ui/github_prompt_dialog.py").read_text(encoding="utf-8")
        for required in ("get_token(settings[\"repository\"])",
                         "set_token(dialog.value[\"repository\"], dialog.new_token)",
                         "delete_token(dialog.value[\"repository\"])",
                         "QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow",
                         "self.path.setMinimumWidth(430)"):
            self.assertIn(required, source + dialog)
        self.assertNotIn("self._github_token", source)
        self.assertIn("Saved in system credential store", dialog)


if __name__ == "__main__":
    unittest.main()
