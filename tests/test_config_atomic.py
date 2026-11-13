"""Failed and concurrent writes must preserve saved provider credentials."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config import providers as config


class AtomicConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name) / 'providers.toml'
        for name, value in [('CONFIG_DIR', Path(self.root.name)), ('PROVIDERS_CONFIG_FILE', self.path)]:
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_replace_failure_keeps_original_and_removes_temporary_file(self):
        original = {'wusrouter': {'api_key': 'original', 'models': []}}
        self.assertTrue(config.save_providers_config(original))
        before = self.path.read_bytes()
        with patch('config.providers.os.replace', side_effect=OSError('simulated failure')):
            self.assertFalse(config.save_providers_config({'wusrouter': {'api_key': 'new'}}))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.providers-*.tmp')), [])

    def test_concurrent_provider_updates_are_preserved(self):
        self.assertTrue(config.save_providers_config(config._default_config()))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(lambda i: config.save_provider_config(
                f'provider{i}', {'api_key': f'test-{i}', 'models': []}), range(8)))
        self.assertTrue(all(outcomes))
        saved = config.get_providers_config()
        for i in range(8):
            self.assertEqual(saved[f'provider{i}']['api_key'], f'test-{i}')
