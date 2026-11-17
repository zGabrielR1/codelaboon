"""Task creation and desktop gateway regression coverage, without live inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,Mock,patch

import requests

from codelaboon.native_gateway import Gateway,serve
from codelaboon.proxy import credential


class DesktopProxyTests(unittest.TestCase):
    def test_builtin_desktop_model_reaches_selected_backend(self):
        provider=MagicMock(base_url='http://127.0.0.1:1234/v1')
        provider.validate_api_key.return_value=True
        provider.credential.return_value=''
        response=MagicMock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':'fixture reply'},'finish_reason':'stop'}]}
        with serve({'local':provider},model_alias='local/fixture') as (gateway,url),patch.object(gateway.local,'post',return_value=response) as upstream,requests.Session() as client:
            client.trust_env=False
            answer=client.post(url+'/messages',headers={'Authorization':'Bearer '+gateway.token},json={
                'model':'claude-sonnet-4-6','messages':[{'role':'user','content':'fixture'}],'max_tokens':40})
            self.assertEqual(answer.status_code,200)
            self.assertEqual(answer.json()['content'][0]['text'],'fixture reply')
            self.assertEqual(upstream.call_args.kwargs['json']['model'],'fixture')

    def test_credential_survives_restart_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'proxy.token'
            first=credential(path)
            self.assertGreaterEqual(len(first),32)
            self.assertEqual(credential(path),first)
            path.write_text('invalid')
            with self.assertRaises(ValueError):credential(path)

    def test_desktop_auth_discovery_messages_stream_and_token_count(self):
        upstream=Mock(status_code=200,headers={'Content-Type':'text/event-stream'},codelaboon_google_oauth=False)
        upstream.iter_content.return_value=iter([b'event: message_stop\ndata: {"type":"message_stop"}\n\n'])
        with patch.object(Gateway,'models',return_value=[{'id':'free','name':'free (Auto)'}]),patch.object(Gateway,'request',return_value=upstream) as route:
            with serve({},token='x'*40,model_alias='free') as (_,url),requests.Session() as client:
                client.trust_env=False
                self.assertEqual(client.get(url+'/models').status_code,401)
                for headers in ({'Authorization':'Bearer '+'x'*40},{'x-api-key':'x'*40}):
                    self.assertEqual(client.get(url+'/models',headers=headers).json()['data'][0]['id'],'free')
                body={'model':'claude-sonnet-4-6','stream':True,'messages':[{'role':'user','content':'fixture'}]}
                result=client.post(url+'/messages',headers=headers,json=body)
                self.assertEqual(result.status_code,200);self.assertIn('message_stop',result.text)
                self.assertEqual(route.call_args.args[1],'anthropic')
                self.assertGreater(client.post(url+'/messages/count_tokens',headers=headers,json=body).json()['input_tokens'],0)
            upstream.close.assert_called_once()

    def test_builtin_aliases_route_but_explicit_provider_ids_stay_explicit(self):
        gateway=Gateway({},health_checks=False);gateway.model_alias='local/fixture'
        try:
            with patch('codelaboon.anthropic_bridge.MessagesResponse'):
                # Capture the transformed body at the bridge boundary, before any transport.
                with patch('codelaboon.anthropic_bridge.to_chat',side_effect=RuntimeError('captured')) as convert:
                    for name in ('sonnet','claude-sonnet-4-6'):
                        with self.assertRaisesRegex(RuntimeError,'captured'):gateway.request({'model':name},'anthropic')
                        self.assertEqual(convert.call_args.args[0]['model'],'local/fixture')
                    with self.assertRaisesRegex(RuntimeError,'captured'):gateway.request({'model':'other/explicit'},'anthropic')
                    self.assertEqual(convert.call_args.args[0]['model'],'other/explicit')
        finally:gateway.local.close()


@unittest.skipUnless(importlib.util.find_spec('textual'),'Optional Textual extra')
class TaskCreationTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_validate_retry_and_open_queued_task(self):
        from codelaboon.task_tui import TaskApp,TaskCreateScreen
        from textual.widgets import Input,TextArea,Label
        state={'tasks':[],'worker':{'running':False}}
        def queue(body):
            if body['objective']=='':raise ValueError('Provide a valid objective')
            state['tasks']=[{'id':'new','title':body['objective'],'objective':body['objective'],'engine':'omp','state':'queued','elevation':'none'}]
            return {'task':'new','worker_started':False,'message':'Queued; start worker manually'}
        with patch('codelaboon.engine_tasks.catalog',return_value=[{'id':'omp','installed':True}]),patch('codelaboon.task_api.snapshot',return_value=state),patch('codelaboon.task_api.enqueue',side_effect=queue) as enqueue,patch('codelaboon.task_api.conversation',return_value={'events':[],'messages':[]}),patch('codelaboon.task_api.logs',return_value={'text':''}):
            app=TaskApp()
            async with app.run_test(size=(100,40)) as pilot:
                await pilot.click('#new-task');await pilot.pause()
                self.assertIsInstance(app.screen,TaskCreateScreen)
                app.screen.query_one('#create-checks',TextArea).load_text('invalid JSON')
                await app.screen.action_submit();enqueue.assert_not_called()
                app.screen.query_one('#create-checks',TextArea).load_text('[["python", "-m", "unittest"]]')
                await app.screen.action_submit()
                self.assertIn('objective',str(app.screen.query_one('#create-error',Label).render()))
                app.screen.query_one('#create-objective',TextArea).load_text('Fix fixture')
                app.screen.query_one('#create-scope',Input).value='Fixture files only'
                await app.screen.action_submit();await pilot.pause()
                self.assertEqual(app.identity,'new')
                body=enqueue.call_args.args[0]
                self.assertEqual(body['cycles'],1);self.assertEqual(body['profile'],'coding')
                self.assertEqual(body['engine'],'omp')

    async def test_queue_in_flight_cannot_be_cancelled_or_submitted_twice(self):
        import asyncio
        from codelaboon.task_tui import TaskApp,TaskCreateScreen
        from textual.widgets import Input,TextArea
        pending=asyncio.Event();started=asyncio.Event()
        async def queue(body):
            started.set();await pending.wait()
            return {'task':'new','message':'Queued'}
        with patch('codelaboon.engine_tasks.catalog',return_value=[{'id':'omp','installed':True}]),patch('codelaboon.task_api.snapshot',return_value={'tasks':[],'worker':{'running':False}}):
            app=TaskApp();app.run_queue_task=queue
            async with app.run_test(size=(90,30)) as pilot:
                await pilot.press('ctrl+n');await pilot.pause()
                screen=app.screen
                screen.query_one('#create-objective',TextArea).load_text('Fixture')
                screen.query_one('#create-scope',Input).value='Fixture only'
                screen.query_one('#create-checks',TextArea).load_text('[["python", "--version"]]')
                submission=asyncio.create_task(screen.action_submit())
                await started.wait()
                screen.action_cancel();await screen.action_submit()
                self.assertIs(app.screen,screen);self.assertTrue(screen.submitting)
                pending.set();await submission;await pilot.pause()
                self.assertNotIsInstance(app.screen,TaskCreateScreen)

    async def test_missing_engine_disables_queue(self):
        from codelaboon.task_tui import TaskApp
        from textual.widgets import Button
        with patch('codelaboon.engine_tasks.catalog',return_value=[]),patch('codelaboon.task_api.snapshot',return_value={'tasks':[],'worker':{'running':False}}),patch('codelaboon.task_api.enqueue') as enqueue:
            app=TaskApp()
            async with app.run_test() as pilot:
                await pilot.press('ctrl+n');await pilot.pause()
                self.assertTrue(app.screen.query_one('#create-submit',Button).disabled)
                await app.screen.action_submit();enqueue.assert_not_called()
