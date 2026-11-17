"""Vercel gateway setup, routing, and account isolation without paid inference."""
import io
import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock,Mock,patch

import requests

from codelaboon.cli import CodelaboonCLI
from codelaboon.native_gateway import Gateway,COMPATIBLE,FREE_COMPATIBLE,serve
from providers.compatible import VercelProvider


class VercelTests(unittest.TestCase):
    def test_credentials_url_normalization_and_credit_boundary(self):
        with patch.dict(os.environ,{'AI_GATEWAY_API_KEY':'env-gateway-key'},clear=True):
            self.assertEqual(VercelProvider().credential(),'env-gateway-key')
            self.assertEqual(VercelProvider('explicit-key').credential(),'explicit-key')
        with patch.dict(os.environ,{'VERCEL_TOKEN':'account-token'},clear=True):
            self.assertFalse(VercelProvider().validate_api_key())
        for base in ('https://ai-gateway.vercel.sh','https://ai-gateway.vercel.sh/','https://ai-gateway.vercel.sh/v1/'):
            self.assertEqual(VercelProvider(base_url=base).base_url,'https://ai-gateway.vercel.sh/v1')
        for base in ('http://ai-gateway.vercel.sh','https://key@ai-gateway.vercel.sh/v1','https://ai-gateway.vercel.sh/v1/messages','https://ai-gateway.vercel.sh?key=x'):
            with self.assertRaises(ValueError):VercelProvider(base_url=base)
        self.assertIn('vercel',COMPATIBLE);self.assertNotIn('vercel',FREE_COMPATIBLE)
        gateway=Gateway({'vercel':VercelProvider('key')},health_checks=False)
        try:self.assertEqual(gateway.routes('free'),[])
        finally:gateway.local.close()

    def test_live_models_chat_and_offline_fallback(self):
        provider=VercelProvider('fixture-key',models=['anthropic/offline'])
        response=MagicMock()
        response.__enter__.return_value=response
        response.json.return_value={'data':[{'id':'anthropic/fixture'},{'id':'openai/fixture'},{'id':'anthropic/fixture'}]}
        with patch('providers.compatible.requests.get',return_value=response) as get:
            self.assertEqual(provider.list_models(),['anthropic/fixture','openai/fixture'])
            self.assertEqual(get.call_args.args[0],'https://ai-gateway.vercel.sh/v1/models')
            self.assertEqual(get.call_args.kwargs['headers']['Authorization'],'Bearer fixture-key')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
        with patch('providers.compatible.requests.get',side_effect=requests.ConnectionError):
            self.assertEqual(provider.list_models(),['anthropic/offline'])
            self.assertEqual(provider.discovery_error,'ConnectionError')
        response.json.return_value={'choices':[{'message':{'content':'fixture answer'}}]}
        with patch('providers.compatible.requests.post',return_value=response) as post:
            self.assertEqual(provider.chat('anthropic/fixture',[{'role':'user','content':'fixture'}]),'fixture answer')
            self.assertEqual(post.call_args.kwargs['json']['model'],'anthropic/fixture')
            self.assertEqual(post.call_args.args[0],'https://ai-gateway.vercel.sh/v1/chat/completions')

    def test_config_load_and_key_rotation_preserve_endpoint_and_roster(self):
        from config.providers import _default_config
        self.assertIn('vercel',_default_config())
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_CONFIG_DIR=directory):
            cli=CodelaboonCLI()
            old={'api_key':'old','base_url':'https://ai-gateway.vercel.sh','models':['anthropic/fixture']}
            with patch('config.providers.get_providers_config',return_value={'vercel':old}):
                cli.load_providers()
                self.assertIsInstance(cli.providers['vercel'],VercelProvider)
                with patch('getpass.getpass',return_value='new'),patch('config.providers.save_provider_config',return_value=True) as save,patch.object(cli,'load_providers'),patch('sys.stdout',new_callable=io.StringIO):
                    cli.configure_provider('vercel')
                self.assertEqual(save.call_args.args,('vercel',{**old,'api_key':'new'}))

    def test_proxy_messages_stream_preserves_native_fields_and_replaces_auth(self):
        provider=VercelProvider('upstream-key')
        upstream=Mock(status_code=200,headers={'Content-Type':'text/event-stream'})
        upstream.codelaboon_google_oauth=False
        upstream.iter_content.return_value=iter([b'event: message_stop\ndata: {"type":"message_stop"}\n\n'])
        body={'model':'claude-sonnet-fixture','stream':True,'max_tokens':9000,
              'system':[{'type':'text','text':'fixture','cache_control':{'type':'ephemeral'}}],
              'thinking':{'type':'adaptive'},'messages':[{'role':'user','content':'fixture'}],
              'tools':[{'name':'fixture','input_schema':{'type':'object'}}]}
        with serve({'vercel':provider},model_alias='vercel/anthropic/fixture') as (gateway,url),patch('codelaboon.native_gateway.requests.post',return_value=upstream) as post,requests.Session() as client:
            client.trust_env=False
            result=client.post(url+'/messages',headers={'Authorization':'Bearer '+gateway.token},json=body)
            self.assertEqual(result.status_code,200);self.assertIn('message_stop',result.text)
            self.assertEqual(post.call_args.args[0],'https://ai-gateway.vercel.sh/v1/messages')
            sent=post.call_args.kwargs
            self.assertEqual(sent['json'],{**body,'model':'anthropic/fixture'})
            self.assertEqual(sent['headers']['authorization'],'Bearer upstream-key')
            self.assertNotIn(gateway.token,str(sent));self.assertFalse(sent['allow_redirects'])
        upstream.close.assert_called_once()

    def test_proxy_responses_and_chat_keep_vercel_model_namespace(self):
        gateway=Gateway({'vercel':VercelProvider('key')},health_checks=False)
        try:
            for api,suffix in (('responses','responses'),('chat','chat/completions')):
                with patch('codelaboon.native_gateway.requests.post',return_value=Mock(status_code=200)) as post:
                    gateway.request({'model':'vercel/openai/fixture','messages':[],'input':'fixture'},api)
                    self.assertEqual(post.call_args.args[0],'https://ai-gateway.vercel.sh/v1/'+suffix)
                    self.assertEqual(post.call_args.kwargs['json']['model'],'openai/fixture')
        finally:gateway.local.close()

    def test_web_key_setup_is_authenticated_and_preserves_existing_values(self):
        from codelaboon.web import create_server
        cli=Mock(providers={})
        cli._current_provider_config.return_value={'models':['anthropic/fixture'],'base_url':'https://ai-gateway.vercel.sh/v1'}
        server=create_server(0,cli)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with requests.Session() as client,patch('config.providers.save_provider_config',return_value=True) as save:
                client.trust_env=False
                url='http://127.0.0.1:'+str(server.server_port)
                token=client.get(url+'/api/session').json()['token']
                body={'provider':'vercel','api_key':'fixture-private-key'}
                self.assertEqual(client.post(url+'/api/providers/configure',json=body).status_code,403)
                result=client.post(url+'/api/providers/configure',headers={'X-Codelaboon-Token':token},json=body)
                self.assertEqual(result.status_code,200);self.assertNotIn('fixture-private-key',result.text)
                self.assertEqual(save.call_args.args,('vercel',{**cli._current_provider_config.return_value,'api_key':'fixture-private-key'}))
        finally:server.shutdown();server.server_close();worker.join(2)


@unittest.skipUnless(importlib.util.find_spec('textual'),'Optional terminal UI extra')
class VercelTerminalTests(unittest.IsolatedAsyncioTestCase):
    async def test_key_dialog_uses_vercel_signup_and_saves_without_losing_configuration(self):
        from textual.app import App
        from textual.widgets import Input,Static
        from codelaboon.tui import ProviderKey
        class SetupApp(App):
            def on_mount(self):self.push_screen(ProviderKey('vercel'))
        app=SetupApp()
        app.cli=Mock()
        existing={'base_url':'https://ai-gateway.vercel.sh/v1','models':['anthropic/fixture']}
        app.cli._current_provider_config.return_value=existing
        app._save_conversation=Mock();app.history=[];app._generation=0
        app._load_models=Mock();app._update_status=Mock()
        with patch('config.providers.save_provider_config',return_value=True) as save:
            async with app.run_test(size=(100,35)) as pilot:
                await pilot.pause()
                self.assertIn('https://vercel.com/ai-gateway',' '.join(str(widget.render()) for widget in app.screen.query(Static)))
                app.screen.query_one('#provider-key',Input).value='fixture-gateway-key'
                await pilot.click('#key-save');await pilot.pause()
                self.assertEqual(save.call_args.args,('vercel',{**existing,'api_key':'fixture-gateway-key'}))
                app.cli.load_providers.assert_called_once()
                app._load_models.assert_called_once_with('vercel')
