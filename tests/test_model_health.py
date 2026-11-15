import json
import os
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest.mock import patch

from codelaboon import model_health as health,free_auto
from codelaboon.native_gateway import Gateway
from providers.compatible import CompatibleProvider,ZaiFreeProvider
from providers.kilo.kilo_provider import KiloProvider


class Provider(CompatibleProvider):
    keyless=True
    base_url='http://127.0.0.1:1234/v1'
    def list_models(self):
        self.live_models=list(self.models)
        return self.models


class Response:
    def __init__(self,body,status=200):self.body=body;self.status_code=status
    def iter_content(self,*args):yield json.dumps(self.body).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.environment=patch.dict(os.environ,{'CODELABOON_CONFIG_DIR':self.directory.name,'CODELABOON_MODEL_CHECKS':'1'})
        self.environment.start();self.addCleanup(self.environment.stop)
        self.provider=Provider('',models=['current'])

    def test_real_ids_replace_curated_guesses_and_empty_live_is_authoritative(self):
        self.provider.models=['new-free']
        self.assertEqual([m.model for m in free_auto.ranked({'kilo':self.provider})],['new-free'])
        self.provider.live_models=[]
        self.assertEqual(free_auto.ranked({'kilo':self.provider}),[])

    def test_missing_and_rate_limit_are_distinct_and_expire(self):
        health.observe('kilo',self.provider,'current','missing')
        self.assertTrue(health.blocked('kilo',self.provider,'current'))
        self.assertEqual(free_auto.ranked({'kilo':self.provider}),[])
        health.observe('kilo',self.provider,'current','rate_limited',delay=1)
        with patch('time.time',return_value=time.time()+2):
            self.assertFalse(health.blocked('kilo',self.provider,'current'))

    def test_endpoint_and_credentials_isolate_health_without_storing_secrets(self):
        self.provider.api_key='secret-one'
        health.observe('kilo',self.provider,'current','missing')
        self.provider.api_key='secret-two'
        self.assertIsNone(health.record('kilo',self.provider,'current'))
        self.provider.api_key='secret-one';self.provider.base_url='http://different/v1'
        self.assertIsNone(health.record('kilo',self.provider,'current'))
        text=(Path(self.directory.name)/'model-health.json').read_text()
        self.assertNotIn('secret-one',text)
        self.assertNotIn('http://127',text)

    def test_discovery_retires_missing_ids_and_recovers_reintroduced_ids(self):
        self.provider.default_models=['retired']
        health.discover('kilo',self.provider)
        self.assertEqual(health.record('kilo',self.provider,'retired')['status'],'missing')
        self.provider.models=['retired'];self.provider.live_models=None
        health.discover('kilo',self.provider)
        self.assertIsNone(health.record('kilo',self.provider,'retired'))

    def test_picker_requires_verified_tool_roundtrip_and_keeps_auto(self):
        gateway=Gateway({'kilo':self.provider})
        rows=[{'id':'free','name':'free (Auto)','api':'chat'},{'id':'kilo/current','name':'current','api':'chat'}]
        self.assertEqual(len(gateway.visible(rows)),1)
        health.observe('kilo',self.provider,'current','working',False)
        self.assertEqual(len(gateway.visible(rows)),1)
        health.observe('kilo',self.provider,'current','working',True)
        self.assertEqual(len(gateway.visible(rows)),2)
        gateway.closed.set()

    def test_probe_checks_tools_and_tool_results_not_just_http200(self):
        requests=[]
        def request(gateway,body,api,**kwargs):
            requests.append(body)
            text=' '.join(str(m.get('content','')) for m in body['messages'])
            nonce=re.search('HEALTH_[0-9a-f]+',text).group()
            if body.get('tools') and not any(row['role']=='tool' for row in body['messages']):
                answer={'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'health_echo','arguments':json.dumps({'value':nonce})}}]}
            else:
                tool=next((row for row in body['messages'] if row['role']=='tool'),None)
                answer={'role':'assistant','content':tool['content'] if tool else nonce}
            return Response({'choices':[{'message':answer}]})
        with patch('codelaboon.native_gateway.Gateway.request',request):
            row=health.probe('kilo',self.provider,'current')
        self.assertEqual((row['status'],row['tools']),('working',True))
        self.assertEqual(len(requests),3)
        self.assertTrue(health.verified('kilo',self.provider,'current',coding=True))

    def test_http200_error_and_empty_content_are_not_healthy(self):
        for value in ({'error':{'message':'model not found'}},{'choices':[{'message':{'content':''}}]}):
            with patch('codelaboon.native_gateway.Gateway.request',return_value=Response(value)):
                row=health.probe('kilo',self.provider,'current')
            self.assertNotEqual(row['status'],'working')

    def test_rate_limit_stops_probing_remaining_provider_models(self):
        self.provider.models=['one','two','three']
        with patch('codelaboon.native_gateway.Gateway.request',return_value=Response({'error':'rate limit'},429)) as request:
            rows=health.check_provider('kilo',self.provider,force=True)
        self.assertEqual(request.call_count,1)
        self.assertEqual([row['status'] for row in rows],['rate_limited','deferred','deferred'])

    def test_corrupt_cache_cannot_break_routing(self):
        path=Path(self.directory.name)/'model-health.json'
        for text in ('broken','{"format":1,"models":[],"catalogs":{}}','{"format":1,"models":{"x":{}},"catalogs":{}}'):
            path.write_text(text)
            self.assertFalse(health.blocked('kilo',self.provider,'current'))

    def test_paid_credentials_are_not_checked_as_free(self):
        gemini=Provider('paid-api-key')
        self.assertFalse(health.eligible('gemini',gemini))
        class Paid(Provider):
            def _pat(self):return 'paid-cloud-pat'
        self.assertFalse(health.eligible('qoder',Paid('')))

    def test_scope_reads_no_lock_file_when_cache_absent(self):
        self.assertIsNone(health.record('kilo',self.provider,'current'))
        self.assertFalse((Path(self.directory.name)/'model-health.lock').exists())

    def test_zai_free_prices_fail_closed_and_never_accept_paid_flash(self):
        provider=ZaiFreeProvider('key')
        class Price:
            text='> | GLM-4.7-Flash | Free | Free | Free | Free |\n| GLM-5.3-Flash | $1 | $1 | Free | $1 |'
            def raise_for_status(self):pass
        with patch('providers.compatible.requests.get',return_value=Price()):
            self.assertTrue(provider.accepts({'id':'glm-4.7-flash'}))
            self.assertFalse(provider.accepts({'id':'glm-5.3-flash'}))
        provider.prices_until=0
        import requests
        with patch('providers.compatible.requests.get',side_effect=requests.Timeout):
            self.assertFalse(provider.accepts({'id':'glm-4.7-flash'}))

    def test_one_missing_model_does_not_disable_working_model_on_same_provider(self):
        from unittest.mock import MagicMock
        self.provider.models=['retired','current']
        gateway=Gateway({'kilo':self.provider})
        dead=MagicMock(status_code=404);good=MagicMock(status_code=200)
        with patch('codelaboon.native_gateway.requests.post',side_effect=[dead,good]) as post:
            self.assertIs(gateway.request({'model':'free','messages':[]},'chat'),good)
        self.assertEqual(post.call_count,2)
        self.assertNotIn('kilo',gateway.cooldowns)
        self.assertTrue(health.blocked('kilo',self.provider,'retired'))
        self.assertFalse(health.blocked('kilo',self.provider,'current'))

    def test_runtime_rate_limit_is_not_replayed_against_every_provider_model(self):
        from unittest.mock import MagicMock
        self.provider.models=['one','two']
        gateway=Gateway({'kilo':self.provider})
        with patch('codelaboon.native_gateway.requests.post',return_value=MagicMock(status_code=429)) as post:
            with self.assertRaises(ValueError):gateway.request({'model':'free','messages':[]},'chat')
        self.assertEqual(post.call_count,1)

    def test_explicit_live_empty_and_malformed_catalog_are_different(self):
        from unittest.mock import MagicMock
        provider=KiloProvider('',models=['old'])
        response=MagicMock(status_code=200)
        response.json.return_value={'unexpected':[]}
        with patch('providers.kilo.kilo_provider.requests.get',return_value=response):
            self.assertEqual(provider.list_models(),['old'])
            self.assertIsNone(provider.live_models)
        response.json.return_value={'data':[]}
        with patch('providers.kilo.kilo_provider.requests.get',return_value=response):
            self.assertEqual(provider.list_models(),[])
            self.assertEqual(provider.live_models,[])

    def test_unchecked_models_are_hidden_from_manual_lists(self):
        self.assertEqual(free_auto.candidates({'kilo':self.provider}),[])
        health.observe('kilo',self.provider,'current','working',True)
        self.assertEqual(free_auto.candidates({'kilo':self.provider})[0][1],'current')

    def test_incremental_background_budget_prioritizes_unchecked_models(self):
        self.provider.models=['limited','unchecked']
        health.observe('kilo',self.provider,'limited','rate_limited')
        with patch('codelaboon.model_health.probe',return_value={'provider':'kilo','model':'unchecked','status':'working','tools':True}) as probe:
            rows=health.check_provider('kilo',self.provider,limit=1)
        self.assertEqual(probe.call_count,1)
        self.assertEqual(probe.call_args.args[2],'unchecked')
        self.assertEqual(rows[0]['model'],'unchecked')

    def test_openrouter_zero_price_metadata_rejects_nonzero_free_alias(self):
        from providers.compatible import OpenRouterFreeProvider
        provider=OpenRouterFreeProvider('key')
        self.assertFalse(provider.accepts({'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0.1'}}))
        self.assertFalse(provider.accepts({'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0','request':'0.01'}}))
        self.assertTrue(provider.accepts({'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0','request':'0'}}))

    def test_sse_probe_collects_fragmented_function_arguments(self):
        chunks=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'call','function':{'name':'health_echo','arguments':'{'}}]}}]},
                {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'arguments':'"value":"ok"}'}}]}}]}]
        class Stream:
            status_code=200
            def iter_content(self,size):yield ''.join('data: '+json.dumps(c)+'\n\n' for c in chunks).encode()
        value,error=health.wire(Stream(),1)
        self.assertIsNone(error)
        self.assertEqual(json.loads(value['tool_calls'][0]['function']['arguments']),{'value':'ok'})

    def test_verified_coding_routes_precede_unchecked_provider_fallbacks(self):
        self.provider.models=['one','two']
        other=Provider('',models=['deepseek-v4.1-flash-free'])
        for model in self.provider.models:health.observe('kilo',self.provider,model,'working',True)
        routes=Gateway({'ourfree':other,'kilo':self.provider}).routes('free')
        self.assertEqual(routes[:2],[('kilo','one'),('kilo','two')])

    def test_retry_after_defers_later_sweeps_without_retiring_models(self):
        self.provider.models=['one','two']
        response=Response({'error':'rate limit'},429)
        response.headers={'Retry-After':'600'}
        with patch('codelaboon.native_gateway.Gateway.request',return_value=response) as request:
            first=health.check_provider('kilo',self.provider,force=True)
            second=health.check_provider('kilo',self.provider,force=True)
        self.assertEqual(request.call_count,1)
        self.assertEqual(first[0]['status'],'rate_limited')
        self.assertEqual(second[0]['status'],'deferred')
        self.assertGreater(second[0]['retry_at'],time.time()+590)
        self.assertIsNone(health.record('kilo',self.provider,'two'))

    def test_cache_write_failure_does_not_break_successful_inference(self):
        self.provider.chat=lambda *args,**kwargs:'reply'
        with patch('codelaboon.model_health._observe',side_effect=PermissionError('read only cache')):
            chosen,reply=free_auto.chat({'kilo':self.provider},[{'role':'user','content':'hello'}])
        self.assertEqual(reply,'reply')
        self.assertEqual(chosen.model,'current')


if __name__=='__main__':unittest.main()
