"""Tests for complete prompt bundles and non-destructive import/synchronization."""
import json
import unittest

from ainotepro.core.prompt_bundle import (
    make_bundle, merge_bundles, parse_bundle, serialize_bundle,
)


class BundleTests(unittest.TestCase):
    def test_roundtrip_both_modes_unicode_and_newlines(self):
        data = make_bundle({"First": "汉字\nline", "Default": "Local default"},
                           {"Prompt": "{Text}\n{OUT:Out}"})
        self.assertEqual(parse_bundle(json.loads(serialize_bundle(data))), data)

    def test_older_exports_still_import(self):
        self.assertEqual(parse_bundle({"One": "two"})["easy"], {"One": "two"})
        old = {"version": 1, "mode": "advanced", "prompts": {"A": "B"}}
        self.assertEqual(parse_bundle(old)["advanced"], {"A": "B"})

    def test_conflicts_are_renamed_without_overwriting(self):
        local = make_bundle({"Prompt": "local", "Prompt (1)": "other",
                             "Default": "built-in"}, {"A": "x"})
        remote = make_bundle({"Prompt": "remote", "Default": "historical"},
                             {"A": "new", "B": "y"})
        result, stats = merge_bundles(local, remote)
        self.assertEqual(result["easy"]["Prompt (2)"], "remote")
        self.assertEqual(result["easy"]["Default"], "built-in")
        self.assertEqual(result["easy"]["Default (1)"], "historical")
        self.assertEqual(result["advanced"]["A (1)"], "new")
        self.assertEqual(result["advanced"]["B"], "y")
        repeated, stats2 = merge_bundles(result, remote)
        self.assertEqual(repeated, result)
        self.assertEqual(stats2["easy"]["added"], 0)

    def test_github_push_preserves_first_default_name(self):
        remote = make_bundle({}, {})
        local = make_bundle({"Default": "original", "A": "prompt"}, {})
        result, _ = merge_bundles(remote, local, protect_default=False)
        self.assertEqual(result["easy"], local["easy"])

    def test_push_then_pull_does_not_multiply_entries(self):
        remote = make_bundle({"A": "remote"}, {})
        local = make_bundle({"A": "local"}, {})
        pushed, _ = merge_bundles(remote, local, protect_default=False)
        self.assertEqual(pushed["easy"], {"A": "remote", "A (1)": "local"})
        pulled, _ = merge_bundles(local, pushed)
        self.assertEqual(pulled["easy"], {"A": "local", "A (1)": "remote"})
        pushed_again, _ = merge_bundles(pushed, pulled, protect_default=False)
        self.assertEqual(pushed_again, pushed)

    def test_invalid_versions_and_prompt_types_rejected(self):
        with self.assertRaises(ValueError):
            parse_bundle({"format": "AINotePro.prompt-library", "version": 99,
                          "easy": {}, "advanced": {}})
        with self.assertRaises(ValueError):
            parse_bundle({"format": "AINotePro.prompt-library", "version": 2,
                          "easy": {"A": 3}, "advanced": {}})


if __name__ == "__main__":
    unittest.main()
