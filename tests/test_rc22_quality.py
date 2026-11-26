"""Updater recovery, verified wheel selection and terminal navigation contracts."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import cli, native_tui, release_update, runtime_management as runtime, update


class QualityOfLife(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        environment = patch.dict(os.environ, CODELABOON_CONFIG_DIR=str(self.root/'config'), CODELABOON_METRICS='0', CODELABOON_MODEL_CHECKS='0')
        environment.start(); self.addCleanup(environment.stop)

    def prepared(self, engine='opencode'):
        root = self.root/engine
        path = root/'node_modules/@actions/core/package.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"name":"@actions/core"}')
        (root/'.codelaboon-ready').write_text(json.dumps({'format':3,'dependency_manifests':native_tui.dependency_snapshot(root)}))
        return root, path

    def test_maintenance_repairs_corruption_and_preserves_lazy_engines(self):
        root, manifest = self.prepared()
        manifest.write_bytes(b'\0'*1025)
        def repair(engine):
            self.assertEqual(engine, 'opencode')
            self.prepared()
        with patch.object(runtime,'location',side_effect=lambda engine:self.root/engine), patch.object(native_tui,'setup',side_effect=repair) as setup:
            self.assertEqual(runtime.inspect('opencode')['state'], 'damaged')
            runtime.maintain()
            setup.assert_called_once_with('opencode')
            self.assertEqual(runtime.inspect('opencode')['state'], 'ready')
            self.assertFalse((self.root/'omp').exists())
        receipt = runtime.read_receipt()
        self.assertTrue(receipt['success'])
        self.assertEqual(receipt['runtimes'][0]['action'], 'repaired')

    def test_failed_maintenance_records_failure_without_claiming_ready(self):
        root, manifest = self.prepared()
        manifest.write_bytes(b'\0')
        _, omp_manifest = self.prepared('omp')
        omp_manifest.write_bytes(b'\0')

        def repair(engine):
            if engine == 'opencode':
                raise RuntimeError('fixture failure')
            self.prepared(engine)

        with patch.object(runtime,'location',side_effect=lambda engine:self.root/engine), patch.object(native_tui,'setup',side_effect=repair):
            with self.assertRaisesRegex(RuntimeError, 'opencode'):
                runtime.maintain()
            self.assertEqual(runtime.inspect('opencode')['state'], 'damaged')
            self.assertEqual(runtime.inspect('omp')['state'], 'ready')
        receipt = runtime.read_receipt()
        self.assertFalse(receipt['success'])
        self.assertEqual(receipt['runtimes'], [
            {'engine': 'opencode', 'state': 'repair_failed'},
            {'engine': 'omp', 'state': 'ready', 'action': 'repaired'},
        ])

    def test_source_update_runs_fresh_repair_process_and_reports_failure(self):
        source=self.root/'source'
        source.mkdir();(source/'pyproject.toml').touch()
        file_patch=patch.object(update,'__file__',str(source/'codelaboon/update.py'))
        file_patch.start();self.addCleanup(file_patch.stop)
        with patch('codelaboon.install.install_package',return_value=(0,'')), patch.object(update.subprocess,'call',return_value=0) as call, patch('sys.stdout',new_callable=io.StringIO):
            self.assertTrue(update.update(pull=False))
            self.assertEqual(call.call_args.args[0], [sys.executable,'-m','codelaboon.runtime_management','maintain'])
        with patch('codelaboon.install.install_package',return_value=(0,'')), patch.object(update.subprocess,'call',return_value=1), patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertFalse(update.update(pull=False))
            self.assertIn('Core installation finished, but runtime verification failed',output.getvalue())
        with patch('codelaboon.install.install_package',return_value=(1,'install failed')), patch.object(update.subprocess,'call') as call, patch('sys.stdout',new_callable=io.StringIO):
            self.assertFalse(update.update(pull=False))
            call.assert_not_called()

    def test_runtime_verification_uses_the_installation_interpreter(self):
        with patch('codelaboon.install.installation_python',return_value=('managed-python',self.root)),patch.object(update.subprocess,'call',return_value=0) as start:
            self.assertTrue(update.finish_runtime_update(self.root,False,'opencode'))
            self.assertEqual(start.call_args.args[0][0],'managed-python')

    def test_installed_update_does_not_require_a_checkout(self):
        with patch.object(update,'__file__',str(self.root/'site/codelaboon/update.py')), patch.object(release_update,'install_latest',return_value=(True,'already current')) as install, patch.object(update.subprocess,'call',return_value=0) as maintain:
            self.assertTrue(update.update())
            install.assert_called_once()
            maintain.assert_called_once()

    def test_tui_shortcuts_forward_and_restore_project_and_environment(self):
        before = Path.cwd()
        previous = os.environ.get('CODELABOON_NO_ANIMATION')
        def launch(engine, arguments, profile, local_only, theme):
            self.assertEqual(Path.cwd().resolve(), self.root.resolve())
            self.assertEqual(os.environ['CODELABOON_NO_ANIMATION'], '1')
            self.assertEqual(arguments, ['--model','codelaboon/free','--continue'])
        with patch('sys.argv',['codelaboon','tui','--continue','--project',str(self.root),'--model','codelaboon/free','--no-animation']), patch.object(cli.CodelaboonCLI,'load_providers'), patch.object(cli,'run_tui',side_effect=launch) as start:
            cli.CodelaboonCLI().run()
            start.assert_called_once()
        self.assertEqual(Path.cwd(),before)
        self.assertEqual(os.environ.get('CODELABOON_NO_ANIMATION'),previous)

    def test_status_is_offline_and_prints_recovery_action(self):
        with patch.object(runtime,'location',side_effect=lambda engine:self.root/engine), patch('sys.argv',['codelaboon','status']), patch.object(cli.CodelaboonCLI,'load_providers') as providers, patch.object(native_tui,'setup') as setup, patch('sys.stdout',new_callable=io.StringIO) as output:
            cli.main()
            providers.assert_not_called(); setup.assert_not_called()
            self.assertIn('Continue work:',output.getvalue())
            self.assertIn('not installed',output.getvalue())


class VerifiedReleaseUpdates(unittest.TestCase):
    def release(self):
        tag='v1.0.0-rc.22'
        wheel='codelaboon-1.0.0rc22-py3-none-any.whl'
        return {'tag_name':tag,'draft':False,'assets':[{'name':name,'browser_download_url':release_update.DOWNLOAD+tag+'/'+name} for name in (wheel,'SHA256SUMS')]},wheel

    def test_wheel_name_uses_normalized_version(self):
        release, name = self.release()
        tag = 'v1.0.0rc.022'
        release['tag_name'] = tag
        for asset in release['assets']:
            asset['browser_download_url'] = release_update.DOWNLOAD + tag + '/' + asset['name']
        raw = b'test-wheel-bytes'
        manifest = f'{hashlib.sha256(raw).hexdigest()}  {name}\n'.encode()
        with patch('codelaboon.__version__', '1.0.0rc21'), patch.object(
            release_update, 'download', side_effect=[json.dumps([release]).encode(), manifest, raw]
        ) as download, patch('codelaboon.install.install_package', return_value=(0, '')) as install:
            self.assertTrue(release_update.install_latest()[0])
            self.assertEqual(download.call_args.args[0], release_update.DOWNLOAD + tag + '/' + name)
            self.assertEqual(install.call_args.kwargs['artifact'].name, name)

    def test_malformed_asset_metadata_stops_update(self):
        release, _ = self.release()
        for assets in (None, {'name': 'SHA256SUMS'}, [None]):
            with self.subTest(assets=assets):
                release['assets'] = assets
                with patch('codelaboon.__version__', '1.0.0rc21'), patch.object(
                    release_update, 'download', return_value=json.dumps([release]).encode()
                ) as download, patch('codelaboon.install.install_package') as install:
                    with self.assertRaisesRegex(ValueError, 'invalid asset metadata'):
                        release_update.install_latest()
                    self.assertEqual(download.call_count, 1)
                    install.assert_not_called()

    def test_checksum_required_before_wheel_is_passed_to_pip(self):
        release,name=self.release()
        raw=b'test-wheel-bytes'
        digest=hashlib.sha256(raw).hexdigest()
        def install(**options):
            self.assertEqual(options['artifact'].read_bytes(),raw)
            self.assertTrue(options['quiet'])
            return 0,''
        with patch('codelaboon.__version__','1.0.0rc21'), patch.object(release_update,'download',side_effect=[json.dumps([release]).encode(),(digest+'  '+name+'\n').encode(),raw]), patch('codelaboon.install.install_package',side_effect=install) as pip:
            ok,message=release_update.install_latest()
            self.assertTrue(ok); self.assertIn('SHA256 verified',message); pip.assert_called_once()
        with patch('codelaboon.__version__','1.0.0rc21'), patch.object(release_update,'download',side_effect=[json.dumps([release]).encode(),('0'*64+'  '+name).encode(),raw]), patch('codelaboon.install.install_package') as pip:
            with self.assertRaisesRegex(ValueError,'checksum mismatch'): release_update.install_latest()
            pip.assert_not_called()

    def test_no_downgrade_and_no_unexpected_asset_hosts(self):
        release,name=self.release()
        with patch('codelaboon.__version__','1.0.0rc23'), patch.object(release_update,'download',return_value=json.dumps([release]).encode()) as download, patch('codelaboon.install.install_package') as pip:
            self.assertTrue(release_update.install_latest()[0]); self.assertEqual(download.call_count,1); pip.assert_not_called()
        release['assets'][0]['browser_download_url']='https://other.invalid/'+name
        with patch('codelaboon.__version__','1.0.0rc21'), patch.object(release_update,'download',return_value=json.dumps([release]).encode()) as download:
            with self.assertRaisesRegex(ValueError,'outside'): release_update.install_latest()
            self.assertEqual(download.call_count,1)
