"""RC20 behavioral security/routing/elevation contracts on Linux/macOS/Windows."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from codelaboon import privilege as p,security_assessment as s,routing_metrics as m,supervision


@contextmanager
def fixture():
    class Handler(BaseHTTPRequestHandler):
        calls=[]
        def log_message(self,*args):pass
        def do_GET(self):
            self.calls.append(self.path)
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','http://user:secret@external.example/private?token=secret');body=b''
            else:
                self.send_response(200)
                self.send_header('Content-Type','text/html' if self.path in ('/','/secure') else 'text/plain')
                if self.path=='/secure':
                    self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'")
                body=b'PASSWORD=private-value' if self.path=='/.env' else b'ref: refs/heads/main\n' if self.path=='/.git/HEAD' else b'<html>fixture</html>'
            self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port),Handler
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


class SecurityLabs(unittest.TestCase):
    def test_real_vulnerable_and_hardened_headers_evidence_and_secret_redaction(self):
        with fixture() as (url,handler):
            scope=s.create_scope([url+'/',url+'/secure',url+'/.env',url+'/.git/HEAD'],['headers','exposure'])
            report=s.assess(scope,s.identity(scope));encoded=json.dumps(report)
            self.assertEqual(report['requests_used'],8)
            self.assertEqual(len([f for f in report['findings'] if f['rule']=='sensitive-file-exposure']),2)
            self.assertFalse(any(f['target'].endswith('/secure') for f in report['findings']))
            self.assertNotIn('private-value',encoded);self.assertNotIn('PASSWORD=',encoded)
            proofs={e['id'] for e in report['evidence']}
            self.assertTrue(all(f['evidence'] in proofs for f in report['findings']))
    def test_redirect_never_followed_and_credentials_redacted(self):
        with fixture() as (url,handler):
            scope=s.create_scope([url+'/redirect'],['headers']);report=s.assess(scope,s.identity(scope))
            self.assertEqual(handler.calls,['/redirect']);self.assertNotIn('secret',json.dumps(report));self.assertFalse(report['findings'])
    def test_scope_budget_tampering_expiry_and_unavailable_target(self):
        with fixture() as (url,handler):
            scope=s.create_scope([url+'/',url+'/secure'],['headers','exposure'],1)
            approved=s.identity(scope);report=s.assess(scope,approved)
            self.assertEqual(len(handler.calls),1);self.assertTrue(any(c['status']=='budget_exhausted' for c in report['checks']))
            scope['max_requests']=2
            with self.assertRaises(ValueError):s.assess(scope,approved)
            scope['expires']=0
            with self.assertRaises(ValueError):s.assess(scope,s.identity(scope))
        for target in ('file:///tmp/a','https://user:pass@example.com','http://example.com/?token=secret'):
            with self.assertRaises(ValueError):s.target(target)
    def test_nmap_import_rejects_wrong_host_port_and_xml_entities(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scan.xml';scope=s.create_scope(['http://127.0.0.1:8080'],['headers']);approved=s.identity(scope)
            xml='<nmaprun><host><address addr="127.0.0.1" addrtype="ipv4"/><ports><port protocol="tcp" portid="8080"><state state="open"/></port></ports></host></nmaprun>'
            path.write_text(xml);self.assertEqual(s.import_nmap(scope,approved,path)['findings'][0]['severity'],'info')
            for content in (xml.replace('8080','9999'),xml.replace('127.0.0.1','127.0.0.2'),xml.replace('tcp','udp'),'<!DOCTYPE x [<!ENTITY a "secret">]><nmaprun/>'):
                path.write_text(content)
                with self.assertRaises(ValueError):s.import_nmap(scope,approved,path)
    def test_tls_trust_failure_has_evidence_and_no_false_success(self):
        import datetime
        import ssl
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes,serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.datetime.now(datetime.timezone.utc)
        cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1)).sign(key,hashes.SHA256())
        with tempfile.TemporaryDirectory() as directory,fixture() as (url,handler):
            # Separate TLS fixture: existing HTTP server is used only for its handler.
            root=Path(directory);(root/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM));(root/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            server=ThreadingHTTPServer(('127.0.0.1',0),handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(root/'cert.pem',root/'key.pem');server.socket=context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                scope=s.create_scope(['https://127.0.0.1:'+str(server.server_port)],['tls']);report=s.assess(scope,s.identity(scope))
                self.assertEqual(report['findings'][0]['rule'],'tls-certificate-trust');self.assertEqual(report['evidence'][0]['error'],'certificate_verification_failed')
            finally:server.shutdown();server.server_close();thread.join(timeout=3)

    def test_ipv6_and_windows_scope_patterns(self):
        self.assertEqual(s.target('http://[::1]/'),'http://[::1]:80/')
        self.assertTrue(supervision.path_matches('reports/a.json',r'reports\*.json'))
        for pattern in (r'C:\Windows\*',r'..\outside\*',r'\\server\share\*','../*'):
            with self.assertRaises(ValueError):supervision.validate({'enabled':True,'allowed_paths':[pattern]})

    def test_jcode_native_security_overlay_preserves_user_and_native_base(self):
        from codelaboon.jcode_engine import prepare_profile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'prompt-overlay.md';path.write_text('User preference')
            prepare_profile(root,'security');self.assertIn('authorized pentesting',path.read_text());self.assertIn('User preference',path.read_text())
            prepare_profile(root,'security');self.assertEqual(path.read_text().count('codelaboon-security:start'),1)
            prepare_profile(root,'coding');self.assertEqual(path.read_text().strip(),'User preference');self.assertFalse((root/'system-prompt.md').exists())


class PrivilegeCases(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.env=patch.dict(os.environ,CODELABOON_CONFIG_DIR=self.directory.name);self.env.start();self.addCleanup(self.env.stop)
    def case(self,**options):return p.create([sys.executable,'-c','print("exact case")'],'Only disposable fixture',**options)
    def test_review_dry_run_does_not_elevate_and_requires_interactive_approval(self):
        identity,path=self.case()
        with patch('codelaboon.privilege.subprocess.call') as execute:
            self.assertEqual(p.run_case(path,identity,True)['case'],identity);execute.assert_not_called()
            with patch('sys.stdin.isatty',return_value=False):
                with self.assertRaises(ValueError):p.run_case(path,identity)
            execute.assert_not_called()
    def test_case_tamper_expiry_and_replay_fail_closed(self):
        identity,path=self.case();value=json.loads(path.read_text());value['argv'].append('unapproved');path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):p.run_case(path,identity,True)
        identity,path=self.case()
        with patch('codelaboon.privilege.time.time',return_value=time.time()+100000):
            with self.assertRaises(ValueError):p.load(path,identity)
        path.with_suffix('.used').touch()
        with self.assertRaises(ValueError):p.run_case(path,identity,True)
    def test_linux_macos_exact_argv_and_windows_native_uac_quoting(self):
        identity,path=self.case()
        for system in ('Linux','Darwin'):
            command=p.elevation_command(path,identity,system);self.assertEqual(command[:3],['sudo','-k','--']);self.assertEqual(command[-1],identity);self.assertIn('-I',command)
        command=p.elevation_command(path,identity,'Windows');decoded=base64.b64decode(command[-1]).decode('utf-16-le')
        self.assertIn('-Verb RunAs -Wait -PassThru',decoded);self.assertIn(identity,decoded);self.assertNotIn('ExecutionPolicy Bypass',decoded)
    def test_elevated_task_never_dispatched_by_background_worker(self):
        from codelaboon.work_queue import ready
        root=Path(self.directory.name)
        self.assertFalse(ready({'id':'case','elevation':'root'},{},root))
    def test_invalid_scope_and_bounds(self):
        for options in ({'ttl':0},{'timeout':86401}):
            with self.assertRaises(ValueError):self.case(**options)
        with self.assertRaises(ValueError):p.create([sys.executable],'')


class RoutingObservations(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.env=patch.dict(os.environ,CODELABOON_CONFIG_DIR=self.directory.name,CODELABOON_METRICS='1');self.env.start();self.addCleanup(self.env.stop)
        self.provider=type('Provider',(),{'api_key':'never-store-this-secret','base_url':'https://example.com/v1'})()
        m._CACHE[:]=[None,0,{}]
    def observe(self,model='fast',status='ok',first_token=.2):m.observe('fixture',self.provider,model,'coding',status,1,first_byte=.1,first_token=first_token,tokens=20)
    def test_task_quality_speed_and_credential_isolation(self):
        for _ in range(4):self.observe();self.observe('slow',first_token=10)
        self.assertGreater(m.adjustment('fixture',self.provider,'fast','coding'),m.adjustment('fixture',self.provider,'slow','coding'))
        self.assertEqual(m.adjustment('fixture',self.provider,'fast','security'),0)
        original=m.key('fixture',self.provider,'fast','coding');self.provider.api_key='other'
        self.assertNotEqual(original,m.key('fixture',self.provider,'fast','coding'))
        self.assertNotIn('never-store-this-secret',(Path(self.directory.name)/'routing.sqlite3').read_bytes().decode('latin1'))
    def test_nonstreaming_latency_contributes_to_routing(self):
        for _ in range(2):
            m.observe('fixture', self.provider, 'quick', 'general', 'ok', 0.2)
            m.observe('fixture', self.provider, 'slow', 'general', 'ok', 10)
        self.assertGreater(m.adjustment('fixture', self.provider, 'quick', 'general'),
                           m.adjustment('fixture', self.provider, 'slow', 'general'))

    def test_acceptance_feedback_idempotent_and_failed_candidates_penalized(self):
        self.observe();self.observe();trace=Path(self.directory.name)/'trace.jsonl';trace.write_text(json.dumps({'key':m.key('fixture',self.provider,'fast','coding')})+'\n')
        m.feedback(trace,True);m.feedback(trace,True);m.feedback(trace,False)
        self.assertEqual(m.report()[0]['checks_passed'],1);self.assertEqual(m.report()[0]['checks_failed'],0)
        self.observe('broken','failed');self.observe('broken','failed');self.assertLess(m.adjustment('fixture',self.provider,'broken','coding'),0)
    def test_sse_preserved_fragmented_tools_usage_and_cancelled_not_success(self):
        chunks=[b'data: {"choices":[{"delta":{"tool_',b'calls":[{"id":"a"}]}}]}\n\n',b'data: {"choices":[],"usage":{"completion_tokens":12}}\n\ndata: [DONE]\n\n']
        class Response:
            status_code=200
            def iter_content(self,*args,**kwargs):yield from chunks
            def close(self):pass
        measured=m.MeasuredResponse(Response(),'fixture',self.provider,'sse','coding',time.monotonic());self.assertEqual(b''.join(measured.iter_content()),b''.join(chunks));measured.close()
        row=next(r for r in m.report() if r['model']=='sse');self.assertEqual(row['ok'],1);self.assertEqual(row['tool_responses'],1)
        measured=m.MeasuredResponse(Response(),'fixture',self.provider,'cancel','coding',time.monotonic());stream=measured.iter_content();next(stream);stream.close()
        row=next(r for r in m.report() if r['model']=='cancel');self.assertEqual(row['cancelled'],1);self.assertEqual(row['ok'],0)
    def test_empty_http200_is_not_a_successful_model_observation(self):
        class Response:
            status_code=200
            def json(self):return {'choices':[]}
            def close(self):pass
        measured=m.MeasuredResponse(Response(),'fixture',self.provider,'empty','coding',time.monotonic())
        self.assertEqual(measured.json(),{'choices':[]});row=m.report()[0];self.assertEqual(row['failed'],1);self.assertEqual(row['ok'],0)

    def test_corrupt_observations_and_readonly_storage_do_not_break_routing(self):
        self.observe();identity=m.key('fixture',self.provider,'fast','coding')
        with m.database() as db:db.execute('UPDATE observations SET data=? WHERE id=?',(json.dumps({'ok':'bad','seconds':{},'first_token':['bad',None]}),identity))
        self.assertEqual(m.adjustment('fixture',self.provider,'fast','coding'),0)
        with patch('codelaboon.routing_metrics.database',side_effect=OSError('readonly')):self.observe()
    def test_task_classifier_and_evaluation_reporting(self):
        from codelaboon.controller_evaluation import evaluate,cases
        with patch.dict(os.environ,CODELABOON_ROUTING_TASK='planning'):
            self.assertEqual(m.task_class([{'content':'implement code'}]),'planning')
        with patch('codelaboon.controller_evaluation.review',return_value={'action':'continue'}):
            report=evaluate({'model':'fixture'})
        self.assertEqual(report['total'],len(cases()));self.assertEqual(report['missed_drifts'],4)

if __name__=='__main__':unittest.main()
