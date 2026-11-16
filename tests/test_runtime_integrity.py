"""Damaged source-runtime detection and recovery without using the shared cache."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from codelaboon import native_tui as runtime


class RuntimeIntegrity(unittest.TestCase):
    def manifest(self, root, raw=b'{"name":"@actions/core","version":"1.0.0"}'):
        path = root/'node_modules/@actions/core/package.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def mark(self, root):
        (root/'.codelaboon-ready').write_text(json.dumps({'format':3, 'dependency_manifests':runtime.dependency_snapshot(root)}))

    def test_ready_rejects_nuls_missing_files_and_changed_valid_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.manifest(root)
            self.mark(root)
            self.assertTrue(runtime.ready(root))
            for raw in (b'\0'*1025, b'{"name":"modified"}', b'[]'):
                path.write_bytes(raw)
                self.assertFalse(runtime.ready(root))
            path.unlink()
            self.assertFalse(runtime.ready(root))

    def test_corrupt_dependencies_are_preserved_and_install_uses_fresh_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'runtime'
            original = self.manifest(root, b'\0'*1025)
            (root/'.codelaboon-ready').write_text('{"format":2}')
            def install(command, **kwargs):
                self.assertIn('--cache-dir', command)
                self.assertFalse((root/'.codelaboon-ready').exists())
                self.manifest(root)
            with patch.object(runtime,'source_root',return_value=root), \
                 patch.object(runtime,'ensure_bun',return_value='bun'), \
                 patch.object(runtime.subprocess,'check_output',return_value='1.4.4'), \
                 patch.object(runtime.subprocess,'run',side_effect=install), \
                 patch.object(runtime,'check_startup') as startup, \
                 patch.object(runtime.requests,'get',return_value=Mock(json=lambda:{})):
                runtime.setup('opencode')
            backups = list(root.glob('.codelaboon-corrupt-dependencies-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0]/'@actions/core/package.json').read_bytes(), b'\0'*1025)
            self.assertTrue(original.is_file())
            self.assertTrue(runtime.ready(root))
            startup.assert_called_once_with('opencode',root,'bun')

    def test_failed_startup_or_install_leaves_no_ready_marker(self):
        for failure in ('install', 'startup'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.manifest(root)
                self.mark(root)
                with patch.object(runtime,'source_root',return_value=root), \
                     patch.object(runtime,'ensure_bun',return_value='bun'), \
                     patch.object(runtime.subprocess,'check_output',return_value='1.4.4'), \
                     patch.object(runtime.subprocess,'run',side_effect=RuntimeError('failed') if failure=='install' else None), \
                     patch.object(runtime,'check_startup',side_effect=RuntimeError('failed') if failure=='startup' else None), \
                     patch.object(runtime.requests,'get',return_value=Mock(json=lambda:{})):
                    with self.assertRaises(RuntimeError): runtime.setup('opencode')
                self.assertFalse((root/'.codelaboon-ready').exists())

    def test_force_repair_rebuilds_valid_manifest_tree_from_fresh_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.manifest(root)
            self.mark(root)
            def install(command, **kwargs):
                self.assertIn('--cache-dir', command)
                self.manifest(root)
            with patch.object(runtime,'source_root',return_value=root), patch.object(runtime,'ensure_bun',return_value='bun'), \
                 patch.object(runtime.subprocess,'check_output',return_value='1.4.4'), patch.object(runtime.subprocess,'run',side_effect=install), \
                 patch.object(runtime,'check_startup'), patch.object(runtime.requests,'get',return_value=Mock(json=lambda:{})):
                runtime.setup('opencode',force=True)
            self.assertTrue(runtime.ready(root))
            self.assertEqual(len(list(root.glob('.codelaboon-corrupt-dependencies-*'))),1)

    def test_startup_verification_bounds_failure_output_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def failed(command, **kwargs):
                self.assertEqual(command[-1], '--help')
                self.assertEqual(kwargs['env']['OPENCODE_DISABLE_MODELS_FETCH'], 'true')
                kwargs['stderr'].write(b'\0'*5000)
                return Mock(returncode=1)
            with patch.object(runtime.subprocess,'run',side_effect=failed):
                with self.assertRaises(RuntimeError) as result: runtime.check_startup('opencode',root,'bun')
                self.assertNotIn('\0',str(result.exception))
                self.assertLess(len(str(result.exception)), 11000)
            with patch.object(runtime.subprocess,'run',side_effect=subprocess.TimeoutExpired('bun',60)):
                with self.assertRaisesRegex(RuntimeError,'timed out'): runtime.check_startup('omp',root,'bun')
