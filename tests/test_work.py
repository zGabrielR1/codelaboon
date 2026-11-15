import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import work
from codelaboon.watch import run


class WorkTests(unittest.TestCase):
    def configure(self, root):
        config = root / 'config.json'
        config.write_text(json.dumps({
            'runtime': 'runtime', 'harnesses': [{'id': 'test', 'argv': [sys.executable, '-c', 'print("ok")']}],
            'tasks': [{'id': 'first', 'project': '.', 'prompt': 'first'}]}), encoding='utf-8')
        return config

    def test_add_is_persistent_and_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configure(root)
            task_id = work.add(root, 'new instruction', [[sys.executable, '-c', 'pass']], config)
            result = work.status(config)
            self.assertFalse(result['running'])
            self.assertIn(task_id, [t['id'] for t in result['pending']])
            self.assertTrue((root / 'runtime/inbox' / (task_id + '.json')).is_file())

    def test_new_instruction_is_picked_up_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configure(root)
            calls = []
            def execute(*args, **kwargs):
                calls.append(args)
                if len(calls) == 1:
                    work.add(root, 'second instruction', [[sys.executable, '-c', 'pass']], config)
                else:
                    (root / 'runtime/STOP').touch()
                return 0
            with patch('codelaboon.watch.execute', side_effect=execute), patch('time.sleep'):
                run(config)
            state = json.loads((root / 'runtime/state.json').read_text())
            self.assertEqual(len(state['done']), 2)
            self.assertEqual(len(calls), 3)  # Both tasks plus the queued task acceptance command.

    def test_pause_and_resume_preserve_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configure(root)
            work.control('pause', config)
            with patch('codelaboon.watch.execute') as execute:
                run(config, once=True)
                execute.assert_not_called()
            self.assertTrue(work.status(config)['paused'])
            work.control('resume', config)
            self.assertFalse(work.status(config)['paused'])

    def test_add_rejects_missing_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configure(root)
            with self.assertRaises(ValueError):
                work.add(root, 'instruction', [], config)

    def test_initialized_empty_queue_can_wait_without_dispatching(self):
        with tempfile.TemporaryDirectory() as directory:
            config = work.initialize(Path(directory) / 'work.json')
            with patch('codelaboon.watch.execute') as execute:
                run(config, once=True)
            execute.assert_not_called()
            self.assertEqual(work.status(config)['pending'], [])


if __name__ == '__main__':
    unittest.main()
