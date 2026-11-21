"""RC21 real web fixtures, local configuration checks and hostile evidence."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from codelaboon import security_assessment as s
from codelaboon.security_checks import browser_observations, cookie_observations, PROBE_ORIGIN
from codelaboon.security_local import audit_local
from codelaboon.security_reports import compare, read_report


@contextmanager
def web_lab():
    class Handler(BaseHTTPRequestHandler):
        hardened = False
        calls = []
        def log_message(self, *args): pass
        def do_GET(self):
            self.calls.append((self.path, self.headers.get('Origin')))
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'" if self.hardened else "script-src * 'unsafe-eval'; report-uri /private-header-token")
            self.send_header('X-Content-Type-Options', 'nosniff' if self.hardened else 'invalid')
            if self.headers.get('Origin'):
                self.send_header('Access-Control-Allow-Origin', 'https://trusted.invalid' if self.hardened else self.headers['Origin'])
                self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Set-Cookie', 'session=secret-cookie; HttpOnly; Secure; SameSite=Lax' if self.hardened else 'session=secret-cookie; SameSite=None')
            self.end_headers()
            self.wfile.write(b'<html>private-body-token</html>')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port)+'/approved', Handler
    finally:
        server.shutdown(); server.server_close(); thread.join(3)


class WebSecurity(unittest.TestCase):
    def test_attack_observations_and_defensive_retest(self):
        with web_lab() as (url, handler):
            scope = s.create_scope([url], ['cors', 'browser', 'cookies'])
            before = s.assess(scope, s.identity(scope))
            rules = {row['rule'] for row in before['findings']}
            self.assertTrue({'cors-untrusted-origin-credentials', 'unrestricted-framing', 'csp-unsafe-eval', 'csp-wildcard-scripts', 'invalid-nosniff'} <= rules)
            self.assertEqual(handler.calls, [('/approved', PROBE_ORIGIN), ('/approved', None), ('/approved', None)])
            for secret in ('private-header-token', 'secret-cookie', 'private-body-token'):
                self.assertNotIn(secret, json.dumps(before))
            handler.hardened = True
            after = s.assess(scope, s.identity(scope))
            self.assertEqual(after['findings'], [])
            delta = compare(before, after)
            self.assertFalse(delta['new'])
            self.assertEqual(len(delta['not_observed_on_retest']), len(before['findings']))
            self.assertEqual(before['requests_used'], 3)
            blocked = json.loads(json.dumps(after))
            blocked['evidence'][0]['error'] = 'certificate_verification_failed'
            with self.assertRaises(ValueError): compare(before, blocked)
            missing = json.loads(json.dumps(after))
            missing['evidence'] = []
            with self.assertRaises(ValueError): compare(before, missing)

    def test_cors_wildcard_is_not_credentialed_exploit_and_framing_wildcard(self):
        policy = browser_observations([('Access-Control-Allow-Origin', '*'), ('Access-Control-Allow-Credentials', 'true'), ('Content-Security-Policy', 'frame-ancestors *')], False)
        self.assertTrue(policy['cors_wildcard'])
        self.assertFalse(policy['cors_reflects_probe_origin'])
        self.assertFalse(policy['framing_restricted'])
        duplicate = browser_observations([('Access-Control-Allow-Origin', PROBE_ORIGIN), ('Access-Control-Allow-Origin', 'https://other.invalid')], False)
        self.assertTrue(duplicate['duplicate_policy_headers'])
        self.assertFalse(duplicate['cors_reflects_probe_origin'])

    def test_expiry_checked_between_probes_and_no_additional_requests(self):
        with web_lab() as (url, handler):
            scope = s.create_scope([url], ['cors', 'browser'], max_requests=1)
            report = s.assess(scope, s.identity(scope))
            self.assertEqual(report['checks'][1]['status'], 'budget_exhausted')
            self.assertEqual(len(handler.calls), 1)
            now = time.time()
            with patch.object(s.time, 'time', side_effect=[now, now, scope['expires']+1, scope['expires']+1, scope['expires']+1]):
                expired = s.assess(scope, s.identity(scope))
            self.assertEqual(expired['requests_used'], 0)
            self.assertTrue(all(row['status']=='scope_expired' for row in expired['checks']))

    def test_scope_rejects_malformed_pins_and_port_zero(self):
        for url in ('http://127.0.0.1:0/', 'http://[fe80::1%25eth0]/'):
            with self.assertRaises(ValueError): s.target(url)
        for pins in ('127.0.0.1', [123], ['127.000.0.1'], []):
            scope = s.create_scope(['http://127.0.0.1'])
            scope['targets'][0]['addresses'] = pins
            with self.assertRaises(ValueError): s.assess(scope, s.identity(scope))

    def test_cookie_prefix_and_large_hsts_tokens(self):
        counts = cookie_observations(['__Host-id=secret; Secure; Path=/; Domain=example.invalid', '__Secure-id=secret'], True)
        self.assertEqual(counts['invalid_host_prefix'], 1)
        self.assertEqual(counts['invalid_secure_prefix'], 1)
        good = cookie_observations(['__Host-id=secret; Secure; Path=/; HttpOnly; SameSite=Lax'], True)
        self.assertFalse(any(value for key,value in good.items() if key not in ('parsed', 'unparsed')))
        policy = browser_observations([('Strict-Transport-Security', 'max-age='+'9'*5000)], True)
        self.assertTrue(policy['hsts_positive_max_age'])


class LocalConfiguration(unittest.TestCase):
    def test_key_material_redaction_limits_and_platform_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.env'
            path.write_bytes(b'-----BEGIN PRIVATE KEY-----\nsecret-private-key\n'+b'x'*70000)
            path.chmod(0o666)
            report = audit_local(directory, ['.env'])
            self.assertTrue(report['checks'][0]['truncated'])
            self.assertEqual(report['checks'][0]['sample_bytes'], 65536)
            rules = {row['rule'] for row in report['findings']}
            self.assertIn('private-key-material', rules)
            self.assertNotIn('secret-private-key', json.dumps(report))
            if os.name != 'nt':
                self.assertIn('sensitive-file-permissions', rules)
                self.assertIn('world-writable-config', rules)
                path.chmod(0o600)
                self.assertEqual(len(audit_local(directory, ['.env'])['findings']), 1)
            else:
                self.assertEqual(report['checks'][0]['permission_check'], 'not_supported')

    def test_explicit_files_only_no_escape_or_special_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'config').mkdir()
            for files in ([], 'settings', [123], ['../outside'], [str(root.resolve())], ['config'], ['.env:secret'], ['x']*101):
                with self.assertRaises(ValueError): audit_local(root, files)

    def test_symlink_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'actual').write_text('safe')
            try: (root/'link').symlink_to(root/'actual')
            except OSError: self.skipTest('Symlink creation unavailable')
            with self.assertRaises(ValueError): audit_local(root, ['link'])

    def test_nested_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'real').mkdir()
            (root / 'real' / 'settings').write_text('safe')
            try:
                (root / 'link').symlink_to(root / 'real', target_is_directory=True)
            except OSError:
                self.skipTest('Symlink creation unavailable')
            with self.assertRaises(ValueError):
                audit_local(root, ['link/settings'])

    def test_credential_candidates_are_redacted_and_can_gate_ci(self):
        from codelaboon.security_assessment import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'settings.txt'
            token = 'ghp_' + 'Z' * 36
            stripe = 'sk_live_' + 'Z' * 28
            path.write_text(f'TOKEN={token}\nSTRIPE={stripe}\nSTRIPE_TEST=sk_test_example\n')
            output = root / 'before.json'
            args = ['audit-local', '--project', directory, '--file', path.name, '--fail-on', 'high']
            with self.assertRaises(SystemExit) as gated:
                main([*args, '--output', str(output)])
            self.assertEqual(gated.exception.code, 2)
            original = output.read_text()
            self.assertNotIn(token, original)
            self.assertNotIn(stripe, original)
            candidates = [(row['rule'], row['line']) for row in json.loads(original)['findings']
                          if row['status'] == 'suspected_credential']
            self.assertEqual(candidates, [('github-token-pattern', 1), ('stripe-live-secret-pattern', 2)])
            path.write_text('TOKEN_FROM_ENV=true\n')
            main([*args, '--output', str(root / 'after.json')])
            self.assertEqual(json.loads((root / 'after.json').read_text())['findings'], [])


class ReportAndEvidence(unittest.TestCase):
    def test_compare_refuses_incomplete_or_different_coverage(self):
        before = {'format':1, 'scope_id':'fixture', 'checks':[{'target':'http://localhost:80/', 'check':'cors', 'status':'completed','evidence':'proof'}], 'evidence':[{'id':'proof','target':'http://localhost:80/','check':'cors'}], 'findings':[]}
        for change in ({'status':'inconclusive'}, {'status':'budget_exhausted'}, {'target':'http://elsewhere:80/'}):
            after = json.loads(json.dumps(before))
            after['checks'][0].update(change)
            with self.assertRaises(ValueError): compare(before, after)
        for malformed in ([], None, {'format':1, 'scope_id':'fixture', 'checks':['bad']}, {**before, 'findings':[None]}):
            with self.assertRaises(ValueError): compare(before, malformed)

    def test_xml_encoding_and_multi_address_port_scope(self):
        scope = s.create_scope(['http://127.0.0.1:8080', 'http://127.0.0.2:9090'])
        xml = '<nmaprun><host><address addr="127.0.0.1" addrtype="ipv4"/><address addr="127.0.0.2" addrtype="ipv4"/><ports><port protocol="tcp" portid="8080"><state state="open"/></port></ports></host></nmaprun>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'scan.xml'
            for raw in (xml.encode(), ('<!DOCTYPE x [<!ENTITY a "secret">]><nmaprun/>').encode('utf-16'), b'<unrelated/>', b'x'*(8*1024*1024+1)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError): s.import_nmap(scope, s.identity(scope), path)
            with self.assertRaises(ValueError): read_report(path)

    def test_cli_local_audit_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'settings').write_text('safe')
            args = ['audit-local','--project',directory,'--file','settings','--output',str(root/'report.json')]
            s.main(args)
            self.assertEqual(json.loads((root/'report.json').read_text())['findings'], [])
            with self.assertRaises(SystemExit): s.main(args)
