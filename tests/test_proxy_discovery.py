"""Desktop startup requests must discover usable models without inference."""
import io
import json
import unittest
from unittest.mock import patch

import requests

from codelaboon.native_gateway import Gateway,serve
from codelaboon import proxy


class DiscoveryTests(unittest.TestCase):
    def test_query_pagination_metadata_and_authentication(self):
        models=[{'id':'free','name':'free (Auto)'},{'id':'local/test','name':'Local test'},{'id':'claude/test','name':'Claude test'}]
        with patch.object(Gateway,'models',return_value=models),serve({}) as (gateway,url),requests.Session() as client:
            client.trust_env=False
            headers={'x-api-key':gateway.token,'anthropic-version':'2023-06-01'}
            self.assertEqual(client.get(url+'/models?limit=1').status_code,401)
            first=client.get(url+'/models?limit=1',headers=headers)
            self.assertEqual(first.status_code,200)
            self.assertEqual(first.json()['first_id'],'free');self.assertTrue(first.json()['has_more'])
            self.assertEqual(first.json()['data'][0]['created_at'],'1970-01-01T00:00:00Z')
            second=client.get(url+'/models',params={'limit':1,'after_id':first.json()['last_id']},headers=headers).json()
            self.assertEqual(second['data'][0]['id'],'local/test');self.assertTrue(second['has_more'])
            last=client.get(url+'/models',params={'limit':1,'after_id':second['last_id']},headers=headers).json()
            self.assertEqual(last['last_id'],'claude/test');self.assertFalse(last['has_more'])
            previous=client.get(url+'/models',params={'limit':1,'before_id':last['first_id']},headers=headers).json()
            self.assertEqual(previous['first_id'],'local/test');self.assertTrue(previous['has_more'])
            empty=client.get(url+'/models',params={'after_id':last['last_id']},headers=headers).json()
            self.assertEqual(empty['data'],[]);self.assertIsNone(empty['first_id']);self.assertFalse(empty['has_more'])
            for query in ('limit=0','limit=-1','limit=1001','limit=bad','limit=','limit=1&limit=2','after_id=unknown','after_id=free&before_id=local/test'):
                with self.subTest(query=query):self.assertEqual(client.get(url+'/models?'+query,headers=headers).status_code,400)
            # OpenAI callers without pagination keep the complete catalogue.
            plain=client.get(url+'/models',headers={'Authorization':'Bearer '+gateway.token}).json()
            self.assertEqual([row['id'] for row in plain['data']],[row['id'] for row in models])

    def test_empty_catalogue_and_anthropic_default_page_size(self):
        with patch.object(Gateway,'models',return_value=[]),serve({}) as (gateway,url),requests.Session() as client:
            client.trust_env=False
            headers={'x-api-key':gateway.token,'anthropic-version':'2023-06-01'}
            self.assertEqual(client.get(url+'/models?limit=20',headers=headers).json(),{
                'object':'list','data':[],'has_more':False,'first_id':None,'last_id':None})
            with patch.object(Gateway,'models',return_value=[{'id':str(i),'name':str(i)} for i in range(25)]):
                page=client.get(url+'/models',headers=headers).json()
                self.assertEqual(len(page['data']),20);self.assertTrue(page['has_more'])

    def test_desktop_configuration_uses_explicit_route_without_tokens_or_provider_requests(self):
        for model in ('free','local/test'):
            with patch('codelaboon.cli.CodelaboonCLI.load_providers') as providers,patch.object(proxy,'credential') as token,patch('sys.stdout',new_callable=io.StringIO) as output:
                proxy.main(['--desktop-models','--model',model])
                settings=json.loads(output.getvalue())
                self.assertFalse(settings['modelDiscoveryEnabled'])
                self.assertEqual(settings['inferenceModels'][0]['name'],model)
                self.assertNotIn('behavesAs',settings['inferenceModels'][0])
                providers.assert_not_called();token.assert_not_called()
