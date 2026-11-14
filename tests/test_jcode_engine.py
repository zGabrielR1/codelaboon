import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from codelaboon import jcode_engine


class JcodeEngineTests(unittest.TestCase):
    def test_refresh_preserves_native_display_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'config.toml').write_text('[display]\ntheme="nord"\n[features]\nmemory=true\n')
            for url in ('http://first/v1', 'http://second/v1'):
                jcode_engine.prepare([{'id':'free','api':'chat'}],url,root)
            value=tomllib.loads((root/'config.toml').read_text())
            self.assertEqual(value['display']['theme'],'nord')
            self.assertEqual(value['providers']['codelaboon']['base_url'],'http://second/v1')
            self.assertFalse(value['features']['memory'])
            self.assertEqual(len(value['providers']['codelaboon']['models']),1)

    def test_malformed_preferences_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'config.toml').write_text('[broken')
            with self.assertRaises(ValueError):
                jcode_engine.prepare([], 'http://gateway/v1', root)
            self.assertEqual((root/'config.toml').read_text(),'[broken')

    @unittest.skipIf(os.name=='nt','POSIX lock semantics')
    def test_concurrent_ui_cannot_overwrite_a_live_gateway_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            with jcode_engine.profile_lock(Path(directory)):
                with self.assertRaisesRegex(RuntimeError,'already owns'):
                    with jcode_engine.profile_lock(Path(directory)):
                        self.fail('Concurrent profile acquired')
            with jcode_engine.profile_lock(Path(directory)):
                pass

    def test_interactive_profile_persists_and_has_no_headless_timeout(self):
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.jcode_engine.data_dir',return_value=Path(directory)), patch('codelaboon.jcode_engine.run',return_value=0) as run:
            for _ in range(2):
                jcode_engine.launch('native', [], 'coding', False, [], 'http://gateway/v1', 'private')
            self.assertIsNone(run.call_args.kwargs['timeout'])
            self.assertTrue(run.call_args.kwargs['interactive'])
            self.assertEqual(run.call_args_list[0].kwargs['home'],run.call_args_list[1].kwargs['home'])


if __name__=='__main__':
    unittest.main()
