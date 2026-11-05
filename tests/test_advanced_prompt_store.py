import json
import os
import tempfile
import unittest
from unittest.mock import patch
from ainotepro.config import manager


class PromptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.patchers = [patch.object(manager, 'USER_FILES_DIR', self.root), patch.object(manager, 'CONFIG_FILE', os.path.join(self.root, 'user_config.json')), patch.object(manager, 'LEGACY_USER_DATA_DIR', os.path.join(self.root, 'missing'))]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)
        self.store = manager.ConfigManager()

    def test_migration_delete_does_not_revive_and_cas(self):
        os.makedirs(os.path.join(self.root, 'gen_text'))
        with open(os.path.join(self.root, 'gen_text', 'prompt.json'), 'w') as f:
            json.dump({'Legacy': 'value'}, f)
        initial, digest = self.store.prompt_snapshot('easy')
        self.assertEqual(initial['Legacy'], 'value')
        stale = digest
        del initial['Legacy']
        digest = self.store.replace_prompts('easy', initial, digest)
        self.assertNotIn('Legacy', self.store.prompt_snapshot('easy')[0])
        with self.assertRaises(RuntimeError):
            self.store.replace_prompts('easy', {'stale': 'x'}, stale)
        self.assertEqual(digest, self.store.prompt_snapshot('easy')[1])

    def test_first_migration_preserves_legacy_custom_default(self):
        os.makedirs(os.path.join(self.root, 'gen_text'))
        with open(os.path.join(self.root, 'gen_text', 'prompt.json'), 'w') as f:
            json.dump({'Default': 'Historical customized default'}, f)
        prompts, _digest = self.store.prompt_snapshot('easy')
        self.assertEqual(prompts['Default'], 'Historical customized default')

    def test_domains_do_not_conflict(self):
        easy, token = self.store.prompt_snapshot('easy')
        advanced, other = self.store.prompt_snapshot('advanced')
        advanced['Custom'] = 'x'
        self.store.replace_prompts('advanced', advanced, other)
        self.store.set_provider_config('text', 'openai', {'model': 'new'})
        easy['Another'] = 'y'
        self.store.replace_prompts('easy', easy, token)
        self.assertEqual(self.store._read_raw()['text']['openai']['model'], 'new')
        self.assertIn('Custom', self.store.prompt_snapshot('advanced')[0])

    def test_bad_mirror_rolls_back(self):
        os.makedirs(os.path.join(self.root, 'gen_text'))
        with open(os.path.join(self.root, 'gen_text', 'prompt.json'), 'w') as f:
            f.write('{')
        before = self.store._revision()
        with self.assertRaises(ValueError):
            self.store.prompt_snapshot('easy')
        self.assertEqual(before, self.store._revision())

    def test_complete_library_merge_is_atomic_and_preserves_audio_identity(self):
        import copy
        from ainotepro.core.prompt_bundle import make_bundle

        initial = self.store.library_snapshot()
        before = copy.deepcopy(self.store._read_raw())
        audio = initial["audio_profiles"][0]
        imported = copy.deepcopy(audio)
        imported["provider_configs"]["edge_tts"]["voices"][0]["speed"] = 7
        incoming = make_bundle(
            {"Default": "A different Default", "Backup": "easy text"},
            {"Backup": "advanced text"}, [imported],
        )

        writes = []
        original = self.store._atomic_write

        def count_write(data):
            writes.append(copy.deepcopy(data))
            return original(data)

        with patch.object(self.store, "_atomic_write", side_effect=count_write):
            merged, stats = self.store.merge_library(incoming)
        self.assertEqual(len(writes), 1, "All three domains must commit together")
        self.assertEqual(merged["prompts"]["easy"]["Default"],
                         initial["prompts"]["easy"]["Default"])
        self.assertEqual(merged["prompts"]["easy"]["Default (1)"],
                         "A different Default")
        self.assertEqual(merged["prompts"]["advanced"]["Backup"],
                         "advanced text")
        self.assertEqual(len(merged["audio_profiles"]), 2)
        self.assertEqual(self.store.library_snapshot(), merged)

        disk = self.store._read_raw()
        old_id = next(iter(before["audio"]["profiles"]))
        self.assertIn(old_id, disk["audio"]["profiles"])
        self.assertEqual(disk["audio"]["profiles"][old_id],
                         before["audio"]["profiles"][old_id])
        self.assertEqual(disk["audio"]["last_profile_id"],
                         before["audio"]["last_profile_id"])
        self.assertEqual(len(disk["audio"]["profiles"]), 2)
        self.assertEqual(disk["text"]["openai"], before["text"]["openai"])
        self.assertEqual(stats["audio_profiles"]["renamed"], 1)

        snapshot = open(manager.CONFIG_FILE, "rb").read()
        again, stats_again = self.store.merge_library(incoming)
        self.assertEqual(again, merged)
        self.assertEqual(stats_again["audio_profiles"]["added"], 0)
        self.assertEqual(open(manager.CONFIG_FILE, "rb").read(), snapshot)

    def test_library_import_keeps_nfd_audio_identity_when_nfc_alias_matches(self):
        import copy
        from ainotepro.core.prompt_bundle import make_bundle

        # The audio name is valid but has decomposed Unicode spelling.
        self.store.library_snapshot()  # finish one-time legacy migration
        audio, revision = self.store.get_audio_snapshot()
        profile_id = next(iter(audio["profiles"]))
        audio["profiles"][profile_id]["name"] = "Cafe\u0301"
        self.store.replace_audio(audio, expected_revision=revision)
        original = copy.deepcopy(self.store._read_raw())

        equivalent = copy.deepcopy(audio["profiles"][profile_id])
        equivalent["name"] = "Café"
        incoming = make_bundle(
            {"Unicode import": "text-only change"}, {}, [equivalent],
        )
        merged, stats = self.store.merge_library(incoming)
        updated = self.store._read_raw()

        self.assertIn("Unicode import", merged["prompts"]["easy"])
        self.assertEqual(stats["audio_profiles"]["added"], 0)
        self.assertEqual(updated["audio"], original["audio"])
        self.assertEqual(set(updated["audio"]["profiles"]), {profile_id})
        self.assertEqual(updated["audio"]["last_profile_id"],
                         original["audio"]["last_profile_id"])

        after_first_import = open(manager.CONFIG_FILE, "rb").read()
        again, repeat_stats = self.store.merge_library(incoming)
        self.assertEqual(again, merged)
        self.assertEqual(repeat_stats["audio_profiles"]["added"], 0)
        self.assertEqual(open(manager.CONFIG_FILE, "rb").read(), after_first_import)

    def test_invalid_audio_rejects_entire_import_without_file_changes(self):
        import copy
        from ainotepro.core.prompt_bundle import make_bundle

        original = self.store.library_snapshot()
        before = open(manager.CONFIG_FILE, "rb").read()
        invalid = copy.deepcopy(original)
        invalid["prompts"]["easy"]["New"] = "Should not be imported"
        invalid["audio_profiles"][0]["provider_configs"]["edge_tts"]["voices"][0]["speed"] = 999
        with self.assertRaises(ValueError):
            self.store.merge_library(invalid)
        self.assertEqual(open(manager.CONFIG_FILE, "rb").read(), before)

        incoming = make_bundle({"Another": "text"}, {}, [])
        with patch.object(self.store, "_atomic_write",
                          side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                self.store.merge_library(incoming)
        self.assertEqual(open(manager.CONFIG_FILE, "rb").read(), before)

    def test_github_settings_do_not_contain_token(self):
        self.store.set_github_prompt_settings(
            {'repository': 'user/prompts', 'branch': 'main', 'path': 'prompts.json'}
        )
        self.assertEqual(self.store.github_prompt_settings()['repository'],
                         'user/prompts')
        raw = self.store._read_raw()
        self.assertNotIn('token', str(raw.get('text', {}).get('github_prompt_sync')))

    def test_credential_settings_rollback_restores_unconfigured_state(self):
        original = self.store.github_prompt_settings()
        self.assertEqual(original["repository"], "")
        self.store.set_github_prompt_settings({
            "repository": "owner/repo", "branch": "main",
            "path": "anki/ainotepro-library.json",
        })
        self.assertIn("github_prompt_sync", self.store._read_raw()["text"])
        self.store.restore_github_prompt_settings(original)
        self.assertNotIn("github_prompt_sync", self.store._read_raw()["text"])
        self.assertEqual(self.store.github_prompt_settings(), original)

    def test_prompt_maps_cannot_bypass_mode_cas(self):
        self.store.prompt_snapshot('easy')
        before = self.store._read_raw()
        with self.assertRaises(ValueError):
            self.store.update_text_fields({'prompts': {'Bypass': 'no'}})
        proposed = self.store.get_all()
        proposed['text']['prompts']['Bypass'] = 'no'
        with self.assertRaises(ValueError):
            self.store.save_all(proposed)
        after = self.store._read_raw()
        self.assertEqual(after['text']['prompts'], before['text']['prompts'])
        self.assertEqual(after['text']['openai'], before['text']['openai'])
        self.assertEqual(after['audio'], before['audio'])

if __name__ == '__main__':
    unittest.main()
