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

    def test_complete_library_merge_is_atomic_and_never_overwrites_names(self):
        from ainotepro.core.prompt_bundle import make_bundle
        self.store.prompt_snapshot('easy')
        self.store.prompt_snapshot('advanced')
        initial = self.store.prompt_library_snapshot()
        self.assertIn('Default', initial['easy'])
        incoming = make_bundle(
            {'Default': 'A different Default', 'Backup': 'easy text'},
            {'Backup': 'advanced text'},
        )
        merged, stats = self.store.merge_prompt_library(incoming)
        self.assertEqual(merged['easy']['Default'], initial['easy']['Default'])
        self.assertEqual(merged['easy']['Default (1)'], 'A different Default')
        self.assertEqual(merged['easy']['Backup'], 'easy text')
        self.assertEqual(merged['advanced']['Backup'], 'advanced text')
        self.assertEqual(self.store.prompt_library_snapshot(), merged)
        again, stats_again = self.store.merge_prompt_library(incoming)
        self.assertEqual(again, merged)
        self.assertEqual(stats_again['easy']['added'], 0)
        self.assertEqual(stats_again['advanced']['added'], 0)

    def test_github_settings_do_not_contain_token(self):
        self.store.set_github_prompt_settings(
            {'repository': 'user/prompts', 'branch': 'main', 'path': 'prompts.json'}
        )
        self.assertEqual(self.store.github_prompt_settings()['repository'],
                         'user/prompts')
        raw = self.store._read_raw()
        self.assertNotIn('token', str(raw.get('text', {}).get('github_prompt_sync')))

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
