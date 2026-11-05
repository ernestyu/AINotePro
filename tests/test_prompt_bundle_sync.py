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

    def test_audio_profile_whitelist_omits_unknown_nested_secret_fields(self):
        dangerous = profile("Secret")
        dangerous["credentials"] = "top-secret-profile"
        dangerous["provider_configs"]["edge_tts"]["client_secret"] = "nested-secret"
        dangerous["provider_configs"]["kokoro_gradio"]["api_key"] = "provider-secret"
        dangerous["provider_configs"]["edge_tts"]["voices"][0]["access_token"] = "voice-secret"
        encoded = serialize_bundle(make_bundle({}, {}, [dangerous])).decode()
        for secret in ("top-secret-profile", "nested-secret", "provider-secret",
                       "voice-secret", "client_secret", "credentials", "access_token"):
            self.assertNotIn(secret, encoded)
        restored = parse_bundle(json.loads(encoded))
        self.assertEqual(len(restored["audio_profiles"]), 1)
        self.assertEqual(len(restored["audio_profiles"][0]
                             ["provider_configs"]["edge_tts"]["voices"]), 4)

    def test_names_reject_casefold_nfc_and_whitespace_collisions(self):
        cases = [
            {"A": "x", "a": "y"},
            {"Straße": "x", "STRASSE": "y"},
            {"Café": "x", "Cafe\u0301": "y"},
            {"Name": "x", " Name ": "y"},
        ]
        for prompts in cases:
            with self.subTest(prompts=prompts), self.assertRaisesRegex(
                ValueError, "Duplicate Easy prompt name"
            ):
                make_bundle(prompts, {}, [])
        with self.assertRaisesRegex(ValueError, "Duplicate Audio Profile"):
            make_bundle({}, {}, [profile("Straße"), profile("STRASSE")])
        with self.assertRaisesRegex(ValueError, "Advanced Default"):
            make_bundle({}, {"default": "dynamic"}, [])

    def test_aliases_are_intentionally_distinct_by_name(self):
        aliases = make_bundle({"My Prompt": "Translate this",
                               "Translation": "Translate this"}, {}, [])
        merged, stats = merge_bundles(make_bundle({}, {}, []), aliases)
        self.assertEqual(len(merged["prompts"]["easy"]), 2)
        self.assertEqual(stats["easy"]["added"], 2)

    def test_multi_device_rounds_preserve_content_without_name_convergence(self):
        """V1 requires content union and idempotence, not identical local names."""
        devices = [
            make_bundle({"A": "x"}, {"Scenario": "x"}, [profile("Voice", speed=0)]),
            make_bundle({"A": "y"}, {"Scenario": "y"}, [profile("Voice", speed=5)]),
            make_bundle({"A": "z"}, {"Scenario": "z"}, [profile("Voice", speed=10)]),
        ]
        remote = make_bundle({}, {}, [])
        def saved_values(bundle):
            return (
                set(bundle["prompts"]["easy"].values()),
                set(bundle["prompts"]["advanced"].values()),
                {p["provider_configs"]["edge_tts"]["voices"][0]["speed"]
                 for p in bundle["audio_profiles"]},
            )
        for index in (0, 1, 2, 2, 0, 1, 1, 2, 0):
            remote, _ = merge_bundles(remote, devices[index], protect_default=False)
            devices[index], _ = merge_bundles(devices[index], remote)
        for idx in range(3):
            devices[idx], _ = merge_bundles(devices[idx], remote)
        expected = ({"x", "y", "z"}, {"x", "y", "z"}, {0, 5, 10})
        self.assertEqual(saved_values(remote), expected)
        for device in devices:
            self.assertEqual(saved_values(device), expected)
        before = json.dumps(remote, sort_keys=True)
        for device in devices:
            remote, result = merge_bundles(remote, device, protect_default=False)
            self.assertEqual(result["easy"]["added"], 0)
            self.assertEqual(result["advanced"]["added"], 0)
            self.assertEqual(result["audio_profiles"]["added"], 0)
        self.assertEqual(json.dumps(remote, sort_keys=True), before)

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
