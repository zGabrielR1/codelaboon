import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from providers.compatible import HowToFixProvider,CopilotProvider
from codelaboon import task_attempts,task_api


class Providers(unittest.TestCase):
    def test_howtofix_live_catalogue_and_credit_lane_not_in_free_auto(self):
        provider=HowToFixProvider('fixture-key')
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.json.return_value={'data':[{'id':'actual-live-model'},{'id':'actual-live-model'}]}
        with patch('providers.compatible.requests.get',return_value=response) as get:
            self.assertEqual(provider.list_models(),['actual-live-model']);self.assertEqual(provider.live_models,['actual-live-model'])
        self.assertEqual(get.call_args.args[0],'https://api.howtofix.id/v1/models');self.assertFalse(get.call_args.kwargs['allow_redirects'])
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'],'Bearer fixture-key')
        from codelaboon.native_gateway import FREE_COMPATIBLE,COMPATIBLE
        self.assertIn('howtofix',COMPATIBLE);self.assertNotIn('howtofix',FREE_COMPATIBLE);self.assertNotIn('copilot',FREE_COMPATIBLE)
    def test_gateway_preserves_tools_and_uses_provider_specific_auth(self):
        from codelaboon.native_gateway import Gateway
        message=[{'role':'user','content':'Fixture only'},{'role':'tool','content':'fixture result','tool_call_id':'call'}]
        tools=[{'type':'function','function':{'name':'fixture','parameters':{'type':'object'}}}]
        for name,provider in [('howtofix',HowToFixProvider('fixture-key')),('copilot',CopilotProvider('fixture-token'))]:
            response=Mock(status_code=200)
            with patch('codelaboon.native_gateway.requests.post',return_value=response) as post:
                gateway=Gateway({name:provider},health_checks=False)
                gateway.request({'model':name+'/fixture-model','messages':message,'tools':tools,'stream':True},'chat')
                sent=post.call_args.kwargs
                self.assertEqual(sent['json']['messages'],message);self.assertEqual(sent['json']['tools'],tools)
                self.assertIn(provider.credential(),str(sent['headers']))
                if name=='copilot':self.assertEqual(sent['headers']['x-initiator'],'agent')
                self.assertEqual(gateway.routes('free'),[])

    def test_howtofix_empty_authoritative_catalog_and_no_credential_guessing(self):
        self.assertFalse(HowToFixProvider('').validate_api_key())
        provider=HowToFixProvider('fixture-key');response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.json.return_value={'data':[]}
        with patch('providers.compatible.requests.get',return_value=response):self.assertEqual(provider.list_models(),[]);self.assertEqual(provider.live_models,[])
    def test_copilot_official_host_and_supported_model_filter(self):
        with self.assertRaises(ValueError):CopilotProvider('secret',base_url='https://external.example/v1')
        provider=CopilotProvider('fixture-token')
        self.assertFalse(provider.accepts({'id':'responses-only','supported_endpoints':['/responses']}))
        self.assertFalse(provider.accepts({'id':'disabled','policy':{'state':'disabled'}}))
        self.assertEqual(provider.headers([{'role':'tool'}])['x-initiator'],'agent');self.assertEqual(provider.headers([{'role':'user'}])['x-initiator'],'user')
    def test_copilot_device_flow_slowdown_private_storage_and_public_notification(self):
        from codelaboon import copilot_auth
        def response(data):r=Mock();r.json.return_value=data;return r
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,CODELABOON_CONFIG_DIR=directory,COPILOT_GITHUB_TOKEN=''):
            notify=Mock()
            replies=[response({'device_code':'private-device','user_code':'PUBLIC-CODE','verification_uri':'https://github.com/login/device','expires_in':60,'interval':1}),response({'error':'authorization_pending'}),response({'error':'slow_down'}),response({'access_token':'fixture-oauth-secret'})]
            with patch('codelaboon.copilot_auth.requests.post',side_effect=replies),patch('codelaboon.copilot_auth.time.sleep') as sleep:
                copilot_auth.login(notify=notify)
            self.assertEqual(copilot_auth.credential(),'fixture-oauth-secret');self.assertNotIn('private-device',str(notify.call_args));self.assertNotIn('fixture-oauth-secret',str(notify.call_args))
            self.assertEqual([call.args[0] for call in sleep.call_args_list],[4,4,9])
            if os.name!='nt':self.assertEqual((Path(directory)/'copilot-session.json').stat().st_mode&0o777,0o600)
    def test_copilot_rejects_untrusted_verification_link(self):
        from codelaboon import copilot_auth
        response=Mock();response.json.return_value={'device_code':'x','user_code':'x','verification_uri':'https://external.example'}
        with patch('codelaboon.copilot_auth.requests.post',return_value=response):
            with self.assertRaises(ValueError):copilot_auth.login(notify=Mock())
    def test_devin_native_model_and_permissions_are_explicit(self):
        from codelaboon.account_engines import task_command
        with patch('codelaboon.account_engines.executable',return_value='native-devin'),patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='default'):
            argv=task_command('devin/account-default',Path('prompt with space.md'));self.assertNotIn('--model',argv);self.assertNotIn('dangerous',argv)
            with self.assertRaises(ValueError):task_command('free',Path('prompt.md'))
        with patch('codelaboon.account_engines.executable',return_value='native-devin'),patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='full'):
            argv=task_command('devin/swe-model',Path('p'));self.assertIn('dangerous',argv);self.assertIn('swe-model',argv)
    def test_devin_login_delegates_to_native_auth_not_model_inference(self):
        from codelaboon.account_engines import login
        with patch('codelaboon.account_engines.executable',return_value='native-devin'),patch('codelaboon.account_engines.subprocess.run') as run:
            login();self.assertEqual(run.call_args.args[0],['native-devin','auth','login'])


class Attempts(unittest.TestCase):
    def test_historical_output_is_task_scoped_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'older';attempt.mkdir();(attempt/'result.json').write_text(json.dumps({'task':'fixture','status':'failed','started':1}));(attempt/'output.log').write_text('Authorization: Bearer sk-fixture-secret')
            monitored={'latest_attempts':{}}
            with patch('codelaboon.task_api.selected',return_value=(root/'work.json',root,{})),patch('codelaboon.work_monitor.snapshot',return_value=monitored):
                data=task_api.logs('fixture','older');self.assertIn('[redacted]',data['text']);self.assertNotIn('fixture-secret',data['text'])
                with self.assertRaises(ValueError):task_api.logs('other','older')
                with self.assertRaises(ValueError):task_api.logs('fixture','../older')
    def test_retry_is_a_control_file_and_single_supervisor_owns_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'failed-attempt';attempt.mkdir();(attempt/'result.json').write_text(json.dumps({'task':'fixture','status':'failed','started':1}))
            task={'id':'fixture','swarm':{'engine':'jcode'}};worker={'running':True,'paused':False,'service':{'features':['task-retry']},'pending':[{'id':'fixture'}]}
            task_attempts.retry(root,task,worker);task_attempts.retry(root,task,worker)
            self.assertFalse((root/'state.json').exists())
            state={'last_attempts':{'fixture':str(attempt)},'cooldowns':{'swarm-fixture':999,'other':999},'next_run':{'fixture':999,'other':999}}
            changed,receipts=task_attempts.consume(root,{'fixture':task},state)
            self.assertTrue(changed);self.assertEqual(state['cooldowns'],{'other':999});self.assertEqual(state['next_run'],{'other':999});self.assertEqual(len(receipts),1)
    def test_retry_cannot_duplicate_running_work_or_change_privileged_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempt=root/'active';attempt.mkdir();(attempt/'result.json').write_text(json.dumps({'task':'fixture','status':'running','started':1}))
            worker={'running':True,'service':{'features':['task-retry']},'pending':[{'id':'fixture'}]}
            for task in ({'id':'fixture','swarm':{}},{'id':'fixture','swarm':{'engine':'jcode'},'elevation':'root'},{'id':'fixture','swarm':{'engine':'jcode'}}):
                with self.assertRaises(ValueError):task_attempts.retry(root,task,worker)
    def test_stale_retry_does_not_replay_newer_attempt(self):
        from codelaboon.work_queue import controls
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'old';old.mkdir();(old/'result.json').write_text(json.dumps({'task':'fixture','status':'failed'}));control=controls(root,'fixture');control.mkdir(parents=True);(control/'RETRY.json').write_text(json.dumps({'attempt':'old'}))
            state={'last_attempts':{'fixture':str(root/'new')},'cooldowns':{'swarm-fixture':999},'next_run':{}}
            changed,_=task_attempts.consume(root,{'fixture':{'swarm':{'engine':'jcode'}}},state);self.assertFalse(changed);self.assertEqual(state['cooldowns']['swarm-fixture'],999)


class PolicyPropagation(unittest.TestCase):
    def test_nested_engine_keeps_its_explicit_task_permissions(self):
        from codelaboon import swarm
        with tempfile.TemporaryDirectory() as directory,patch('codelaboon.swarm.data_dir',return_value=Path(directory)),patch.dict(os.environ,CODELABOON_WORK_PERMISSIONS='full',CODELABOON_WORK_PROFILE='coding'):
            def execute(argv,cwd,output,timeout,**kwargs):
                self.assertEqual(kwargs['env']['CODELABOON_WORK_PERMISSIONS'],'full');output.write_text('Native fixture result');return 0
            with patch('codelaboon.watch.execute',side_effect=execute):self.assertEqual(swarm.execute('Only disposable fixture',workers=1,timeout=10,engine='codex'),0)
    def test_native_account_model_rejected_before_queue_creation(self):
        from codelaboon.work_queue import validate_swarm
        options={'controller':'worker','workers':1,'timeout':30,'interval':30,'cycles':1,'model':'free','engine':'devin'}
        with self.assertRaises(ValueError):validate_swarm(options)
        self.assertEqual(validate_swarm(dict(options,model='devin/account-default'))['engine'],'devin')
    def test_malformed_retry_cannot_crash_scheduler(self):
        from codelaboon.work_queue import controls
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);control=controls(root,'fixture');control.mkdir(parents=True);(control/'RETRY.json').write_text('[]')
            state={'last_attempts':{},'cooldowns':{},'next_run':{}}
            changed,receipts=task_attempts.consume(root,{'fixture':{}},state);self.assertFalse(changed);self.assertEqual(len(receipts),1)


class KeyEndpoint(unittest.TestCase):
    def test_save_requires_csrf_and_origin_and_never_returns_secret(self):
        import threading
        import requests
        from codelaboon.web import create_server
        cli=Mock(providers={});cli._current_provider_config.return_value={'models':[]}
        server=create_server(0,cli);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            token=requests.get(url+'/api/session').json()['token'];body={'provider':'howtofix','api_key':'fixture-key-secret'}
            self.assertEqual(requests.post(url+'/api/providers/configure',json=body).status_code,403)
            headers={'X-Codelaboon-Token':token}
            self.assertEqual(requests.post(url+'/api/providers/configure',headers=dict(headers,Origin='https://foreign.example'),json=body).status_code,403)
            with patch('config.providers.save_provider_config',return_value=True) as save:
                result=requests.post(url+'/api/providers/configure',headers=headers,json=body)
                self.assertEqual(result.status_code,200);self.assertNotIn('fixture-key-secret',result.text);self.assertEqual(save.call_args.args[1]['api_key'],'fixture-key-secret')
            self.assertEqual(requests.post(url+'/api/providers/configure',headers=headers,json={'provider':'copilot','api_key':'x'}).status_code,400)
        finally:server.shutdown();server.server_close();thread.join(timeout=3)

class WorkerControls(unittest.TestCase):
    def test_controls_delegate_without_mutating_task_authority(self):
        with patch('codelaboon.task_api.configuration',return_value=(Path('work.json'),{},Path('runtime'))),patch('codelaboon.work.start') as start,patch('codelaboon.work.control') as control:
            task_api.worker_control('start');start.assert_called_once_with(Path('work.json'))
            task_api.worker_control('pause');control.assert_called_with('pause',Path('work.json'))
            task_api.worker_control('resume');control.assert_called_with('resume',Path('work.json'))
            with self.assertRaises(ValueError):task_api.worker_control('elevate')
    def test_unconfigured_worker_is_not_initialized_by_view_or_control(self):
        with patch('codelaboon.task_api.configuration',return_value=(None,None,None)),patch('codelaboon.work.start') as start:
            with self.assertRaises(ValueError):task_api.worker_control('start')
            start.assert_not_called()

class DevinInstaller(unittest.TestCase):
    def test_checksum_verified_lazy_bundle_and_bad_digest_rejection(self):
        import hashlib,io,tarfile
        from codelaboon import external_engines
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w:gz') as archive:
            content=b'fixture executable';member=tarfile.TarInfo('bin/'+('devin.exe' if os.name=='nt' else 'devin'));member.size=len(content);archive.addfile(member,io.BytesIO(content))
        bundle=data.getvalue();checksum=hashlib.sha256(bundle).hexdigest()
        release={'version':'3000.12.57','platforms':{'x86_64-unknown-linux':{'url':'https://static.devin.ai/cli/3000.12.57/fixture.tar.gz','sha256':checksum}}}
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.iter_content.return_value=[bundle]
        with tempfile.TemporaryDirectory() as directory,patch('codelaboon.external_engines.config_dir',return_value=Path(directory)),patch('codelaboon.external_engines.target',return_value='linux-x64'),patch('codelaboon.external_engines.metadata',return_value=release),patch('codelaboon.external_engines.requests.get',return_value=response),patch('codelaboon.external_engines.subprocess.run') as run:
            binary=external_engines.setup('devin');self.assertEqual(binary.read_bytes(),b'fixture executable');self.assertEqual(Path(run.call_args.args[0][0]).name,'devin.exe' if os.name=='nt' else 'devin');self.assertEqual(run.call_args.args[0][1:],["--version"])
            marker=json.loads((Path(directory)/'runtime/native-clis/devin/current.json').read_text());self.assertEqual(marker['integrity'],'sha256:'+checksum)
        release['platforms']['x86_64-unknown-linux']['sha256']='0'*64
        with tempfile.TemporaryDirectory() as directory,patch('codelaboon.external_engines.config_dir',return_value=Path(directory)),patch('codelaboon.external_engines.target',return_value='linux-x64'),patch('codelaboon.external_engines.metadata',return_value=release),patch('codelaboon.external_engines.requests.get',return_value=response),patch('codelaboon.external_engines.subprocess.run') as run:
            with self.assertRaises(RuntimeError):external_engines.setup('devin')
            run.assert_not_called()
    def test_windows_arm64_manifest_target_mapping(self):
        from codelaboon.external_engines import target
        with patch('codelaboon.external_engines.platform.system',return_value='Windows'),patch('codelaboon.external_engines.platform.machine',return_value='ARM64'):
            self.assertEqual(target('devin'),'windows-arm64')
    def test_native_open_separator_preserves_flags_as_arguments(self):
        from codelaboon.account_engines import main
        with patch('codelaboon.account_engines.executable',return_value='native-devin'),patch('codelaboon.account_engines.subprocess.call',return_value=0) as call:
            with self.assertRaises(SystemExit) as result:main(['devin','open','--','--resume','native-session'])
            self.assertEqual(result.exception.code,0);self.assertEqual(call.call_args.args[0],['native-devin','--resume','native-session'])
    def test_nonofficial_bundle_host_rejected_before_download(self):
        from codelaboon import external_engines
        release={'version':'3000.12.57','platforms':{'x86_64-unknown-linux':{'url':'https://foreign.example/cli/3000.12.57/fixture.tar.gz','sha256':'0'*64}}}
        with tempfile.TemporaryDirectory() as directory,patch('codelaboon.external_engines.config_dir',return_value=Path(directory)),patch('codelaboon.external_engines.target',return_value='linux-x64'),patch('codelaboon.external_engines.metadata',return_value=release),patch('codelaboon.external_engines.requests.get') as get:
            with self.assertRaises(RuntimeError):external_engines.setup('devin')
            get.assert_not_called()

if __name__=='__main__':unittest.main()
