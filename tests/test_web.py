import json
import threading
import unittest
from unittest.mock import Mock, patch
import requests
from codelaboon.web import create_server
from codelaboon.cli import CodelaboonCLI

class WebTests(unittest.TestCase):
    def setUp(self):
        provider=Mock(keyless=False)
        provider.validate_api_key.return_value=True
        provider.list_models.return_value=['test-model']
        provider.chat.return_value='Verified reply'
        self.provider=provider
        cli=Mock(providers={'test':provider})
        self.server=create_server(0,cli)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def test_assets_discovery_and_chat(self):
        self.assertEqual(requests.get(self.url).status_code,200)
        for asset in ('app.js','style.css','logo.svg'):
            self.assertEqual(requests.get(self.url+'/'+asset).status_code,200)
        data=requests.get(self.url+'/api/providers').json()
        self.assertNotIn('api_key',json.dumps(data))
        self.assertEqual(requests.get(self.url+'/api/models?provider=test').json()['models'],['test-model'])
        r=requests.post(self.url+'/api/chat',headers={'X-Codelaboon-Token':data['token']},json={'provider':'test','model':'test-model','messages':[{'role':'user','content':'Hello'}]})
        self.assertEqual(r.json(),{'reply':'Verified reply'})
    def test_untrusted_and_invalid_requests(self):
        self.assertEqual(requests.get(self.url,headers={'Host':'evil.example'}).status_code,403)
        self.assertEqual(requests.post(self.url+'/api/chat',json={}).status_code,403)
        token=requests.get(self.url+'/api/providers').json()['token']
        headers={'X-Codelaboon-Token':token}
        self.assertEqual(requests.post(self.url+'/api/chat',headers={**headers,'Origin':'https://evil.example'},json={}).status_code,403)
        self.assertEqual(requests.post(self.url+'/api/chat',headers=headers,json={}).status_code,400)
        self.assertEqual(requests.get(self.url+'/../pyproject.toml').status_code,404)
    def test_auth_status_is_tracked_per_account_provider(self):
        for provider in ('chatgpt','claude','gemini'):
            self.assertEqual(requests.get(self.url+'/api/auth/status?provider='+provider).json(),{'status':'idle'})
        self.assertEqual(requests.get(self.url+'/api/auth/status?provider=unknown').status_code,404)
        token=requests.get(self.url+'/api/providers').json()['token']
        self.assertEqual(requests.post(self.url+'/api/auth/unknown',headers={'X-Codelaboon-Token':token}).status_code,404)
    def test_provider_error_is_redacted(self):
        self.provider.chat.side_effect=RuntimeError('secret-api-key')
        token=requests.get(self.url+'/api/providers').json()['token']
        r=requests.post(self.url+'/api/chat',headers={'X-Codelaboon-Token':token},json={'provider':'test','model':'test-model','messages':[{'role':'user','content':'Hello'}]})
        self.assertEqual(r.status_code,502)
        self.assertNotIn('secret-api-key',r.text)

class LaunchTests(unittest.TestCase):
    def test_no_arguments_launch_tui(self):
        with patch('sys.argv',['codelaboon']),patch('codelaboon.cli.run_tui') as launch:
            CodelaboonCLI().run()
            launch.assert_called_once()
