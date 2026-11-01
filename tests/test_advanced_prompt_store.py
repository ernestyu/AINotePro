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

if __name__ == '__main__':
    unittest.main()
