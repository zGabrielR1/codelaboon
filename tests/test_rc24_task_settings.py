import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

from codelaboon import task_settings as settings,task_orchestrator,task_changes,work,watch


class Settings(unittest.TestCase):
    def test_cloud_planning_overlay_does_not_start_the_legacy_local_router(self):
        from codelaboon.service import pending_work
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            task={'id':'fixture','swarm':{'model':'free','controller':'local'},'supervision':{'enabled':False}}
            config={'tasks':[task]}
            values={**settings.defaults(task),'orchestrator_mode':'cloud','orchestrator_model':'nvidia/planner'}
            settings.write(root,task,values,'initial')
            self.assertFalse(pending_work(config,root))
            task['supervision']['enabled']=True
            self.assertTrue(pending_work(config,root))
    def test_creation_captures_models_and_prompts_before_inbox_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'work.json';work.initialize(config)
            values={**settings.defaults({}),'worker_model':'nvidia/worker','orchestrator_mode':'local','orchestrator_model':'local/planner'}
            identity=work.add(root,'Fixture',[[sys.executable,'-c','pass']],config,swarm={'controller':'worker','model':'free','engine':'jcode','workers':1,'cycles':1,'interval':1,'timeout':30},execution_settings=values)
            task=json.loads(next((root/'work-runtime/inbox').glob('*.json')).read_text())
            self.assertEqual(task['execution_settings']['worker_model'],'nvidia/worker');self.assertEqual(task['swarm']['model'],'nvidia/worker')
            self.assertEqual(settings.read(root/'work-runtime',task)['revision'],'queued')
    def test_versioned_checkpoint_overlay_and_privileged_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);task={'id':'fixture','swarm':{'model':'free','controller':'local'},'scope':'fixture only'}
            original=copy.deepcopy(task);values=settings.defaults(task);values.update(worker_model='nvidia/fixture',orchestrator_mode='local',orchestrator_model='local/fixture',worker_system_prompt='Use regression tests')
            row=settings.write(root,task,values,'initial')
            effective=settings.apply(root,task)
            self.assertEqual(task,original);self.assertEqual(effective['swarm']['model'],'nvidia/fixture');self.assertEqual(effective['swarm']['controller'],'worker')
            self.assertEqual(effective['execution_settings']['revision'],row['revision'])
            with self.assertRaisesRegex(ValueError,'another session'):settings.write(root,task,values,'initial')
            self.assertEqual(settings.apply(root,{**task,'_privileged_case':True}),{**task,'_privileged_case':True})
            with self.assertRaisesRegex(ValueError,'immutable'):settings.write(root,{**task,'elevation':'root'},values,row['revision'])
            self.assertIn('fixture only',settings.system_text(task,values))

    def test_invalid_mode_models_and_policy_fields_are_rejected(self):
        values=settings.defaults({})
        for change in ({'orchestrator_mode':'local'},{'orchestrator_mode':'cloud','orchestrator_model':'local/fixture'},{'permissions':'full'},{'worker_model':'bad\nmodel'},{'worker_system_prompt':'x'*12001}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):settings.validate({**values,**change})

    def test_local_planner_never_calls_cloud_and_preserves_system_roles(self):
        local=Mock();local.chat.return_value='Local fixture plan';cloud=Mock()
        values={**settings.defaults({}),'orchestrator_mode':'local','orchestrator_model':'local/fixture','orchestrator_system_prompt':'Prefer regression evidence'}
        self.assertEqual(task_orchestrator.plan(values,'Immutable scope: fixture only',{'local':local,'nvidia':cloud}),'Local fixture plan')
        args=local.chat.call_args.args;self.assertEqual(args[0],'fixture');self.assertEqual(args[1][0]['role'],'system');self.assertIn('regression',args[1][0]['content']);cloud.chat.assert_not_called()
        local.chat.side_effect=RuntimeError('local server stopped')
        with self.assertRaises(RuntimeError):task_orchestrator.plan(values,'task',{'local':local,'nvidia':cloud})
        cloud.chat.assert_not_called()

    def test_cloud_planner_has_an_independent_model_and_no_tools(self):
        provider=Mock();provider.chat.return_value='Cloud fixture plan'
        values={**settings.defaults({}),'worker_model':'local/worker','orchestrator_mode':'cloud','orchestrator_model':'nvidia/planner'}
        self.assertEqual(task_orchestrator.plan(values,'Task',{'nvidia':provider}),'Cloud fixture plan')
        self.assertEqual(provider.chat.call_args.args[0],'planner');self.assertNotIn('tools',provider.chat.call_args.kwargs)


class CheckpointExecution(unittest.TestCase):
    def exercise(self,fail_plan):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'work.json';work.initialize(config)
            identity=work.add(root,'Only the fixture files',[[sys.executable,'-c','from pathlib import Path;Path("checked").write_text("verified")']],config,swarm={'controller':'worker','model':'free','engine':'jcode','workers':1,'cycles':1,'interval':1,'timeout':30})
            runtime=root/'work-runtime';task=json.loads(next((runtime/'inbox').glob('*.json')).read_text())
            values={**settings.defaults(task),'worker_model':'nvidia/worker','orchestrator_mode':'cloud','orchestrator_model':'nvidia/planner','worker_system_prompt':'Keep reports concise'}
            revision=settings.write(runtime,task,values,'initial')['revision']
            original_execute=watch.execute;calls=[]
            def execute(argv,cwd,output,timeout,**options):
                calls.append(argv)
                if any(part.endswith('task_orchestrator.py') for part in argv):
                    output.write_text('fixture planning')
                    if not fail_plan:Path(argv[-1]).write_text('Fixture plan: add regression evidence')
                    return 1 if fail_plan else 0
                return original_execute(argv,cwd,output,timeout,**options)
            def harness(task):
                self.assertEqual(task['swarm']['model'],'nvidia/worker')
                return {'id':'fixture-worker','location':'cloud','stages':['build'],'timeout_seconds':30,'argv':['{python}','-c','import os,sys;from pathlib import Path; p=Path(sys.argv[1]).read_text();assert "Fixture plan" in p;assert os.environ["CODELABOON_TASK_MODEL"]=="nvidia/worker";assert "Keep reports concise" in Path(os.environ["CODELABOON_TASK_SYSTEM_PROMPT_FILE"]).read_text();print("fixture implemented")','{prompt_file}']}
            with patch.object(watch,'execute',side_effect=execute),patch.object(watch,'swarm_harness',side_effect=harness):watch.run(config,once=True)
            result=json.loads(next(runtime.glob('*/result.json')).read_text())
            self.assertEqual(result['execution_settings']['revision'],revision)
            self.assertEqual((root/'checked').exists(),not fail_plan)
            self.assertEqual(result['status'],'failed' if fail_plan else 'succeeded')
            self.assertEqual(len(calls),1 if fail_plan else 3)
    def test_plan_worker_and_independent_checks_share_checkpoint_settings(self):self.exercise(False)
    def test_planner_failure_never_dispatches_workers_or_accepts_cycle(self):self.exercise(True)


class ProjectChanges(unittest.TestCase):
    def test_read_only_diff_labels_preexisting_changes_and_omits_untracked_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            subprocess.run(['git','init',str(root)],capture_output=True,check=True)
            (root/'tracked.py').write_text('before\n')
            subprocess.run(['git','add','tracked.py'],cwd=root,check=True)
            subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture'],cwd=root,capture_output=True,check=True)
            (root/'tracked.py').write_text('after\npassword=fixture-secret\n')
            (root/'untracked.txt').write_text('untracked-private-contents')
            before=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root)
            row=task_changes.snapshot(root)
            self.assertTrue(row['available']);self.assertIn('tracked.py',row['status']);self.assertIn('+after',row['diff']);self.assertNotIn('fixture-secret',row['diff']);self.assertNotIn('untracked-private-contents',json.dumps(row))
            self.assertIn('pre-existing',row['notice']);self.assertEqual(before,subprocess.check_output(['git','rev-parse','HEAD'],cwd=root))


class SystemPromptWire(unittest.TestCase):
    def test_task_system_prompt_reaches_chat_gateway_without_replacing_native_system(self):
        from codelaboon.native_gateway import Gateway
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'system.txt';path.write_text('Fixture system instructions')
            provider=Mock(api_key='',base_url='https://fixture.invalid/v1');provider.validate_api_key.return_value=True
            with patch.dict(os.environ,CODELABOON_TASK_SYSTEM_PROMPT_FILE=str(path)):
                gateway=Gateway({'nvidia':provider},health_checks=False)
            response=Mock(status_code=200)
            with patch('codelaboon.native_gateway.requests.post',return_value=response) as post:
                gateway.request({'model':'nvidia/fixture','messages':[{'role':'system','content':'Native system'},{'role':'user','content':'task'}]},'chat')
            messages=post.call_args.kwargs['json']['messages']
            self.assertEqual(messages[0],{'role':'system','content':'Fixture system instructions'});self.assertEqual(messages[1]['content'],'Native system')
    def test_selected_worker_model_applies_to_delegated_gateway_requests(self):
        from codelaboon.native_gateway import Gateway
        provider=Mock(api_key='',base_url='https://fixture.invalid/v1');provider.validate_api_key.return_value=True
        with patch.dict(os.environ,CODELABOON_HEADLESS_TASK='1',CODELABOON_TASK_MODEL='nvidia/selected-worker'):
            gateway=Gateway({'nvidia':provider},health_checks=False)
        with patch('codelaboon.native_gateway.requests.post',return_value=Mock(status_code=200)) as post:
            gateway.request({'model':'nvidia/native-subagent-default','messages':[{'role':'user','content':'task'}]},'chat')
        self.assertEqual(post.call_args.kwargs['json']['model'],'selected-worker')
