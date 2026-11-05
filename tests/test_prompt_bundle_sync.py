"""Unified library contract tests (no Anki UI or external services)."""
import json
import unittest

from ainotepro.config.audio_profiles import default_profile
from ainotepro.core.prompt_bundle import (
    FORMAT, make_bundle, merge_bundles, merge_audio_profiles,
    parse_bundle, serialize_bundle,
)


def profile(name="English", speed=0):
    saved = default_profile(name)
    saved["provider_configs"]["edge_tts"]["voices"][0]["speed"] = speed
    return saved


class BundleTests(unittest.TestCase):
    def test_complete_library_json_roundtrip(self):
        example = make_bundle(
            {"First": "汉字\nline", "Default": "Local default"},
            {"Prompt": "{Text}\n{OUT:Out}"},
            [profile("English"), profile("Kokoro", speed=5)],
        )
        parsed = parse_bundle(json.loads(serialize_bundle(example)))
        self.assertEqual(parsed, example)
        self.assertEqual(parsed["format"], "AINotePro.library")
        self.assertEqual(parsed["version"], 1)
        self.assertEqual(len(parsed["audio_profiles"]), 2)
        self.assertEqual(len(parsed["audio_profiles"][0]
                             ["provider_configs"]["edge_tts"]["voices"]), 4)

    def test_old_unreleased_prompt_only_formats_are_rejected(self):
        for old in (
            {"Easy": "text"},
            {"version": 1, "mode": "advanced", "prompts": {"A": "B"}},
            {"format": "AINotePro.prompt-library", "version": 2,
             "easy": {}, "advanced": {}},
        ):
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse_bundle(old)

    def test_prompt_conflict_numbers_and_repeat_noops(self):
        local = make_bundle({"A": "local", "A (1)": "other",
                             "Default": "built-in"}, {"B": "original"}, [])
        remote = make_bundle({"A": "remote", "Default": "historical"},
                             {"B": "new", "C": "added"}, [])
        result, stats = merge_bundles(local, remote)
        self.assertEqual(result["prompts"]["easy"]["A (2)"], "remote")
        self.assertEqual(result["prompts"]["easy"]["Default"], "built-in")
        self.assertEqual(result["prompts"]["easy"]["Default (1)"], "historical")
        self.assertEqual(result["prompts"]["advanced"]["B (1)"], "new")
        self.assertEqual(result["prompts"]["advanced"]["C"], "added")
        again, stats_again = merge_bundles(result, remote)
        self.assertEqual(again, result)
        self.assertEqual(stats_again["easy"]["added"], 0)
        self.assertEqual(stats_again["advanced"]["added"], 0)

    def test_audio_profile_conflict_preserves_settings_and_is_idempotent(self):
        local = [profile("Voice", speed=0), profile("Voice (1)", speed=5)]
        remote = [profile("Voice", speed=10)]
        merged, stats = merge_audio_profiles(local, remote)
        self.assertEqual([p["name"] for p in merged],
                         ["Voice", "Voice (1)", "Voice (2)"])
        self.assertEqual(merged[2]["provider_configs"]["edge_tts"]["voices"][0]["speed"], 10)
        self.assertEqual(stats["renamed"], 1)
        again, stats2 = merge_audio_profiles(merged, remote)
        self.assertEqual(again, merged)
        self.assertEqual(stats2["added"], 0)

    def test_same_audio_config_and_name_does_not_duplicate(self):
        original = profile("One")
        merged, stats = merge_audio_profiles([original], [original])
        self.assertEqual(merged, [original])
        self.assertEqual(stats["unchanged"], 1)

    def test_github_first_push_keeps_default_and_audio(self):
        remote = make_bundle({}, {}, [])
        local = make_bundle({"Default": "original"}, {}, [profile("New")])
        result, stats = merge_bundles(remote, local, protect_default=False)
        self.assertEqual(result, local)
        self.assertEqual(stats["audio_profiles"]["added"], 1)

    def test_two_devices_push_pull_stabilizes(self):
        remote = make_bundle({"A": "remote"}, {}, [profile("Voice", speed=0)])
        local = make_bundle({"A": "local"}, {}, [profile("Voice", speed=10)])
        pushed, _ = merge_bundles(remote, local, protect_default=False)
        self.assertEqual([p["name"] for p in pushed["audio_profiles"]],
                         ["Voice", "Voice (1)"])
        pulled, _ = merge_bundles(local, pushed)
        pushed_again, stats = merge_bundles(pushed, pulled, protect_default=False)
        self.assertEqual(pushed_again, pushed)
        self.assertEqual(stats["audio_profiles"]["added"], 0)

    def test_audio_schema_error_rejects_whole_library(self):
        bad = profile("Bad")
        bad["provider_configs"]["edge_tts"]["voices"][0]["speed"] = 999
        with self.assertRaises(ValueError):
            make_bundle({"Good": "should not commit"}, {}, [bad])
        with self.assertRaises(ValueError):
            parse_bundle({"format": FORMAT, "version": 1,
                          "prompts": {"easy": {}, "advanced": {}},
                          "audio_profiles": [{"name": "Incomplete"}]})

    def test_missing_audio_is_error_and_profile_ids_not_exported(self):
        with self.assertRaises(ValueError):
            parse_bundle({"format": FORMAT, "version": 1,
                          "prompts": {"easy": {}, "advanced": {}}})
        with self.assertRaises(ValueError):
            make_bundle({}, {}, [dict(profile("ID"), id="insecure")])

    def test_audio_profile_with_unexpected_api_key_is_rejected(self):
        dangerous = profile("Secret")
        dangerous["provider_configs"]["edge_tts"]["api_key"] = "do-not-upload"
        with self.assertRaisesRegex(ValueError, "credential field"):
            make_bundle({}, {}, [dangerous])

    def test_advanced_default_is_not_exported(self):
        with self.assertRaises(ValueError):
            make_bundle({}, {"Default": "dynamic"}, [])

    def test_long_name_numbering_does_not_duplicate_on_repeat(self):
        name = "N" * 100
        original = profile(name, speed=0)
        incoming = profile(name, speed=1)
        merged, _ = merge_audio_profiles([original], [incoming])
        self.assertEqual(len(merged), 2)
        again, stats = merge_audio_profiles(merged, [incoming])
        self.assertEqual(len(again), 2)
        self.assertEqual(stats["added"], 0)


if __name__ == "__main__":
    unittest.main()
