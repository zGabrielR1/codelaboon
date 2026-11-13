"""Independent offline oracle for the cloud build-runner hardening task."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TARGET = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location('candidate_build_workspace', TARGET)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class BuildFailureOracle(unittest.TestCase):
    def exercise(self, outcome):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(candidate, 'ROOT', root), \
                    patch.object(candidate.subprocess, 'run', side_effect=outcome) as launch, \
                    patch.object(sys, 'argv', [str(TARGET), '--project', 'verified']):
                try:
                    value = candidate.main()
                    failed = value not in (None, 0)
                except SystemExit as error:
                    failed = error.code not in (None, 0)
            manifest_path = root / 'workspace-build.json'
            self.assertTrue(manifest_path.is_file(), 'Failure must leave a build manifest')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertIs(manifest['source_regenerated'], False)
            self.assertIsInstance(manifest.get('target_executed'), str)
            return failed, manifest, launch

    def test_timeout_is_recorded_and_stops_dependents(self):
        failed, manifest, launch = self.exercise(subprocess.TimeoutExpired(['compiler'], 300))
        self.assertTrue(failed)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(len(manifest['results']), 1)
        result = manifest['results'][0]
        self.assertEqual(result['project'], 'data-core')
        self.assertEqual(result['exit_code'], 124)
        self.assertIn('timeout', result['error'].lower())
        self.assertTrue(result['started_utc'])
        self.assertTrue(result['finished_utc'])

    def test_start_failure_is_recorded(self):
        failed, manifest, launch = self.exercise(FileNotFoundError('missing compiler fixture'))
        self.assertTrue(failed)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(manifest['results'][0]['exit_code'], 127)
        self.assertIn('missing compiler fixture', manifest['results'][0]['error'])

    def test_success_preserves_compile_flags_and_order(self):
        failed, manifest, launch = self.exercise([
            subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)])
        self.assertFalse(failed)
        self.assertEqual([r['project'] for r in manifest['results']], ['data-core', 'reports'])
        self.assertEqual(launch.call_count, 2)
        commands = [call.args[0] for call in launch.call_args_list]
        self.assertIn('--compile-only', commands[0])
        self.assertIn('--test', commands[0])
        self.assertIn('--source-linked', commands[1])
        self.assertFalse(any('--recover' in command for command in commands))


if __name__ == '__main__':
    unittest.main()
