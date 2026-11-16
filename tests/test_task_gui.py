"""Loopback GUI queue/control contracts with no real worker/model execution."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import os

import requests
from codelaboon import work
from codelaboon.web import create_server


class TaskGui(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        env=patch.dict(os.environ,CODELABOON_CONFIG_DIR=str(self.root),CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0')
        env.start();self.addCleanup(env.stop)
        self.engines=patch('codelaboon.engine_tasks.catalog',return_value=[{'id':engine,'installed':True,'native_swarm':engine=='jcode','worker_limit':1000 if engine=='jcode' else 1,'coordination':'fixture','prepare_command':'fixture'} for engine in ('jcode','opencode','omp','kilo','claude','codex','crush')])
        self.engines.start();self.addCleanup(self.engines.stop)
        self.start=patch('codelaboon.work.start');self.worker=self.start.start();self.addCleanup(self.start.stop)
        self.server=create_server(0,Mock(providers={}))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.client=requests.Session();self.client.trust_env=False;self.addCleanup(self.client.close)
        self.token=self.client.get(self.url+'/api/session').json()['token']
        self.headers={'X-Codelaboon-Token':self.token}
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3)
    def body(self,**values):
        return dict(request_id='fixture-request',objective='Assess the local fixture authorization boundary',project=str(self.root),
            scope='Only local fixture files; no network testing',model='free',engine='jcode',workers=2,timeout=30,interval=60,cycles=1,
            checks=[['python','-c','print("fixture check")']],profile='security',permissions='default',elevation='none',**values)
    def post(self,path,body):return self.client.post(self.url+path,headers=self.headers,json=body)
    def test_assets_auth_and_unconfigured_empty_state(self):
        for asset in ('tasks','tasks.js','tasks.css'):
            response=self.client.get(self.url+'/'+asset)
            self.assertEqual(response.status_code,200)
            self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
        self.assertEqual(self.client.get(self.url+'/api/tasks').status_code,403)
        self.assertEqual(self.client.get(self.url+'/api/tasks',headers={**self.headers,'Origin':'https://other.invalid'}).status_code,403)
        data=self.client.get(self.url+'/api/tasks',headers=self.headers).json()
        self.assertFalse(data['configured']);self.assertEqual(data['tasks'],[])
        self.worker.assert_not_called()
    def test_task_conversation_auth_idempotency_and_delivery(self):
        identity=self.post('/api/tasks',self.body()).json()['task']
        body={'task':identity,'message_id':'fixture-message','text':'Prioritize local regression evidence','mode':'guidance'}
        self.assertEqual(self.client.post(self.url+'/api/tasks/messages',json=body).status_code,403)
        with patch('codelaboon.work.running',return_value=False):
            self.assertEqual(self.post('/api/tasks/messages',body).status_code,202)
            self.assertEqual(self.post('/api/tasks/messages',body).status_code,202)
        data=self.client.get(self.url+'/api/tasks/messages?task='+identity,headers=self.headers).json()
        self.assertEqual(len(data['messages']),1)
        self.assertEqual(data['messages'][0]['delivery'],'Queued for next attempt')
        with patch('codelaboon.work.status',return_value={'running':True,'service':{'features':[]}}):
            self.assertEqual(self.post('/api/tasks/messages',{**body,'message_id':'other'}).status_code,400)
            self.assertEqual(self.post('/api/tasks/messages',{**body,'message_id':'note','mode':'note'}).status_code,202)
    def test_queue_is_idempotent_and_controls_share_the_cli_queue(self):
        body=self.body()
        first=self.post('/api/tasks',body);second=self.post('/api/tasks',body)
        self.assertEqual(first.status_code,202);self.assertEqual(first.json()['task'],second.json()['task'])
        identity=first.json()['task'];self.assertEqual(len(list((self.root/'work-runtime/inbox').glob('*.json'))),1)
        self.worker.assert_called_once()
        altered={**body,'objective':'Different objective'}
        self.assertEqual(self.post('/api/tasks',altered).status_code,400)
        self.assertEqual(self.post('/api/tasks/control',{'task':identity,'action':'pause'}).status_code,202)
        row=self.client.get(self.url+'/api/tasks',headers=self.headers).json()['tasks'][0]
        self.assertEqual(row['state'],'paused');self.assertEqual(row['engine'],'jcode')
        self.assertEqual(self.post('/api/tasks/control',{'task':identity,'action':'resume'}).status_code,202)
    def test_explicit_full_and_elevated_queue_never_runs_a_privilege_case(self):
        body={**self.body(),'permissions':'full','elevation':'administrator'}
        self.assertEqual(self.post('/api/tasks',body).status_code,400)
        with patch('codelaboon.privilege.run_case') as elevation:
            response=self.post('/api/tasks',{**body,'confirm_full':True})
            self.assertEqual(response.status_code,202);elevation.assert_not_called()
        row=self.client.get(self.url+'/api/tasks',headers=self.headers).json()['tasks'][0]
        self.assertEqual(row['state'],'awaiting elevation approval')
        self.assertEqual(self.post('/api/tasks/elevate',{}).status_code,404)
    def test_old_worker_cannot_silently_ignore_selected_engine(self):
        work.initialize(self.root/'work.json')
        runtime=self.root/'work-runtime';runtime.mkdir()
        (runtime/'service-info.json').write_text(json.dumps({'features':['continuous-swarm','task-execution-policy']}))
        with patch('codelaboon.work.running',return_value=True):
            response=self.post('/api/tasks',{**self.body(),'engine':'opencode','workers':1})
        self.assertEqual(response.status_code,400);self.assertIn('Restart',response.json()['error'])
        self.assertEqual(list((runtime/'inbox').glob('*.json')),[])
    def test_logs_are_bounded_redacted_and_task_scoped(self):
        identity=self.post('/api/tasks',self.body()).json()['task']
        attempt=self.root/'work-runtime'/'attempt';attempt.mkdir()
        (attempt/'result.json').write_text(json.dumps({'task':identity,'status':'failed','exit_code':1,'started':1}))
        (attempt/'output.log').write_text('x'*20000+'\npassword=private-value\nBearer private-token\nsk-private-key\n<script>bad()</script>')
        data=self.client.get(self.url+'/api/tasks/logs?task='+identity,headers=self.headers).json()
        self.assertTrue(data['truncated']);self.assertNotIn('private-value',data['text']);self.assertNotIn('private-token',data['text']);self.assertNotIn('sk-private-key',data['text'])
        self.assertEqual(self.client.get(self.url+'/api/tasks/logs?task=../outside',headers=self.headers).status_code,400)
    def test_invalid_body_and_portable_worker_limit_fail_before_queueing(self):
        self.assertEqual(self.post('/api/tasks',[]).status_code,400)
        self.assertEqual(self.post('/api/tasks',{**self.body(),'engine':'claude','workers':4}).status_code,400)
        self.worker.assert_not_called()
    def test_settings_are_authenticated_versioned_and_old_worker_gated(self):
        identity=self.post('/api/tasks',self.body()).json()['task']
        endpoint='/api/tasks/settings?task='+identity
        self.assertEqual(self.client.get(self.url+endpoint).status_code,403)
        row=self.client.get(self.url+endpoint,headers=self.headers).json()
        values={**row['values'],'worker_model':'nvidia/fixture','orchestrator_mode':'local','orchestrator_model':'local/fixture','worker_system_prompt':'Prefer regression evidence'}
        with patch('codelaboon.work.running',return_value=False):
            response=self.post('/api/tasks/settings',{'task':identity,'expected_revision':row['revision'],'values':values})
            self.assertEqual(response.status_code,202)
            self.assertEqual(self.post('/api/tasks/settings',{'task':identity,'expected_revision':row['revision'],'values':values}).status_code,400)
        with patch('codelaboon.work.running',return_value=True):
            self.assertEqual(self.post('/api/tasks/settings',{'task':identity,'expected_revision':response.json()['revision'],'values':values}).status_code,400)
        data=self.client.get(self.url+'/api/tasks/changes?task='+identity,headers=self.headers).json()
        self.assertIn('pre-existing',data['notice'])
