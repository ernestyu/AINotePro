"""Failure-injection tests for the two-store GitHub settings transaction."""
import unittest

from ainotepro.services.github_settings_transaction import (
    GitHubSettingsTransactionError, apply_github_settings,
)


class FakeStores:
    def __init__(self):
        self.settings = {"repository": "owner/old", "branch": "main",
                         "path": "library.json"}
        self.tokens = {"owner/old": "github_pat_old",
                       "owner/new": "github_pat_existing"}
        self.fail_set = False
        self.fail_save = False
        self.commit_then_fail = False
        self.fail_compensation = False
        self.corrupt_write = False

    def get(self, repo):
        return self.tokens.get(repo, "")

    def set(self, repo, token):
        if self.fail_compensation and token == "github_pat_existing":
            raise RuntimeError("rollback vault unavailable")
        if self.fail_set:
            self.fail_set = False
            raise RuntimeError("vault write failed")
        self.tokens[repo] = "corrupted" if self.corrupt_write else token

    def delete(self, repo):
        if self.fail_compensation:
            raise RuntimeError("cannot rollback delete")
        self.tokens.pop(repo, None)

    def read(self):
        return dict(self.settings)

    def save(self, setting):
        if self.commit_then_fail:
            self.settings = dict(setting)
            raise RuntimeError("write completed but sync failed")
        if self.fail_save:
            raise RuntimeError("settings write failed")
        self.settings = dict(setting)

    def restore(self, previous):
        self.settings = dict(previous)

    def run(self, *, token="", remove=False, repo="owner/new"):
        return apply_github_settings(
            {"repository": repo, "branch": "main",
             "path": "anki/ainotepro-library.json"},
            new_token=token, remove_token=remove,
            read_settings=self.read, save_settings=self.save,
            restore_settings=self.restore, get_token=self.get,
            set_token=self.set, delete_token=self.delete,
        )


class TransactionTests(unittest.TestCase):
    def test_successful_replacement_preserves_other_repository(self):
        store = FakeStores()
        self.assertEqual(store.run(token="github_pat_new"), "saved")
        self.assertEqual(store.get("owner/new"), "github_pat_new")
        self.assertEqual(store.get("owner/old"), "github_pat_old")
        self.assertEqual(store.settings["repository"], "owner/new")

    def test_token_write_failure_rolls_back_without_settings_mutation(self):
        store = FakeStores()
        store.fail_set = True
        original = store.read()
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            store.run(token="github_pat_new")
        self.assertFalse(raised.exception.partial)
        self.assertEqual(store.get("owner/new"), "github_pat_existing")
        self.assertEqual(store.read(), original)

    def test_failed_verification_restores_old_credential(self):
        store = FakeStores()
        original = store.read()
        # Write a different value on the first call, then allow recovery.
        original_set = store.set
        calls = 0
        def altered(repo, value):
            nonlocal calls
            calls += 1
            if calls == 1:
                store.tokens[repo] = "unexpected"
            else:
                original_set(repo, value)
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            apply_github_settings(
                {"repository": "owner/new", "branch": "main", "path": "x.json"},
                new_token="github_pat_new", read_settings=store.read,
                save_settings=store.save, restore_settings=store.restore,
                get_token=store.get, set_token=altered, delete_token=store.delete,
            )
        self.assertFalse(raised.exception.partial)
        self.assertEqual(store.get("owner/new"), "github_pat_existing")
        self.assertEqual(store.read(), original)

    def test_config_write_failure_restores_changed_token(self):
        store = FakeStores()
        store.fail_save = True
        old = store.read()
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            store.run(token="github_pat_new")
        self.assertFalse(raised.exception.partial)
        self.assertIn("restored", str(raised.exception))
        self.assertNotIn("github_pat_new", str(raised.exception))
        self.assertEqual(store.get("owner/new"), "github_pat_existing")
        self.assertEqual(store.read(), old)

    def test_delete_then_config_failure_restores_existing_token(self):
        store = FakeStores()
        store.fail_save = True
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            store.run(remove=True)
        self.assertFalse(raised.exception.partial)
        self.assertEqual(store.get("owner/new"), "github_pat_existing")

    def test_config_commit_then_error_compensates_settings_and_token(self):
        store = FakeStores()
        old = store.read()
        store.commit_then_fail = True
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            store.run(token="github_pat_new")
        self.assertFalse(raised.exception.partial)
        self.assertEqual(store.get("owner/new"), "github_pat_existing")
        self.assertEqual(store.read(), old)

    def test_failed_compensation_reports_partial_change(self):
        store = FakeStores()
        store.fail_save = True
        store.fail_compensation = True
        with self.assertRaises(GitHubSettingsTransactionError) as raised:
            store.run(token="github_pat_new")
        self.assertTrue(raised.exception.partial)
        self.assertIn("PARTIAL CHANGE POSSIBLE", str(raised.exception))
        self.assertNotIn("github_pat_new", str(raised.exception))

    def test_changing_only_repository_does_not_modify_any_token(self):
        store = FakeStores()
        self.assertEqual(store.run(), "unchanged")
        self.assertEqual(store.get("owner/new"), "github_pat_existing")
        self.assertEqual(store.get("owner/old"), "github_pat_old")


if __name__ == "__main__":
    unittest.main()
