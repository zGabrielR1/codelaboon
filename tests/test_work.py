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

    def test_malformed_inbox_entry_does_not_block_status_or_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configure(root)
            task_id = work.add(root, 'new instruction', [[sys.executable, '-c', 'pass']], config)
            inbox = root / 'runtime/inbox'
            (inbox / 'damaged.json').write_text('{', encoding='utf-8')
            valid = json.loads((inbox / f'{task_id}.json').read_text(encoding='utf-8'))
            for name, changes in {
                'malformed-swarm': {'swarm': []},
                'malformed-settings': {'execution_settings': []},
                'malformed-supervision': {'supervision': None},
                'malformed-checks': {'verify_argv': {'command': ['test']}},
                'malformed-id': {'id': '\ud800'},
            }.items():
                record = {**valid, 'id': name, **changes}
                (inbox / f'{name}.json').write_text(json.dumps(record), encoding='utf-8')
            pending = {task['id']: task for task in work.status(config)['pending']}
            self.assertEqual(set(pending), {'first', task_id})

            work.control('pause', config, task_id)
            pending = {task['id']: task for task in work.status(config)['pending']}
            self.assertTrue(pending[task_id]['paused'])
            with patch('codelaboon.watch.execute', return_value=0):
                run(config, once=True)
            state = json.loads((root / 'runtime/state.json').read_text(encoding='utf-8'))
            self.assertEqual(state['done'], ['first'])

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

    def test_interrupted_attempt_finishes_and_remains_eligible_on_restart(self):
        from codelaboon.task_attempts import history
        from codelaboon.task_conversation import attempt_events

        for interrupted_log, verification in (('output.log', 'not_run'), ('check-0.log', 'interrupted')):
            with self.subTest(interrupted_log=interrupted_log), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = self.configure(root)
                setup = json.loads(config.read_text(encoding='utf-8'))
                setup['tasks'][0]['verify_argv'] = [[sys.executable, '-c', 'pass']]
                config.write_text(json.dumps(setup), encoding='utf-8')
                runtime = root / 'runtime'

                def execute(argv, cwd, output, timeout, **options):
                    if output.name == interrupted_log:
                        raise KeyboardInterrupt
                    return 0

                with patch('codelaboon.watch.execute', side_effect=execute):
                    with self.assertRaises(KeyboardInterrupt):
                        run(config, once=True)
                attempts = history(runtime, 'first')
                self.assertEqual(len(attempts), 1)
                self.assertEqual(attempts[0]['status'], 'failed')
                self.assertEqual(attempts[0]['verification'], verification)
                self.assertEqual(attempts[0]['failure_label'], 'Worker stopped during this attempt')
                state = json.loads((runtime / 'state.json').read_text(encoding='utf-8'))
                self.assertEqual(Path(state['last_attempts']['first']).name, attempts[0]['id'])
                self.assertEqual(state['done'], [])
                self.assertEqual(state['cooldowns'], {})
                self.assertTrue(any(event.get('failure_kind') == 'interrupted'
                                    for event in attempt_events(runtime, 'first')))

                with patch('codelaboon.watch.execute', return_value=0) as execute:
                    run(config, once=True)
                self.assertEqual(execute.call_count, 2)
                self.assertEqual(history(runtime, 'first')[0]['status'], 'succeeded')

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
