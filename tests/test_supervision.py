import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from codelaboon import supervision,work
from codelaboon.execution_policy import child_environment
from codelaboon.watch import execute,run
from codelaboon.work_queue import controls

class SupervisionTests(unittest.TestCase):
    def test_security_requires_scope_and_full_permissions_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=work.initialize(root/'work.json')
            with self.assertRaises(ValueError):work.add(root,'audit',[['true']],config,profile='security')
            identity=work.add(root,'audit',[['true']],config,permissions='full',profile='security',scope='Local fixture only',allowed_paths=['reports/*'])
            task=json.loads((root/'work-runtime/inbox'/ (identity+'.json')).read_text())
            self.assertEqual(task['permissions'],'full');self.assertEqual(task['profile'],'security')
            self.assertTrue(task['supervision']['enabled']);self.assertEqual(task['supervision']['allowed_paths'],['reports/*'])
            self.assertEqual(child_environment(task)['CODELABOON_WORK_PERMISSIONS'],'full')
            self.assertEqual(child_environment({})['CODELABOON_WORK_PERMISSIONS'],'default')
            self.assertNotEqual(os.environ.get('CODELABOON_WORK_PERMISSIONS'),'full')
    def test_monitor_stops_active_process_without_running_its_remaining_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);marker=root/'should-not-exist'
            script='import time;from pathlib import Path;print("started",flush=True);time.sleep(10);Path('+repr(str(marker))+').touch()'
            started=time.monotonic()
            code=execute([sys.executable,'-c',script],root,root/'output.log',20,monitor=lambda:supervision.REDIRECT,review_interval=.01)
            self.assertEqual(code,supervision.REDIRECT);self.assertFalse(marker.exists());self.assertLess(time.monotonic()-started,5)
    def test_file_scope_pauses_even_if_model_would_approve(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';attempt.mkdir()
            task={'id':'task','prompt':'Edit README only','supervision':{'enabled':True,'allowed_paths':['README.md']}}
            baseline={'fingerprints':{'billing.py':'old'}};current={'fingerprints':{'billing.py':'new'}}
            with patch('codelaboon.supervision.project_state',side_effect=[baseline,current]),patch('codelaboon.supervision.review') as model:
                monitor=supervision.Monitor({},task,root,attempt);self.assertEqual(monitor(),supervision.PAUSE);model.assert_not_called()
            self.assertTrue((controls(root,'task')/'PAUSE').exists())
    def test_three_local_failures_pause_instead_of_uncontrolled_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';attempt.mkdir();task={'id':'task','prompt':'Task','supervision':{'enabled':True}}
            with patch('codelaboon.supervision.project_state',return_value={}),patch('codelaboon.supervision.review',side_effect=OSError('offline')):
                monitor=supervision.Monitor({},task,root,attempt)
                self.assertIsNone(monitor());self.assertIsNone(monitor());self.assertEqual(monitor(),supervision.PAUSE)
    def test_redirect_invalidates_plan_and_preserves_objective(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=work.initialize(root/'work.json')
            identity=work.add(root,'Fix README typo',[[sys.executable,'-c','pass']],config,permissions='full',scope='README.md')
            runtime=root/'work-runtime'
            def plan(argv,cwd,output,timeout,**options):output.write_text('Plan: fix README');return 0
            def drift(argv,cwd,output,timeout,**options):
                self.assertEqual(options['env']['CODELABOON_WORK_PERMISSIONS'],'full')
                self.assertIsNotNone(options.get('monitor'))
                output.write_text('Drifting')
                (output.parent/'supervision.json').write_text(json.dumps({'action':'redirect','correction':'Return to README typo only','evidence':'Drifting'}))
                return supervision.REDIRECT
            with patch('codelaboon.local_router.choose',return_value=0),patch('codelaboon.watch.execute',side_effect=plan):run(config,once=True)
            with patch('codelaboon.local_router.choose',return_value=0),patch('codelaboon.watch.execute',side_effect=drift):run(config,once=True)
            state=json.loads((runtime/'state.json').read_text())
            self.assertNotIn(identity,state['plans']);self.assertEqual(state['corrections'][identity],'Return to README typo only');self.assertFalse(state['done'])
            def corrected(argv,cwd,output,timeout,**options):
                prompt=(output.parent/'prompt.md').read_text();self.assertIn('Fix README typo',prompt);self.assertIn('Return to README typo only',prompt);output.write_text('Corrected plan');return 0
            with patch('codelaboon.local_router.choose',return_value=0),patch('codelaboon.watch.execute',side_effect=corrected):run(config,once=True)
    def test_remote_controller_and_unsafe_allowlist_are_rejected(self):
        with self.assertRaises(ValueError):supervision.review({'url':'https://example.com','model':'x'},{'prompt':'x'},{})
        with self.assertRaises(ValueError):supervision.validate({'enabled':True,'allowed_paths':['../*']})
    def test_default_opencode_policy_and_explicit_full_mode(self):
        from codelaboon.native_tui import opencode_config
        with patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='default'):
            self.assertNotIn('permission',opencode_config([],'http://local','token'))
        with patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='full'):
            self.assertEqual(opencode_config([],'http://local','token')['permission']['*'],'allow')
    def test_security_prefix_is_not_lost_after_model_flags(self):
        from codelaboon.jcode_engine import launch
        with patch('codelaboon.jcode_engine.run',return_value=0) as worker:
            launch('jcode',['--model','free','run','Audit fixture'],'security',False,[],'http://local','token')
        self.assertIn('authorized pentesting',worker.call_args.args[1][-1]);self.assertIn('Audit fixture',worker.call_args.args[1][-1])
    def test_final_review_failure_cannot_complete_an_unreviewed_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';attempt.mkdir()
            with patch('codelaboon.supervision.project_state',return_value={}),patch('codelaboon.supervision.review',side_effect=ValueError('bad decision')):
                monitor=supervision.Monitor({}, {'id':'task','prompt':'Fix docs'},root,attempt)
                self.assertEqual(monitor.finish(),supervision.PAUSE)
    def test_short_successful_worker_still_gets_a_final_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);calls=[]
            code=execute([sys.executable,'-c','print("done")'],root,root/'output.log',5,monitor=lambda:calls.append(True),review_interval=15)
            self.assertEqual(code,0);self.assertEqual(calls,[True])
    def test_task_resume_clears_a_scope_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=work.initialize(root/'work.json')
            identity=work.add(root,'Task',[['true']],config)
            work.control('pause',config,identity);self.assertTrue((controls(root/'work-runtime',identity)/'PAUSE').exists())
            work.control('resume',config,identity);self.assertFalse((controls(root/'work-runtime',identity)/'PAUSE').exists())
    def test_default_queue_job_does_not_inherit_parent_full_policy(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='full',CODELABOON_WORK_PROFILE='security'):
            root=Path(directory);output=root/'output.log'
            self.assertEqual(execute([sys.executable,'-c','import os;print(os.environ["CODELABOON_WORK_PERMISSIONS"],os.environ["CODELABOON_WORK_PROFILE"])'],root,output,5),0)
            self.assertEqual(output.read_text().strip(),'default coding')
    def test_staged_and_reverted_files_are_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'outside.py').write_text('original');subprocess.run(['git','add','.'],cwd=root,check=True)
            state=supervision.project_state(root);self.assertIn('outside.py',state['fingerprints'])
            attempt=root/'attempt';attempt.mkdir();task={'id':'task','prompt':'README only','supervision':{'enabled':True,'allowed_paths':['README.md']}}
            with patch('codelaboon.supervision.project_state',side_effect=[{'fingerprints':{'outside.py':'changed'}},{'fingerprints':{}}]),patch('codelaboon.supervision.review') as model:
                monitor=supervision.Monitor({},task,root,attempt);self.assertEqual(monitor(),supervision.PAUSE);model.assert_not_called()
    def test_allowlist_pauses_if_git_cannot_be_inspected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';attempt.mkdir()
            task={'id':'task','prompt':'README only','supervision':{'enabled':True,'allowed_paths':['README.md']}}
            with patch('codelaboon.supervision.review') as model:
                monitor=supervision.Monitor({},task,root,attempt);self.assertEqual(monitor(),supervision.PAUSE);model.assert_not_called()
    def test_privileged_swarm_receipt_counts_once_and_requires_fresh_case(self):
        from codelaboon.privilege import digest
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=work.initialize(root/'work.json')
            options={'controller':'worker','workers':1,'timeout':60,'interval':1,'cycles':0,'model':'free'}
            identity=work.add(root,'Approved cycle',[[sys.executable,'-c','pass']],config,swarm=options,permissions='full',scope='Disposable fixture',elevation='root',supervise=False)
            runtime=root/'work-runtime';task=json.loads((runtime/'inbox'/(identity+'.json')).read_text());control=controls(runtime,identity);control.mkdir(parents=True)
            (control/'privileged-fixture.json').write_text(json.dumps({'case':'fixture','task_sha256':digest(task),'exit_code':0}))
            with patch('codelaboon.watch.execute') as execute:
                run(config,once=True);run(config,once=True);execute.assert_not_called()
            state=json.loads((runtime/'state.json').read_text());self.assertEqual(state['cycles'][identity],1);self.assertNotIn(identity,state['done'])
