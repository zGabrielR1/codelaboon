"""Local response probes and hostile scope regression cases."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from codelaboon import security_assessment as s
from codelaboon.security_checks import cookie_observations


class SecurityChecks(unittest.TestCase):
    def test_methods_and_cookie_probes_are_bounded_and_redacted(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_OPTIONS(self):
                calls.append((self.command, self.path))
                self.send_response(204)
                self.send_header('Allow', 'GET, PUT, DELETE, TRACE, secret-token')
                self.end_headers()
            def do_GET(self):
                calls.append((self.command, self.path))
                self.send_response(200)
                self.send_header('Set-Cookie', 'session=private-value; SameSite=None')
                self.send_header('Set-Cookie', 'other=another-secret; HttpOnly; Secure; SameSite=Lax')
                self.end_headers()

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = 'http://127.0.0.1:'+str(server.server_port)+'/exact'
            scope = s.create_scope([url], ['methods', 'cookies'], max_requests=2)
            report = s.assess(scope, s.identity(scope))
            self.assertEqual(calls, [('OPTIONS', '/exact'), ('GET', '/exact')])
            self.assertEqual(report['requests_used'], 2)
            rules = {f['rule'] for f in report['findings']}
            self.assertIn('advertised-method-put', rules)
            self.assertIn('cookie-insecure-samesite-none', rules)
            self.assertNotIn('cookie-missing-secure', rules)  # HTTP scope
            for secret in ('private-value', 'another-secret', 'session=', 'secret-token'):
                self.assertNotIn(secret, json.dumps(report))
            proofs = {e['id'] for e in report['evidence']}
            self.assertTrue(all(f['evidence'] in proofs for f in report['findings']))
        finally:
            server.shutdown(); server.server_close(); worker.join(3)

    def test_cookie_https_and_malformed_evidence(self):
        counts = cookie_observations(['id=hidden', 'broken', 'id=hidden; Secure; HttpOnly; SameSite=Strict'], True)
        self.assertEqual(counts['missing_secure'], 1)
        self.assertEqual(counts['missing_httponly'], 1)
        self.assertEqual(counts['missing_samesite'], 1)
        self.assertEqual(counts['unparsed'], 1)

    def test_invalid_scope_is_rejected_before_network_access(self):
        for field, value in [('expires', float('nan')), ('timeout', float('inf')),
                             ('created', float('nan')), ('expires', 10**20)]:
            scope = s.create_scope(['http://127.0.0.1'])
            scope[field] = value
            with self.assertRaises(ValueError):
                s.assess(scope, s.identity(scope))
        for value in ('http://127.0.0.1/\r\nInjected:yes', 'http://127.0.0.1\\@example.com', 'http://127.0.0.1/has space'):
            with self.assertRaises(ValueError): s.target(value)
