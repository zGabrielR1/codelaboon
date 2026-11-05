import json
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from providers.chatgpt.chatgpt_provider import ChatGPTProvider
from codelaboon import chatgpt_auth as auth

class ChatGPTTests(unittest.TestCase):
    def test_live_account_catalogue_keeps_order_and_visible_names(self):
        p=ChatGPTProvider('',models=['gpt-3.5-turbo'])
        r=Mock(status_code=200)
        r.json.return_value={'models':[{'slug':'gpt-6-luna','display_name':'GPT-6 Luna','visibility':'list'},{'slug':'hidden','visibility':'hide'},{'slug':'gpt-6-sol','visibility':'list'}]}
        with patch.object(p,'_credential',return_value=('oauth-token',True)),patch('requests.get',return_value=r) as get:
            self.assertEqual(p.list_models(),['gpt-6-luna','gpt-6-sol'])
            self.assertEqual(p.model_names['gpt-6-luna'],'GPT-6 Luna')
            self.assertEqual(get.call_args.kwargs['timeout'],20)
    def test_api_discovery_ignores_old_configured_roster(self):
        p=ChatGPTProvider('key',models=['gpt-3.5-turbo'])
        r=Mock(status_code=200)
        r.json.return_value={'data':[{'id':'gpt-6-luna'},{'id':'text-embedding-3-small'},{'id':'gpt-image-1'}]}
        with patch('requests.get',return_value=r):
            self.assertEqual(p.list_models(),['gpt-6-luna'])
    def test_discovery_failure_does_not_invent_access(self):
        p=ChatGPTProvider('key')
        with patch('requests.get',return_value=Mock(status_code=401)):
            with self.assertRaises(ValueError):p.list_models()
    def test_subscription_tokens_never_go_to_custom_endpoint(self):
        p=ChatGPTProvider('',base_url='https://example.com/v1')
        with patch.object(auth,'access_token') as token:
            with self.assertRaises(ValueError):p.list_models()
            token.assert_not_called()
    def test_responses_requires_completed_event(self):
        p=ChatGPTProvider('')
        r=Mock(status_code=200)
        r.iter_lines.return_value=[b'data: {"type":"response.output_text.delta","delta":"Hello"}',b'data: {"type":"response.completed"}']
        with patch('requests.post',return_value=r) as post:
            self.assertEqual(p._subscription_chat('token','gpt-6-luna',[]),'Hello')
            self.assertFalse(post.call_args.kwargs['json']['store'])
            self.assertTrue(post.call_args.kwargs['json']['stream'])
        r.iter_lines.return_value=[b'data: {"type":"response.output_text.delta","delta":"Partial"}']
        with patch('requests.post',return_value=r):
            with self.assertRaises(ValueError):p._subscription_chat('token','model',[])
    def test_failed_stream_is_not_success(self):
        r=Mock(status_code=200)
        r.iter_lines.return_value=[b'data: {"type":"response.failed"}']
        with patch('requests.post',return_value=r):
            with self.assertRaises(ValueError):ChatGPTProvider('')._subscription_chat('token','model',[])
    def test_refresh_rotates_token_and_preserves_refresh_token(self):
        with tempfile.TemporaryDirectory() as root,patch.dict('os.environ',{'CODELABOON_CONFIG_DIR':root}):
            auth.save_record('chatgpt-session.json',{'client_id':'client','access_token':'old','refresh_token':'refresh','expires_at':0})
            r=Mock(status_code=200)
            r.json.return_value={'access_token':'new','expires_in':3600}
            with patch('requests.post',return_value=r):self.assertEqual(auth.access_token(),'new')
            self.assertEqual(auth.read_session()['refresh_token'],'refresh')
    def test_nonce_mismatch_rejected(self):
        with patch('jwt.PyJWKClient') as jwks,patch('jwt.decode',return_value={'nonce':'wrong','sub':'subject'}):
            jwks.return_value.get_signing_key_from_jwt.return_value=Mock(key='public')
            with self.assertRaises(ValueError):auth.validate_identity('token','client','expected')
    def test_identity_validation_requires_signature_issuer_audience_expiry(self):
        with patch('jwt.PyJWKClient'),patch('jwt.decode',return_value={'nonce':'ok','sub':'subject'}) as decode:
            auth.validate_identity('token','client','ok')
            self.assertEqual(decode.call_args.kwargs['issuer'],auth.ISSUER)
            self.assertEqual(decode.call_args.kwargs['audience'],'client')
            self.assertIn('exp',decode.call_args.kwargs['options']['require'])
            self.assertEqual(decode.call_args.kwargs['algorithms'],['RS256'])
