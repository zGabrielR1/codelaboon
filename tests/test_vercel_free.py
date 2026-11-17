"""Vercel Auto admits only live zero pricing and cannot fall through to paid IDs."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock,Mock,patch

import requests

from providers.compatible import VercelFreeProvider
from codelaboon import free_auto,model_health
from codelaboon.native_gateway import Gateway
from codelaboon.cli import CodelaboonCLI


def row(identity='vendor/free',**pricing):
    return {'id':identity,'type':'language','pricing':{'input':'0','output':'0',**pricing}}


def response(rows):
    result=MagicMock();result.__enter__.return_value=result
    result.json.return_value={'data':rows}
    return result


class VercelFreeTests(unittest.TestCase):
    def test_free_proxy_rejects_upstream_paid_model_fallbacks_and_byok(self):
        provider=VercelFreeProvider('key')
        with patch('providers.compatible.requests.get',return_value=response([row()])):
            provider.list_models()
            gateway=Gateway({'vercel_free':provider},health_checks=False)
            try:
                for options in ({'models':['vendor/paid']},{'byok':{'vendor':[{'apiKey':'other-key'}]}}):
                    with patch('codelaboon.native_gateway.requests.post') as post:
                        with self.assertRaises(ValueError):gateway.request({'model':'vercel_free/vendor/free','messages':[],
                            'providerOptions':{'gateway':options}},'chat')
                        post.assert_not_called()
            finally:gateway.local.close()

    def test_auto_discovers_prices_without_a_manual_model_list(self):
        provider=VercelFreeProvider('key')
        with patch.dict(os.environ,CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0'),patch('providers.compatible.requests.get',return_value=response([row()])) as get:
            self.assertEqual([entry.model for entry in free_auto.ranked({'vercel_free':provider})],['vendor/free'])
            self.assertEqual(get.call_count,1)

    def test_zero_pricing_rejects_unknown_paid_variable_and_non_text(self):
        self.assertTrue(VercelFreeProvider.zero_priced(row()))
        for candidate in (row(input='0.01'),row(output='0.01'),row(varies_by_provider=True),row(input='NaN'),
                          row(input='Infinity'),row(input=None),row(input=False),row(request='1'),
                          {'id':'free-name','type':'language'}, {**row(),'type':'image'},
                          {'id':'vendor/free','type':'language','pricing':{'input':'0'}}):
            with self.subTest(candidate=candidate):self.assertFalse(VercelFreeProvider.zero_priced(candidate))

    def test_only_live_zero_models_are_ranked_and_paid_requests_rejected(self):
        provider=VercelFreeProvider('fixture-key',models=['vendor/paid'])
        with patch.dict(os.environ,CODELABOON_MODEL_CHECKS='0',CODELABOON_METRICS='0'),patch('providers.compatible.requests.get',return_value=response([row(),row('vendor/paid',input='1'),row('vendor/variable',varies_by_provider=True)])):
            self.assertEqual(provider.list_models(),['vendor/free'])
            self.assertEqual([entry.model for entry in free_auto.ranked({'vercel_free':provider})],['vendor/free'])
            gateway=Gateway({'vercel_free':provider},health_checks=False)
            try:
                self.assertEqual(gateway.routes('free'),[('vercel_free','vendor/free')])
                with patch('codelaboon.native_gateway.requests.post') as post:
                    with self.assertRaises(ValueError):gateway.request({'model':'vercel_free/vendor/paid','messages':[]},'chat')
                    post.assert_not_called()
                    answer=Mock(status_code=200)
                    post.return_value=answer
                    self.assertIs(gateway.request({'model':'free','messages':[]},'chat'),answer)
                    self.assertEqual(post.call_args.kwargs['json']['model'],'vendor/free')
            finally:gateway.local.close()

    def test_expired_prices_failed_discovery_and_paid_repricing_fail_closed(self):
        provider=VercelFreeProvider('key',models=['vendor/free'])
        with patch('providers.compatible.requests.get',return_value=response([row()])):
            self.assertEqual(provider.list_models(),['vendor/free'])
        provider.prices_until=0
        with patch('providers.compatible.requests.get',side_effect=requests.ConnectionError),patch('providers.compatible.requests.post') as post:
            with self.assertRaises(ValueError):provider.chat('vendor/free',[])
            post.assert_not_called();self.assertEqual(provider.priced_free,set())
            self.assertEqual(provider.live_models,[])
        with patch('providers.compatible.requests.get',return_value=response([row(input='0.1')])):
            self.assertEqual(provider.list_models(),[])
            self.assertFalse(provider.accepts({'id':'vendor/free'}))

    def test_key_reuse_only_for_same_endpoint_and_health_scopes_environment(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_CONFIG_DIR=directory):
            cli=CodelaboonCLI()
            values={'vercel':{'api_key':'main-key','models':[]},'vercel_free':{'api_key':'','models':[]}}
            with patch('config.providers.get_providers_config',return_value=values):
                cli.load_providers();self.assertEqual(cli.providers['vercel_free'].api_key,'main-key')
            values['vercel_free']['base_url']='https://other.example/v1'
            with patch('config.providers.get_providers_config',return_value=values):
                cli.load_providers();self.assertEqual(cli.providers['vercel_free'].api_key,'')
            provider=VercelFreeProvider()
            with patch.dict(os.environ,AI_GATEWAY_API_KEY='first'):first=model_health.scope('vercel_free',provider)
            with patch.dict(os.environ,AI_GATEWAY_API_KEY='second'):self.assertNotEqual(first,model_health.scope('vercel_free',provider))
