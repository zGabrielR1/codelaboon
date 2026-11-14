import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from codelaboon.cloud_worker import agent


class CloudWorkerTests(unittest.TestCase):
    def invoke(self, events, code=0):
        process = MagicMock()
        process.stdout = io.StringIO(''.join(json.dumps(e) + '\n' for e in events))
        process.wait.return_value = code
        with tempfile.TemporaryDirectory() as directory, \
                patch('subprocess.Popen', return_value=process):
            return agent('cloud/model', Path(directory) / 'prompt.md', Path(directory), engine='opencode')

    def test_complete_cloud_response(self):
        self.assertEqual(self.invoke([
            {'type': 'text', 'part': {'text': 'Implementation complete'}},
            {'type': 'step_finish', 'part': {'reason': 'stop'}}]), 'Implementation complete')

    def test_partial_empty_or_failed_cloud_response_is_failure(self):
        for events in (
            [{'type': 'text', 'part': {'text': 'partial'}}],
            [{'type': 'step_finish', 'part': {'reason': 'stop'}}],
            [{'type': 'error'}, {'type': 'text', 'part': {'text': 'partial'}},
             {'type': 'step_finish', 'part': {'reason': 'stop'}}],
        ):
            with self.assertRaises(RuntimeError):
                self.invoke(events)

    def test_rust_builder_requires_final_json_text(self):
        process = MagicMock(returncode=0)
        process.communicate.return_value = ('{"text":"Verified build"}', None)
        with tempfile.TemporaryDirectory() as directory, patch('subprocess.Popen', return_value=process) as spawn:
            prompt = Path(directory)/'prompt.md'
            prompt.write_text('Implement change')
            self.assertEqual(agent('codelaboon/free', prompt, Path(directory)), 'Verified build')
            self.assertIn('jcode', spawn.call_args.args[0])
            self.assertIn('free', spawn.call_args.args[0])
            process.communicate.return_value = ('{"text":""}', None)
            with self.assertRaisesRegex(RuntimeError, 'no final'):
                agent('free', prompt, Path(directory))


if __name__ == '__main__':
    unittest.main()
