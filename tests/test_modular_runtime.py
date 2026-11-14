import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from codelaboon import engine_assets, storage
from codelaboon.service import pending_work


class ModularRuntimeTests(unittest.TestCase):
    def test_asset_download_verified_cached_and_partial_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info = {'name': 'test', 'asset': 'test.tar.gz', 'sha256': hashlib.sha256(b'payload').hexdigest(),
                    'url': 'https://example.invalid/asset'}
            response = MagicMock()
            response.__enter__.return_value = response
            response.iter_content.return_value = [b'payload']
            with patch.object(engine_assets, 'record', return_value=info), \
                    patch.object(engine_assets, 'VENDOR', root/'vendor'), \
                    patch.object(engine_assets, 'cache_dir', return_value=root/'cache'), \
                    patch('requests.get', return_value=response) as request:
                first = engine_assets.archive_for('test')
                self.assertEqual(first.read_bytes(), b'payload')
                self.assertEqual(engine_assets.archive_for('test'), first)
                self.assertEqual(request.call_count, 1)
                first.unlink()
                response.iter_content.return_value = [b'corrupt']
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    engine_assets.archive_for('test')
                self.assertEqual(list(first.parent.iterdir()), [])

    def test_router_unloaded_for_idle_completed_and_paused_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'tasks': [{'id': 'one'}]}
            self.assertFalse(pending_work({'tasks': []}, root))
            self.assertTrue(pending_work(config, root))
            (root/'state.json').write_text('{"done":["one"]}')
            self.assertFalse(pending_work(config, root))
            (root/'inbox').mkdir()
            (root/'inbox/new.json').write_text('{"id":"two"}')
            self.assertTrue(pending_work(config, root))
            (root/'PAUSE').touch()
            self.assertFalse(pending_work(config, root))

    def test_relocation_preserves_files_config_and_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root/'project'
            (project/'codelaboon').mkdir(parents=True)
            (project/'codelaboon/cli.py').touch()
            (project/'pyproject.toml').touch()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            local = project/'.watch/local'
            local.mkdir(parents=True)
            (local/'model').write_bytes(b'unique model')
            runtime = project/'.runtime'
            runtime.mkdir()
            (runtime/'work.json').write_text(json.dumps({'local_model': str(local/'model'), 'tasks': []}))
            (project/'.watch/watch-active.json').write_text('{"tasks":["preserve legacy"]}')
            environment = {'CODELABOON_CONFIG_DIR': str(root/'config'), 'CODELABOON_CACHE_DIR': str(root/'cache'),
                           'CODELABOON_DATA_DIR': str(root/'data')}
            with patch.dict(os.environ, environment):
                preview = storage.compact(project)
                self.assertFalse(preview['apply'])
                self.assertTrue(local.exists())
                result = storage.compact(project, apply=True)
                self.assertEqual(len(result['moves']), 3)
                self.assertTrue(Path(result['journal']).exists())
                self.assertEqual((root/'config/runtime/local/model').read_bytes(), b'unique model')
                self.assertEqual(json.loads((root/'config/work.json').read_text())['local_model'],
                                 str(root/'config/runtime/local/model'))
                self.assertEqual(json.loads((root/'data/legacy-watch/watch-active.json').read_text())['tasks'], ['preserve legacy'])

    def test_tracked_source_is_never_relocated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'codelaboon').mkdir()
            (root/'codelaboon/cli.py').touch()
            (root/'pyproject.toml').touch()
            (root/'releases').mkdir()
            (root/'releases/unique').touch()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', 'releases'], check=True)
            with self.assertRaisesRegex(ValueError, 'tracked'):
                storage.plan(root)

class JcodeLifecycleTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX process-group integration')
    def test_timeout_reaps_native_group_and_restores_handlers(self):
        import signal
        import sys
        from codelaboon.jcode_engine import run
        before = signal.getsignal(signal.SIGTERM)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root/'native'
            executable.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(60)\n')
            executable.chmod(0o700)
            with self.assertRaisesRegex(RuntimeError, 'time budget'):
                run(str(executable), ['run', 'test'], [{'id': 'free', 'api': 'chat'}],
                    'http://127.0.0.1:1/v1', 'isolated-token', timeout=0.1, home=root/'home')
            self.assertEqual(signal.getsignal(signal.SIGTERM), before)
            self.assertNotIn('isolated-token', (root/'home/config.toml').read_text())


class SwarmAcceptanceTests(unittest.TestCase):
    def invoke(self, code=0, failure=None, checks=()):
        from codelaboon.swarm import execute
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = MagicMock(providers={'local': object()})
            gateway = MagicMock(token='private')
            gateway.models.return_value = [{'id': 'free', 'api': 'chat'}]
            context = MagicMock()
            context.__enter__.return_value = (gateway, 'http://127.0.0.1:1/v1')
            with patch('codelaboon.cli.CodelaboonCLI', return_value=cli), \
                    patch('codelaboon.external_engines.executable', return_value='native'), \
                    patch('codelaboon.native_gateway.serve', return_value=context), \
                    patch('codelaboon.swarm.data_dir', return_value=root), \
                    patch('codelaboon.jcode_engine.run', return_value=0, side_effect=failure), \
                    patch('codelaboon.watch.execute', return_value=code) as check:
                result = execute('Build and verify', timeout=20, checks=checks)
                record = json.loads(next(root.rglob('result.json')).read_text())
                return result, record, check.call_count

    def test_check_failure_cannot_be_reported_as_success(self):
        result, record, calls = self.invoke(code=9, checks=[['test-command']])
        self.assertEqual((result, record['acceptance'], calls), (9, 'failed', 1))

    def test_missing_checks_are_explicit_and_timeouts_recorded(self):
        self.assertEqual(self.invoke()[1]['acceptance'], 'not_requested')
        result, record, calls = self.invoke(failure=RuntimeError('exceeded time budget'), checks=[['check']])
        self.assertEqual((result, record['acceptance'], calls), (124, 'failed', 0))


if __name__ == '__main__':
    unittest.main()
