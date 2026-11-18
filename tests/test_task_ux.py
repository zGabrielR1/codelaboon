"""Task lifecycle, native handoff, actionable checks and shared web connections."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import requests
from codelaboon import task_api,work,connections
from codelaboon.native_gateway import Gateway,serve
from codelaboon.task_lifecycle import deleted
from codelaboon.task_diagnostics import failed_check,record_failure
from codelaboon.work_queue import controls,ready
from codelaboon.watch import run
from codelaboon.web import create_server


class TaskFixture(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
  self.root=Path(self.temporary.name)
  self.environment=patch.dict(os.environ,CODELABOON_CONFIG_DIR=str(self.root),CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0');self.environment.start();self.addCleanup(self.environment.stop)
  self.config=work.initialize(self.root/'work.json')
  self.identity=work.add(self.root,'Improve the local fixture',[[sys.executable,'-c','pass']],self.config,dict(controller='worker',engine='opencode',workers=1,timeout=20,interval=30,cycles=1,model='free'))
  self.runtime=self.root/'work-runtime'
 def server(self,cli=None):
  self.http=create_server(0,cli or Mock(providers={}))
  self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
  self.addCleanup(self.thread.join,3);self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
  self.url='http://127.0.0.1:'+str(self.http.server_port)
  self.client=requests.Session();self.client.trust_env=False;self.addCleanup(self.client.close)
  self.token=self.client.get(self.url+'/api/session').json()['token']
  self.headers={'X-Codelaboon-Token':self.token}


class LifecycleTests(TaskFixture):
 def test_delete_hides_history_routes_and_stops_future_cycles_without_touching_project(self):
  project_file=self.root/'keep.py';project_file.write_text('print("keep")')
  log=self.runtime/'attempt';log.mkdir();(log/'output.log').write_text('Keep active output')
  task=task_api.selected(self.identity)[2]
  result=task_api.control(self.identity,'delete');self.assertTrue(result['deleted']);self.assertTrue(deleted(self.runtime,self.identity))
  self.assertFalse(ready(task,{},self.runtime));self.assertEqual(task_api.snapshot()['tasks'],[])
  self.assertEqual(work.status(self.config)['pending'],[])
  with self.assertRaises(ValueError):task_api.selected(self.identity)
  self.assertTrue(task_api.control(self.identity,'delete')['deleted'])
  self.assertTrue(project_file.exists());self.assertTrue((log/'output.log').exists())
  (controls(self.runtime,self.identity)/'STOP').unlink()
  self.assertFalse(ready(task,{},self.runtime))
 def test_delete_and_launch_are_authenticated_and_launch_is_explicit_post(self):
  self.server()
  self.assertEqual(self.client.post(self.url+'/api/tasks/open',json={'task':self.identity,'engine':'opencode'}).status_code,403)
  self.assertEqual(self.client.get(self.url+'/api/tasks/open',headers=self.headers).status_code,404)
  with patch('codelaboon.task_launch.launch',return_value={'task':self.identity,'engine':'opencode'}) as launch:
   response=self.client.post(self.url+'/api/tasks/open',headers=self.headers,json={'task':self.identity,'engine':'opencode','request_id':'launch-once'})
   self.assertEqual(response.status_code,202);launch.assert_called_once_with(self.identity,'opencode')
   replay=self.client.post(self.url+'/api/tasks/open',headers=self.headers,json={'task':self.identity,'engine':'opencode','request_id':'launch-once'})
   self.assertEqual(replay.json(),response.json());self.assertEqual(launch.call_count,1)
   conflict=self.client.post(self.url+'/api/tasks/open',headers=self.headers,json={'task':self.identity,'engine':'codex','request_id':'launch-once'})
   self.assertEqual(conflict.status_code,400);self.assertEqual(launch.call_count,1)
   missing=self.client.post(self.url+'/api/tasks/open',headers=self.headers,json={'task':self.identity,'engine':'opencode'})
   self.assertEqual(missing.status_code,400)
  response=self.client.post(self.url+'/api/tasks/control',headers=self.headers,json={'task':self.identity,'action':'delete'})
  self.assertTrue(response.json()['deleted'])
 def test_native_launch_uses_argument_vector_shared_environment_and_real_terminal(self):
  from codelaboon.task_launch import launch
  project=self.root/'subproject';project.mkdir()
  source=next((self.runtime/'inbox').glob('*.json'));task=json.loads(source.read_text());task['project']='subproject';source.write_text(json.dumps(task))
  with patch('codelaboon.engine_tasks.catalog',return_value=[{'id':'opencode','installed':True}]),patch('codelaboon.task_launch.shutil.which',return_value='terminal'),patch('codelaboon.task_launch.subprocess.Popen') as process:
   value=launch(self.identity,'opencode');self.assertEqual(value['task'],self.identity)
   args,options=process.call_args;self.assertIn(self.identity,args[0]);self.assertIsInstance(args[0],list);self.assertFalse(options.get('shell',False));self.assertNotIn('stdin',options)
   self.assertEqual(options['cwd'],str(project.resolve()));self.assertEqual(options['env']['CODELABOON_CONFIG_DIR'],str(self.root))
   with self.assertRaises(ValueError):launch(self.identity,'opencode; arbitrary')


class VerificationTests(TaskFixture):
 def test_independent_checks_get_time_and_diagnostics_are_saved(self):
  clock=[0]
  def execute(argv,project,output,timeout,**kwargs):
   if output.name=='output.log':
    self.assertLessEqual(timeout,16);clock[0]+=15;output.write_text('Worker report');return 0
   self.assertEqual(timeout,5);output.write_text('AssertionError: expected 2, got 1');return 1
  with patch('codelaboon.watch.execute',side_effect=execute),patch('time.monotonic',side_effect=lambda:clock[0]):run(self.config,once=True)
  record=json.loads(next(self.runtime.glob('*/result.json')).read_text())
  self.assertEqual(record['verification_reserved_seconds'],4);self.assertEqual(record['checks'][0]['exit_code'],1)
  self.assertIn('expected 2',record['failure_detail']['output']);self.assertEqual(record['failure_kind'],'verification')
  self.assertNotIn(self.identity,json.loads((self.runtime/'state.json').read_text())['done'])
  message=task_api.conversation(self.identity)['events'][-1]['text'];self.assertIn('expected 2',message);self.assertNotIn('This attempt could not finish',message)
 def test_missing_verifier_does_not_penalize_model_quality(self):
  def execute(argv,project,output,timeout,**kwargs):
   if output.name=='output.log':output.write_text('Worker completed');return 0
   output.write_text("python: can't open file 'missing.py': No such file or directory");return 127
  with patch('codelaboon.watch.execute',side_effect=execute),patch('codelaboon.routing_metrics.feedback') as feedback:
   run(self.config,once=True);feedback.assert_not_called()
  self.assertTrue((controls(self.runtime,self.identity)/'PAUSE').exists())

 def test_missing_command_and_repeated_identical_failure_pause_instead_of_loop(self):
  attempt=self.runtime/'attempt';attempt.mkdir();task={'id':self.identity};state={}
  def record(output):
   (attempt/'check-0.log').write_text(output)
   value={'status':'failed','verification':'failed','checks':[{'index':0,'argv':['python','tests.py'],'exit_code':1}]}
   record_failure(self.runtime,task,state,value,attempt);return value
  value=record('AssertionError: broken fixture');self.assertFalse(value.get('needs_attention',False))
  record('AssertionError: broken fixture');value=record('AssertionError: broken fixture');self.assertTrue(value['needs_attention']);self.assertTrue((controls(self.runtime,self.identity)/'PAUSE').exists())
  value=record("python: can't open file 'missing.py': No such file or directory")
  self.assertEqual(value['failure_kind'],'verification_configuration');self.assertIn('verification command',value['recovery'])
 def test_missing_project_fixture_is_a_repairable_test_failure(self):
  attempt=self.runtime/'attempt';attempt.mkdir();(attempt/'check-0.log').write_text("Traceback: FileNotFoundError: No such file or directory: 'fixtures/data.json'")
  value=failed_check(attempt,{'exit_code':1});self.assertEqual(value['kind'],'verification')

 def test_check_output_is_bounded_and_redacted(self):
  attempt=self.runtime/'attempt';attempt.mkdir();(attempt/'check-0.log').write_text('x'*9000+'\nAuthorization: Bearer secret\nAssertionError: fixture')
  value=failed_check(attempt,{'exit_code':1});self.assertLessEqual(len(value['output']),1800);self.assertNotIn('Bearer secret',value['output'])


class ConnectionTests(TaskFixture):
 def test_running_gateway_reloads_saved_connections_and_invalidates_old_catalogue(self):
  old=Mock();new=Mock();gateway=Gateway({'vercel':old});gateway.catalog=[{'id':'vercel/old'}];gateway.cooldowns={'vercel':999999999}
  gateway.connection_revision=connections.revision();gateway.reload_providers=Mock(return_value={'vercel':new})
  gateway.refresh_connections();gateway.reload_providers.assert_not_called()
  connections.changed();gateway.refresh_connections();self.assertIs(gateway.providers['vercel'],new);self.assertIsNone(gateway.catalog);self.assertEqual(gateway.cooldowns,{})
 def test_saved_connection_is_used_by_an_already_running_engine_gateway(self):
  class Provider:
   base_url='https://provider.example/v1'
   def __init__(self,key):self.api_key=key
   def credential(self):return self.api_key
   def validate_api_key(self):return True
  response=requests.Response();response.status_code=200;response._content=b'{"choices":[{"message":{"content":"connected"}}]}';response._content_consumed=True;response.headers['Content-Type']='application/json'
  with serve({'groq':Provider('old-fixture')},reload_providers=lambda:{'groq':Provider('new-fixture')}) as (gateway,url),requests.Session() as client:
   gateway.health_checks=False;client.trust_env=False;connections.changed()
   with patch('codelaboon.native_gateway.requests.post',return_value=response) as upstream:
    result=client.post(url+'/chat/completions',headers={'Authorization':'Bearer '+gateway.token},json={'model':'groq/fixture','messages':[{'role':'user','content':'hello'}]})
    self.assertEqual(result.status_code,200);self.assertEqual(result.json()['choices'][0]['message']['content'],'connected')
    self.assertEqual(upstream.call_args.kwargs['headers']['authorization'],'Bearer new-fixture')

 def test_web_login_reports_link_and_stores_shared_connection_revision(self):
  provider=Mock(keyless=False);provider.validate_api_key.return_value=False
  self.server(Mock(providers={'freebuff':provider}))
  done=threading.Event();release=threading.Event();self.addCleanup(release.set)
  def login(report):
   report('https://freebuff.example/login');report('Waiting for authorization');done.set();release.wait(3);provider.validate_api_key.return_value=True
  with patch('codelaboon.freebuff_auth.login',side_effect=login):
   self.assertEqual(self.client.get(self.url+'/api/connections').status_code,403)
   before=connections.revision()
   self.client.post(self.url+'/api/auth/freebuff',headers=self.headers,json={});self.assertTrue(done.wait(2))
   rows=self.client.get(self.url+'/api/connections',headers=self.headers).json()['connections'];row=next(r for r in rows if r['id']=='freebuff')
   self.assertEqual(row['login']['verification_uri'],'https://freebuff.example/login');self.assertEqual(row['login']['status'],'pending')
   release.set()
   import time
   deadline=time.monotonic()+3
   while time.monotonic()<deadline:
    row=self.client.get(self.url+'/api/auth/status?provider=freebuff').json()
    if row['status']=='connected':break
    time.sleep(.02)
   self.assertEqual(row['status'],'connected');self.assertNotEqual(before,connections.revision())
   self.assertNotIn('access_token',json.dumps(row))

if __name__=='__main__':unittest.main()
