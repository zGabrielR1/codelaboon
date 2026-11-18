"""Task conversations execute real scheduler turns; provider exhaustion stays retryable."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,Mock,patch

import requests

from codelaboon import engine_tasks,task_api,task_conversation,work,watch,model_health
from codelaboon.native_gateway import Gateway,serve,retry_delay


class TaskChatExecution(unittest.TestCase):
    def test_automatic_next_attempt_receives_independent_check_failure_not_just_worker_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'result.json').write_text(json.dumps({'status':'failed','verification':'failed','exit_code':1}))
            (root/'reply.txt').write_text('I believe the fixture is fixed')
            (root/'check-0.log').write_text('AssertionError: fixture output still differs')
            feedback=watch.progress_tail(root)
            self.assertIn('verification: failed',feedback)
            self.assertIn('AssertionError: fixture output still differs',feedback)
            self.assertIn('I believe the fixture is fixed',feedback)

    def test_jcode_task_captures_actual_json_reply_without_capturing_normal_interactive_sessions(self):
        from codelaboon import jcode_engine
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reply=root/'reply.txt'
            process=Mock(returncode=0);process.communicate.return_value=(json.dumps({'text':'The workers finished the fixture.'}),None)
            process.poll.return_value=0
            with patch.dict(os.environ,CODELABOON_TASK_REPLY_FILE=str(reply)),patch('codelaboon.jcode_engine.subprocess.Popen',return_value=process) as spawn:
                self.assertEqual(jcode_engine.run('jcode',['run','fixture'],[{'id':'free','api':'chat'}],'http://127.0.0.1:1/v1','fixture-token',home=root/'native'),0)
                self.assertIn('--json',spawn.call_args.args[0])
                self.assertEqual(reply.read_text(),'The workers finished the fixture.')

    def test_attachment_prompt_is_not_a_second_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt=Path(directory)/'task with spaces.md';prompt.write_text('Fixture task')
            for engine in ('opencode','kilo'):
                argv=engine_tasks.command(engine,'free',prompt)
                self.assertEqual(argv[argv.index('--file')+1:],[str(prompt)])
                self.assertIn('Execute the attached task specification.',argv[:argv.index('--file')])

    def test_completed_task_replies_and_follow_up_run_as_two_conversation_turns(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_CONFIG_DIR=directory):
            root=Path(directory);config=root/'work.json';work.initialize(config)
            identity=work.add(root,'Inspect the fixture',[['python','-c','pass']],config,
                scope='Fixture project only',swarm={'controller':'worker','engine':'opencode','workers':1,'timeout':30,'interval':60,'cycles':1,'model':'free'})
            runtime=root/'work-runtime';replies=[]
            def execute(argv,cwd,output,timeout,**kwargs):
                output=Path(output);output.write_text('engine diagnostic, not a chat reply')
                if output.name=='output.log':
                    replies.append('Worker answer '+str(len(replies)+1))
                    Path(kwargs['env']['CODELABOON_TASK_REPLY_FILE']).write_text(replies[-1])
                return 0
            with patch('codelaboon.watch.execute',side_effect=execute):
                watch.run(config,once=True)
                self.assertIn(identity,json.loads((runtime/'state.json').read_text())['done'])
                task_conversation.post(runtime,identity,'followup','Now explain the fixture result')
                watch.run(config,once=True)
            events=task_conversation.attempt_events(runtime,identity)
            self.assertEqual([row['text'] for row in events if row.get('kind')=='reply'],replies)
            self.assertEqual(len(replies),2)
            prompts=[p.read_text() for p in runtime.glob('*/prompt.md')]
            self.assertTrue(any('Now explain the fixture result' in text and 'Worker answer 1' in text for text in prompts))
            self.assertIn(identity,json.loads((runtime/'state.json').read_text())['done'])

    def test_followup_does_not_remove_pause_stop_or_provider_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);identity='fixture';task={'id':identity,'swarm':{'cycles':1}}
            task_conversation.post(root,identity,'one','Continue')
            control=task_conversation.controls(root,identity);(control/'PAUSE').touch()
            state={'done':[identity],'next_run':{identity:999},'cooldowns':{'swarm-fixture':999}}
            self.assertTrue(task_conversation.pending_turns(root,{identity:task},state))
            self.assertTrue((control/'PAUSE').exists());self.assertEqual(state['cooldowns'],{'swarm-fixture':999})
            state['done']=[identity];(control/'STOP').touch()
            self.assertFalse(task_conversation.pending_turns(root,{identity:task},state));self.assertEqual(state['done'],[identity])

    def test_completed_conversation_accepts_api_turn_and_keeps_notes_out_of_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'state.json').write_text(json.dumps({'done':['fixture']}))
            task={'id':'fixture','swarm':{'engine':'opencode'}}
            worker={'running':True,'pending':[],'service':{'features':['operator-interventions','task-conversations']}}
            with patch('codelaboon.task_api.selected',return_value=(root/'work.json',root,task)),patch('codelaboon.work.status',return_value=worker):
                task_api.message({'task':'fixture','message_id':'one','text':'Continue the conversation'})
                task_api.message({'task':'fixture','message_id':'two','text':'Private note','mode':'note'})
            content,_=task_conversation.context(root,task)
            self.assertIn('Continue the conversation',content);self.assertNotIn('Private note',content)

    def test_actual_partial_reply_is_distinct_from_logs_and_failed_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'attempt';attempt.mkdir()
            (attempt/'result.json').write_text(json.dumps({'task':'fixture','started':1,'status':'running','phase':'verifying'}))
            with patch.dict(os.environ,CODELABOON_TASK_REPLY_FILE=str(attempt/'reply.txt')):
                task_conversation.save_reply('Working on the fixture',partial=True)
                events=task_conversation.attempt_events(root,'fixture')
                self.assertTrue(next(row for row in events if row['kind']=='reply')['partial'])
                task_conversation.save_reply('The change is ready')
            (attempt/'result.json').write_text(json.dumps({'task':'fixture','started':1,'finished':2,'status':'failed','verification':'failed'}))
            events=task_conversation.attempt_events(root,'fixture')
            self.assertFalse(next(row for row in events if row['kind']=='reply')['partial'])
            self.assertIn('A project check failed',events[-1]['text']);self.assertIn('check output',events[-1]['text'])


class FreeRouteFailures(unittest.TestCase):
    def test_exhausted_free_routes_return_503_retry_after_and_do_not_look_like_local_failure(self):
        provider=Mock(base_url='https://fixture.example/v1',api_key='')
        provider.credential.return_value=''
        upstream=Mock(status_code=429,headers={'Retry-After':'120'})
        with serve({'kilo':provider}) as (gateway,url),patch.object(gateway,'routes',return_value=[('kilo','free-model')]),patch('codelaboon.native_gateway.requests.post',return_value=upstream),requests.Session() as client:
            gateway.health_checks=False;client.trust_env=False
            result=client.post(url+'/chat/completions',headers={'Authorization':'Bearer '+gateway.token},json={'model':'free','messages':[]},timeout=5)
            self.assertEqual(result.status_code,503)
            self.assertGreaterEqual(int(result.headers['Retry-After']),119)
            self.assertIn('local gateway is running',result.json()['error']['message'])
            upstream.close.assert_called_once()

    def test_provider_backoff_survives_gateway_restart_and_changes_with_key(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_CONFIG_DIR=directory,CODELABOON_MODEL_CHECKS='1'):
            provider=Mock(base_url='https://fixture.example/v1',api_key='first')
            model_health.defer('kilo',provider,120)
            self.assertGreater(model_health.cooldown('kilo',provider),110)
            provider.api_key='second'
            self.assertEqual(model_health.cooldown('kilo',provider),0)

    def test_other_free_provider_is_tried_before_reporting_exhaustion(self):
        provider=Mock(base_url='https://fixture.example/v1',api_key='');provider.credential.return_value=''
        gateway=Gateway({'kilo':provider,'pollinations':provider},health_checks=False)
        limited=Mock(status_code=429,headers={'Retry-After':'30'});answer=Mock(status_code=200)
        try:
            with patch.object(gateway,'routes',return_value=[('kilo','one'),('kilo','two'),('pollinations','three')]),patch('codelaboon.native_gateway.requests.post',side_effect=[limited,answer]) as post:
                self.assertIs(gateway.request({'model':'free','messages':[]},'chat'),answer)
                self.assertEqual(post.call_count,2)
                self.assertEqual(post.call_args.kwargs['json']['model'],'three')
        finally:gateway.local.close()
