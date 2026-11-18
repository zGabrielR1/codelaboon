import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import requests
from codelaboon import task_chat
from codelaboon.native_gateway import Gateway,early_stream_error
from codelaboon.task_conversation import included

class TaskChatTests(unittest.TestCase):
 def test_transcript_has_real_replies_and_no_status_messages(self):
  state={'tasks':[{'id':'one','title':'Task','state':'running','project':'.'}],'worker':{'running':True}}
  history={'messages':[{'id':'m','text':'Continue','created':2}], 'events':[{'id':'r','text':'Working','created':3,'kind':'reply'},{'id':'s','text':'Started','created':1,'kind':'status'}]}
  with patch.object(task_chat.task_api,'selected',return_value=(None,None,{'prompt':'Objective'})),patch.object(task_chat.task_api,'snapshot',return_value=state),patch.object(task_chat.task_api,'conversation',return_value=history):
   value=task_chat.document('one');self.assertEqual([m['content'] for m in value['messages']],['Objective','Continue','Working'])
 def test_native_transport_posts_once_and_streams_worker_reply(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);attempt=root/'attempt';attempt.mkdir();(attempt/'reply.txt').write_text('Actual orchestrator reply');(attempt/'result.json').write_text(json.dumps({'status':'succeeded'}))
   state={'activity':'running','worker':{'running':True}}
   body={'model':'task/one','messages':[{'role':'user','content':'Continue'}],'stream':True}
   with patch.object(task_chat.task_api,'selected',return_value=(None,root,{})),patch.object(task_chat.task_api,'message',return_value={}) as post,patch.object(task_chat,'document',return_value=state):
    response=Gateway({}).request(body,'chat');included(root,'one',[response.message_id],'attempt')
    wire=b''.join(response.iter_content()).decode();self.assertIn('Actual orchestrator reply',wire);self.assertIn('[DONE]',wire);post.assert_called_once()
 def test_planning_and_worker_reply_arrive_in_one_native_turn(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);plan=root/'plan';plan.mkdir();build=root/'build';build.mkdir()
   (plan/'orchestrator-plan.md').write_text('The implementation plan')
   (plan/'result.json').write_text(json.dumps({'task':'one','stage':'plan','status':'succeeded','started':1,'finished':2}))
   (build/'reply.txt').write_text('The worker completed the change')
   (build/'result.json').write_text(json.dumps({'task':'one','stage':'build','status':'succeeded','started':3,'finished':4}))
   with patch.object(task_chat.task_api,'selected',return_value=(None,root,{})),patch.object(task_chat.task_api,'message',return_value={}),patch.object(task_chat,'document',return_value={'activity':'running','worker':{'running':True}}),patch('threading.Event.wait',return_value=False):
    response=Gateway({}).request({'model':'task/one','messages':[{'role':'user','content':'Continue'}]},'chat');included(root,'one',[response.message_id],'plan')
    text=response.json()['choices'][0]['message']['content'];self.assertIn('implementation plan',text);self.assertIn('completed the change',text)

 def test_worker_cannot_route_recursively_and_catalogue_contains_tasks(self):
  gateway=Gateway({})
  with patch.object(task_chat,'model_rows',return_value=[{'id':'task/one'}]):
   self.assertEqual(gateway.visible([]),[{'id':'task/one'}])
   with patch.dict(os.environ,CODELABOON_HEADLESS_TASK='1'):
    self.assertEqual(gateway.visible([]),[])
    with self.assertRaises(ValueError):gateway.request({'model':'task/one'},'chat')
 def test_native_http_protocols_share_the_orchestrator(self):
  from codelaboon.native_gateway import serve
  state={'activity':'paused','worker':{'running':False,'paused':True}}
  with patch.object(task_chat.task_api,'message',return_value={}) as post,patch.object(task_chat,'document',return_value=state),serve({}) as (gateway,url),requests.Session() as client:
   client.trust_env=False;headers={'Authorization':'Bearer '+gateway.token}
   chat=client.post(url+'/chat/completions',headers=headers,json={'model':'task/one','messages':[{'role':'user','content':'Continue'}]}).json()
   self.assertIn('message is saved',chat['choices'][0]['message']['content'])
   anthropic=client.post(url+'/messages',headers=headers,json={'model':'task/one','max_tokens':100,'messages':[{'role':'user','content':'Continue'}]}).json()
   self.assertIn('message is saved',anthropic['content'][0]['text'])
   responses=client.post(url+'/responses',headers=headers,json={'model':'task/one','input':'Continue'}).json()
   self.assertIn('message is saved',str(responses));self.assertEqual(post.call_count,3)

 def test_native_launch_passes_task_model_and_restores_environment(self):
  value={'id':'stable'}
  with patch.object(task_chat,'native_document',return_value=value),patch('codelaboon.session_transfer.save',return_value='stable'),patch('codelaboon.session_transfer.resume') as resume:
   task_chat.open_native('codex','one');resume.assert_called_once_with('stable','codex',model='task/one')
  self.assertNotIn('CODELABOON_TASK_CHAT_MODEL',os.environ)

class StreamGateTests(unittest.TestCase):
 def response(self,frames):
  response=requests.Response();response.status_code=200;response.headers['Content-Type']='text/event-stream';response._content=False;response._content_consumed=False
  response.iter_content=lambda **kwargs:iter(frames)
  return response
 def test_error_after_role_prelude_and_healthy_stream_replay(self):
  role=b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
  error=b'data: {"error":{"message":"AI Gateway requires a valid credit card on file"}}\n\n'
  response=self.response([role,error]);self.assertIn('credit card',early_stream_error(response))
  reply=b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n';end=b'data: [DONE]\n\n'
  response=self.response([role,reply,end]);self.assertEqual(early_stream_error(response),'');self.assertEqual(b''.join(response.iter_content()),role+reply+end)
 def test_successful_http_error_fails_over_and_cools_account(self):
  class Provider:
   api_key='';base_url='https://fixture.invalid/v1'
  first=self.response([b'data: {"error":{"message":"credit card required"}}\n\n']);first.close=lambda:None
  second=self.response([b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'])
  gateway=Gateway({'vercel_free':Provider(),'kilo':Provider()});gateway.health_checks=False
  with patch.object(gateway,'routes',return_value=[('vercel_free','one'),('vercel_free','two'),('kilo','three')]),patch('codelaboon.native_gateway.requests.post',side_effect=[first,second]) as post:
   self.assertIs(gateway.request({'model':'free','stream':True,'messages':[]},'chat'),second);self.assertEqual(post.call_count,2);self.assertIn('vercel_free',gateway.cooldowns)

if __name__=='__main__':unittest.main()
