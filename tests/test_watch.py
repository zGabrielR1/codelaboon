import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from codelaboon.watch import run, execute


class WatchTests(unittest.TestCase):
    def test_cloud_plan_build_and_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'orchestrator': {'url': 'http://127.0.0.1:1', 'model': 'router'},
                'harnesses': [
                    {'id': 'planner', 'location': 'cloud', 'stages': ['plan'],
                     'argv': [sys.executable, '-c', 'print("cloud plan")']},
                    {'id': 'builder', 'location': 'cloud', 'stages': ['build'],
                     'argv': [sys.executable, '-c',
                              'from pathlib import Path; Path("built").write_text("ok"); print("built")']}],
                'tasks': [{'id': 'one', 'project': '.', 'prompt': 'secret source context',
                           'verify_argv': [[sys.executable, '-c',
                                            'from pathlib import Path; assert Path("built").read_text() == "ok"']]}]}))
            with patch('codelaboon.local_router.choose', return_value=0) as router:
                run(config, once=True)
                state = json.loads((root / '.watch/state.json').read_text())
                self.assertEqual(state['done'], [])
                self.assertIn('one', state['plans'])
                run(config, once=True)
                state = json.loads((root / '.watch/state.json').read_text())
                self.assertEqual(state['done'], ['one'])
                self.assertNotIn('secret source context', json.dumps(router.call_args_list[0].args))

    def test_local_failure_never_dispatches_cloud(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'orchestrator': {'model': 'router'},
                'harnesses': [{'id': 'cloud', 'location': 'cloud', 'stages': ['plan', 'build'],
                              'argv': [sys.executable, '-c', 'print("unexpected")']}],
                'tasks': [{'id': 'one', 'project': '.', 'prompt': 'task',
                           'verify_argv': [[sys.executable, '-c', 'pass']]}]}))
            with patch('codelaboon.local_router.choose', side_effect=ValueError('invalid job')):
                with self.assertRaises(ValueError):
                    run(config, once=True)
            self.assertFalse(list((root / '.watch').glob('*/result.json')))

    def test_failed_acceptance_check_is_not_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'orchestrator': {'model': 'router'},
                'harnesses': [{'id': 'cloud', 'location': 'cloud', 'stages': ['plan', 'build'],
                              'argv': [sys.executable, '-c', 'print("claims success")']}],
                'tasks': [{'id': 'one', 'project': '.', 'prompt': 'task',
                           'verify_argv': [[sys.executable, '-c', 'raise SystemExit(1)']]}]}))
            with patch('codelaboon.local_router.choose', return_value=0):
                run(config, once=True)
                run(config, once=True)
            state = json.loads((root / '.watch/state.json').read_text())
            self.assertEqual(state['done'], [])
            self.assertIn('cloud', state['cooldowns'])

    def test_resume_and_failure_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'harnesses': [
                    {'id': 'limited', 'argv': [sys.executable, '-c', 'raise SystemExit(1)']},
                    {'id': 'working', 'argv': [sys.executable, '-c', 'print("done")']}],
                'tasks': [{'id': 'one', 'project': '.', 'prompt': 'hello'}]}))
            run(config, once=True)
            state = json.loads((root / '.watch/state.json').read_text())
            self.assertEqual(state['done'], [])
            self.assertIn('limited', state['cooldowns'])
            run(config, once=True)
            state = json.loads((root / '.watch/state.json').read_text())
            self.assertEqual(state['done'], ['one'])
            count = len(list((root / '.watch').glob('*/result.json')))
            run(config, once=True)
            self.assertEqual(len(list((root / '.watch').glob('*/result.json'))), count)

    def test_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = execute([sys.executable, '-c', 'import time; time.sleep(30)'],
                           root, root / 'output.log', 0.1)
            self.assertEqual(code, 124)


if __name__ == '__main__':
    unittest.main()
