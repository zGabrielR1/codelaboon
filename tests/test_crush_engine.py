"""Crush installation, private configuration and native launch contracts."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from codelaboon.crush_engine import configuration, launch
from codelaboon.external_engines import managed_executable, setup, target, CRUSH_VERSION


class CrushTests(unittest.TestCase):
    rows = [{'id': 'free', 'name': 'free (Auto)', 'api': 'chat'},
            {'id': 'local/my-model', 'name': 'Local model', 'api': 'chat'}]

    def test_launch_preserves_permissions_and_uses_private_native_profile(self):
        captured = {}
        def run(command, **kwargs):
            captured.update(command=command, **kwargs)
            captured['config'] = (Path(kwargs['env']['CRUSH_GLOBAL_CONFIG']) / 'crushrc').read_text()
            return 0
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.crush_engine.config_dir', return_value=Path(directory)), patch(
                'codelaboon.crush_engine.subprocess.call', side_effect=run):
            self.assertEqual(launch('/native/crush', [], 'coding', False, self.rows,
                                    'http://127.0.0.1:345/v1', 'private-session-token'), 0)
            env = captured['env']
            self.assertEqual(captured['command'], ['/native/crush'])
            self.assertEqual(env['CODELABOON_GATEWAY_TOKEN'], 'private-session-token')
            self.assertNotIn('private-session-token', captured['config'])
            self.assertIn("--api-key '$CODELABOON_GATEWAY_TOKEN'", captured['config'])
            self.assertEqual(env['CRUSH_CLIENT_SERVER'], 'false')
            self.assertEqual(env['CRUSH_DISABLE_DEFAULT_PROVIDERS'], 'true')
            self.assertTrue(Path(env['CRUSH_DATA_DIR']).is_relative_to(Path(directory) / 'crush/projects'))
            self.assertFalse(Path(env['CRUSH_GLOBAL_CONFIG']).exists(), 'Temporary config leaked after launch')
            self.assertNotIn('permissions allow', captured['config'])

    def test_distinct_projects_keep_distinct_session_directories(self):
        values = []
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.crush_engine.config_dir', return_value=Path(directory)), patch(
                'codelaboon.crush_engine.subprocess.call', side_effect=lambda command, **kw: values.append(kw['env']['CRUSH_DATA_DIR']) or 0):
            for project in ('project-a', 'project-b', 'project-a'):
                with patch('codelaboon.crush_engine.Path.cwd', return_value=Path(directory) / project):
                    launch('/native/crush', [], 'coding', False, self.rows, 'url', 'token')
            self.assertNotEqual(values[0], values[1])
            self.assertEqual(values[0], values[2])

    def test_only_chat_models_are_exposed_and_both_roles_use_free(self):
        value = configuration(self.rows + [{'id': 'claude/paid', 'name': 'Paid', 'api': 'anthropic'}], 'free')
        self.assertIn('model large codelaboon/free', value)
        self.assertIn('model small codelaboon/free', value)
        self.assertNotIn('claude/paid', value)
        self.assertIn('--context-window 8192', value)

    def download_responses(self, payload):
        name = f'crush_{CRUSH_VERSION}_Windows_x86_64.zip'
        metadata, download = MagicMock(), MagicMock()
        for response in (metadata, download):
            response.__enter__.return_value = response
        metadata.text = hashlib.sha256(payload).hexdigest() + '  ' + name
        download.iter_content.return_value = [payload]
        return [metadata, download]

    def test_verified_zip_cannot_escape_install_directory(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../escape', b'bad')
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.external_engines.config_dir', return_value=Path(directory)), patch(
                'codelaboon.external_engines.target', return_value='windows-x64'), patch(
                'codelaboon.external_engines.requests.get', side_effect=self.download_responses(buffer.getvalue())):
            with self.assertRaisesRegex(RuntimeError, 'Unsafe path'):
                setup('crush')
            self.assertFalse(list(Path(directory).rglob('current.json')))
            self.assertFalse(list(Path(directory).rglob('escape')))

    def test_checksum_mismatch_never_activates_crush(self):
        responses = self.download_responses(b'expected')
        responses[1].iter_content.return_value = [b'corrupt']
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.external_engines.config_dir', return_value=Path(directory)), patch(
                'codelaboon.external_engines.target', return_value='windows-x64'), patch(
                'codelaboon.external_engines.requests.get', side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                setup('crush')
            self.assertFalse(list(Path(directory).rglob('current.json')))

    def test_reinstall_activates_verified_copy_and_failed_repair_preserves_it(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('crush.exe' if os.name == 'nt' else 'crush', b'verified binary')
        payload = buffer.getvalue()
        with tempfile.TemporaryDirectory() as directory, patch(
                'codelaboon.external_engines.config_dir', return_value=Path(directory)), patch(
                'codelaboon.external_engines.target', return_value='windows-x64'), patch(
                'codelaboon.external_engines.requests.get',
                side_effect=self.download_responses(payload) * 3), patch(
                'codelaboon.external_engines.subprocess.run') as probe:
            original = setup('crush')
            original.write_bytes(b'damaged')
            repaired = setup('crush')
            self.assertNotEqual(repaired, original)
            self.assertEqual(repaired.read_bytes(), b'verified binary')
            self.assertEqual(managed_executable('crush'), repaired.resolve())
            probe.side_effect = OSError('startup probe failed')
            with self.assertRaisesRegex(OSError, 'startup probe failed'):
                setup('crush')
            self.assertEqual(managed_executable('crush'), repaired.resolve())

    def test_managed_install_lookup_ignores_corrupt_and_outside_paths(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                'codelaboon.external_engines.config_dir', return_value=Path(directory)):
            root = Path(directory)
            outside = root / 'outside'
            outside.touch()
            marker = root / 'runtime/native-clis/crush/current.json'
            marker.parent.mkdir(parents=True)
            for value in ([], {'executable': None},
                          {'executable': str(marker.parent / '../../..' / outside.name)}):
                with self.subTest(value=value):
                    marker.write_text(json.dumps(value), encoding='utf-8')
                    self.assertIsNone(managed_executable('crush'))

    def test_go_binary_does_not_require_a_musl_specific_archive(self):
        with patch('codelaboon.external_engines.platform.system', return_value='Linux'), patch(
                'codelaboon.external_engines.platform.machine', return_value='x86_64'), patch(
                'codelaboon.external_engines.platform.libc_ver', return_value=('musl', '1.2')):
            self.assertEqual(target('crush'), 'linux-x64')

    def test_subcommand_help_does_not_load_providers(self):
        from codelaboon.external_engines import launch as external_launch
        with patch('codelaboon.external_engines.executable', return_value='/native/crush'), patch(
                'codelaboon.external_engines.subprocess.call', return_value=0) as run, patch(
                'codelaboon.cli.CodelaboonCLI', side_effect=AssertionError('Unexpected provider setup')):
            self.assertEqual(external_launch('crush', ['run', '--help']), 0)
            run.assert_called_once_with(['/native/crush', 'run', '--help'])


class CrushServerLifecycleTests(unittest.TestCase):
    def test_native_server_is_stopped_when_client_fails(self):
        from codelaboon.crush_engine import run_with_server
        server = MagicMock()
        server.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.crush_engine.server_ready', return_value=True), patch(
                'codelaboon.crush_engine.subprocess.Popen', return_value=server), patch(
                'codelaboon.crush_engine.subprocess.call', side_effect=RuntimeError('client failed')):
            with self.assertRaisesRegex(RuntimeError, 'client failed'):
                run_with_server('/native/crush', ['run', 'hello'], Path(directory), {}, directory)
            server.terminate.assert_called_once()
            server.wait.assert_called_once_with(timeout=5)

    def test_failed_server_start_exits_before_launching_client(self):
        from codelaboon.crush_engine import run_with_server
        server = MagicMock()
        server.poll.return_value = 1
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.crush_engine.server_ready', return_value=False), patch(
                'codelaboon.crush_engine.subprocess.Popen', return_value=server), patch(
                'codelaboon.crush_engine.subprocess.call') as client:
            with self.assertRaisesRegex(RuntimeError, 'did not become ready'):
                run_with_server('/native/crush', ['run', 'hello'], Path(directory), {}, directory)
            client.assert_not_called()
