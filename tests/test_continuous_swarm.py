import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import swarm, work
from codelaboon.service import pending_work
from codelaboon.watch import run
from codelaboon.work_queue import controls, ready


class ContinuousSwarmTests(unittest.TestCase):
    def configure(self, root, controller='worker', cycles=0):
        config = work.initialize(root/'work.json')
        options = dict(controller=controller, workers=2, timeout=20, interval=30, cycles=cycles, model='free')
        task_id = work.add(root, 'Improve only the fixture', [[sys.executable, '-c', 'pass']], config, options)
        return config, task_id, root/'work-runtime'

    @staticmethod
    def execute(argv, project, output, timeout):
        output.write_text('Verified progress')
        return 0

    def test_worker_control_repeats_after_restart_without_local_router(self):
        with tempfile.TemporaryDirectory() as directory:
            config, task_id, runtime = self.configure(Path(directory), cycles=2)
            with patch('codelaboon.local_router.choose') as router, patch('codelaboon.watch.execute', side_effect=self.execute) as execute:
                run(config, once=True)
                state = json.loads((runtime/'state.json').read_text())
                self.assertEqual(state['cycles'][task_id], 1)
                self.assertNotIn(task_id, state['done'])
                self.assertEqual(execute.call_count, 2)  # Swarm plus independent acceptance.
                run(config, once=True)
                self.assertEqual(execute.call_count, 2)  # Persisted interval suppresses dispatch.
                state['next_run'][task_id] = 0
                (runtime/'state.json').write_text(json.dumps(state))
                run(config, once=True)
                router.assert_not_called()
            state = json.loads((runtime/'state.json').read_text())
            self.assertIn(task_id, state['done'])
            self.assertEqual(state['cycles'][task_id], 2)

    def test_local_control_plans_then_runs_swarm_and_replans_next_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            config, task_id, runtime = self.configure(Path(directory), controller='local')
            with patch('codelaboon.local_router.choose', return_value=0) as router, patch('codelaboon.watch.execute', side_effect=self.execute) as execute:
                run(config, once=True)
                self.assertIn(task_id, json.loads((runtime/'state.json').read_text())['plans'])
                run(config, once=True)
                self.assertEqual(router.call_count, 2)
                self.assertIn('native-swarm', router.call_args.args[1][0]['capabilities'])
                self.assertEqual(execute.call_count, 3)  # Plan, swarm, independent check.
            state = json.loads((runtime/'state.json').read_text())
            self.assertNotIn(task_id, state['plans'])
            self.assertEqual(state['cycles'][task_id], 1)
            self.assertFalse(pending_work(json.loads(config.read_text()), runtime))

    def test_failed_check_does_not_complete_cycle_and_has_backoff(self):
        with tempfile.TemporaryDirectory() as directory:
            config, task_id, runtime = self.configure(Path(directory))
            def failed_check(argv, project, output, timeout):
                output.write_text('build' if 'swarm.py' in ' '.join(argv) else 'failure')
                return 0 if 'swarm.py' in ' '.join(argv) else 8
            with patch('codelaboon.watch.execute', side_effect=failed_check):
                run(config, once=True)
            state = json.loads((runtime/'state.json').read_text())
            self.assertNotIn(task_id, state['cycles'])
            self.assertNotIn(task_id, state['done'])
            self.assertGreater(state['cooldowns']['swarm-'+task_id], 0)
            with patch('codelaboon.watch.execute') as execute:
                run(config, once=True)
                execute.assert_not_called()

    def test_per_swarm_controls_and_router_demand(self):
        with tempfile.TemporaryDirectory() as directory:
            config, task_id, runtime = self.configure(Path(directory), controller='local')
            value = json.loads(config.read_text())
            self.assertTrue(pending_work(value, runtime))
            swarm.control('pause', task_id, config)
            self.assertFalse(pending_work(value, runtime))
            with patch('codelaboon.watch.execute') as execute:
                run(config, once=True)
                execute.assert_not_called()
            self.assertTrue(work.status(config)['pending'][0]['paused'])
            swarm.control('resume', task_id, config)
            self.assertTrue(pending_work(value, runtime))
            swarm.control('stop', task_id, config)
            with self.assertRaises(ValueError):
                swarm.control('resume', task_id, config)
            with self.assertRaises(ValueError):
                swarm.control('pause', 'unknown-id', config)
            self.assertFalse(pending_work(value, runtime))

    def test_worker_controller_never_loads_local_model(self):
        with tempfile.TemporaryDirectory() as directory:
            config, _, runtime = self.configure(Path(directory))
            self.assertFalse(pending_work(json.loads(config.read_text()), runtime))

    def test_enqueue_requires_checks_and_valid_limits_before_writing_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)/'work.json'
            with self.assertRaises(ValueError):
                swarm.enqueue('task', config=config)
            self.assertFalse(config.exists())
            with self.assertRaises(ValueError):
                swarm.enqueue('task', checks=[['check']], interval=0, config=config)
            self.assertFalse(config.exists())

    def test_offline_local_router_does_not_starve_worker_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config, local_id, runtime=self.configure(root, controller='local')
            options=dict(controller='worker',workers=2,timeout=20,interval=30,cycles=1,model='free')
            worker_id=work.add(root,'Worker objective',[[sys.executable,'-c','pass']],config,options)
            tasks={json.loads(path.read_text())['id']:json.loads(path.read_text()) for path in (runtime/'inbox').glob('*.json')}
            value=json.loads(config.read_text())
            value['tasks']=[tasks[local_id],tasks[worker_id]]
            config.write_text(json.dumps(value))
            def execute(argv, project, output, timeout):
                output.write_text('Verified progress')
                (runtime/'STOP').touch()
                return 0
            with patch('codelaboon.local_router.choose',side_effect=ValueError('offline')) as router, patch('codelaboon.watch.execute',side_effect=execute), patch('time.sleep'):
                run(config)
            self.assertEqual(router.call_count,1)
            state=json.loads((runtime/'state.json').read_text())
            self.assertIn(worker_id,state['done'])
            self.assertNotIn(local_id,state['done'])

    def test_swarm_and_checks_share_cycle_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            config,task_id,runtime=self.configure(Path(directory))
            with patch('codelaboon.watch.execute',side_effect=self.execute) as execute, patch('time.monotonic',side_effect=[0,25]):
                run(config,once=True)
            self.assertEqual(execute.call_count,1)
            state=json.loads((runtime/'state.json').read_text())
            self.assertNotIn(task_id,state['cycles'])
            self.assertEqual(next(runtime.glob('*/check-0.log')).read_text(),'Cycle time budget exhausted')

    def test_old_running_service_cannot_silently_consume_continuous_job(self):
        with tempfile.TemporaryDirectory() as directory:
            config=work.initialize(Path(directory)/'work.json')
            with patch('codelaboon.work.running',return_value=True), patch('codelaboon.work.start') as start:
                with self.assertRaisesRegex(ValueError,'predates'):
                    swarm.enqueue('task',checks=[['check']],config=config)
                start.assert_not_called()
            self.assertFalse(list((Path(directory)/'work-runtime/inbox').glob('*.json')))

    def test_acceptance_arguments_keep_literal_braces(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=work.initialize(root/'work.json')
            value=json.loads(config.read_text())
            value.pop('orchestrator')
            value['harnesses']=[{'id':'test','argv':[sys.executable,'-c','print("build")']}]
            check=[sys.executable,'-c','assert {"a":1}["a"]==1']
            value['tasks']=[dict(id='one',project=str(root),prompt='task',verify_argv=[check])]
            config.write_text(json.dumps(value))
            with patch('codelaboon.watch.execute',side_effect=self.execute) as execute:
                run(config,once=True)
            self.assertEqual(execute.call_args.args[0],check)

    def test_progress_context_is_bounded_and_available_to_plain_planner(self):
        from codelaboon.watch import progress_tail
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'output.log').write_bytes(b'x'*30000+b'LAST_VERIFIED_PROGRESS')
            tail=progress_tail(root)
            self.assertLessEqual(len(tail),12000)
            self.assertTrue(tail.endswith('LAST_VERIFIED_PROGRESS'))


if __name__ == '__main__':
    unittest.main()
