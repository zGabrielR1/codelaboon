"""ChatGPT plan sign-in using OpenAI's public OSS registration flow.

This implements the documented "Sign in with ChatGPT" flow for open-source
apps: ``client_id=dynamic_agent_client`` on first registration, an
authorization-code + PKCE grant over a ``127.0.0.1`` loopback callback, the
issued ``oaiapp_...`` client id persisted immediately (so a retry reauthorizes
the same registration instead of registering a second client), ID-token
validation against OpenAI's JWKS, and rotating refresh tokens.

Failures raise ``ValueError`` with the provider's own error code/message; the
TUI shows that text instead of a generic "sign-in did not complete".
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import requests

ISSUER = 'https://auth.openai.com'
AUTHORIZE_URL = ISSUER + '/api/accounts/authorize'
TOKEN_URL = ISSUER + '/api/accounts/oauth/token'
JWKS_URL = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'

PLAN_SCOPE = 'chatgpt.tokens.use.direct'
REQUESTED_SCOPE = 'openid profile email offline_access resource.invoke ' + PLAN_SCOPE
DYNAMIC_CLIENT_ID = 'dynamic_agent_client'
AGENT_NAME = 'codelaboon'
CALLBACK_PATH = '/auth/callback'

SESSION_FILE = 'chatgpt-session.json'
REGISTRATION_FILE = 'chatgpt-registration.json'
HOST_FILE = 'chatgpt-host.json'

# OpenAI's auth hosts accept these for the public OSS flow; the originator
# header is what the reference clients send alongside their client id.
REQUEST_HEADERS = {
    'accept': 'application/json',
    'user-agent': 'codelaboon/1.0',
    'originator': 'codelaboon',
}

TERMINAL_REFRESH_ERRORS = {
    'invalid_grant',
    'invalid_refresh_token',
    'token_expired',
    'refresh_token_expired',
    'refresh_token_invalidated',
    'refresh_token_reused',
    'invalid_client',
}

_lock = threading.RLock()


def directory():
    from codelaboon.paths import config_dir

    return config_dir()


def read_record(name):
    """Read a private JSON record, tolerating missing or malformed files."""
    try:
        value = json.loads((directory() / name).read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def read_session():
    return read_record(SESSION_FILE)


def save_record(name, data):
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    # Create a private file before writing credentials; replace atomically.
    temporary = root / (name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _error_detail(response):
    """The OAuth error code and description from a failed token response."""
    try:
        body = response.json()
    except ValueError:
        text = (response.text or '').strip()
        return text[:400] if text else 'no response body'
    if isinstance(body, dict):
        error = body.get('error')
        if isinstance(error, dict):
            error = error.get('code') or error.get('message')
        description = body.get('error_description') or body.get('message') or ''
        if error:
            return f"{error}: {description}".rstrip(': ')
        return description or 'no error code'
    return str(body)[:400]


def _scopes_from(value):
    if isinstance(value, str):
        return value.split()
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return []


def _unverified_claims(token):
    """Decode a JWT payload without verifying it (scope/expiry bookkeeping)."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims if isinstance(claims, dict) else {}
    except (IndexError, ValueError, TypeError):
        return {}


def access_token():
    """A fresh ChatGPT plan access token, refreshing it before expiry."""
    with _lock:
        session = read_session()
        if not session:
            return ''
        if float(session.get('expires_at') or 0) > time.time() + 60:
            return str(session.get('access_token') or '')
        refresh_token = str(session.get('refresh_token') or '')
        client_id = str(session.get('client_id') or '')
        if not refresh_token or not client_id:
            raise ValueError('ChatGPT session expired. Run `codelaboon login chatgpt` again.')
        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    'grant_type': 'refresh_token',
                    'client_id': client_id,
                    'refresh_token': refresh_token,
                    'resource': RESOURCE,
                },
                headers=REQUEST_HEADERS,
                timeout=30,
            )
        except requests.RequestException as error:
            raise ValueError(f'Could not reach OpenAI to refresh the ChatGPT session: {error}') from error
        if response.status_code != 200:
            code = _error_detail(response).split(':', 1)[0].strip()
            if code in TERMINAL_REFRESH_ERRORS:
                raise ValueError(
                    f'ChatGPT session is no longer usable ({code}). Run `codelaboon login chatgpt` again.'
                )
            raise ValueError(f'ChatGPT session refresh failed (HTTP {response.status_code}). Try again later.')
        data = response.json()
        scopes = _scopes_from(data.get('scope')) or _scopes_from(session.get('scopes'))
        if scopes and PLAN_SCOPE not in scopes:
            raise ValueError(
                'ChatGPT plan usage is no longer granted. Run `codelaboon login chatgpt` and allow plan usage.'
            )
        session.update(
            access_token=data['access_token'],
            refresh_token=data.get('refresh_token') or refresh_token,
            expires_at=time.time() + int(data.get('expires_in') or 3600),
            id_token=data.get('id_token') or session.get('id_token'),
            scopes=scopes,
        )
        save_record(SESSION_FILE, session)
        return str(session['access_token'])


def validate_identity(token, client_id, nonce):
    """Verify the ID token's signature, issuer, audience, expiry and nonce."""
    key = jwt.PyJWKClient(JWKS_URL, timeout=15).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        key.key,
        algorithms=['RS256'],
        audience=client_id,
        issuer=ISSUER,
        options={'require': ['exp', 'iss', 'aud', 'sub']},
        leeway=60,
    )
    if not secrets.compare_digest(str(claims.get('nonce') or ''), nonce):
        raise ValueError('ChatGPT returned an invalid sign-in nonce. Start sign-in again.')
    if not isinstance(claims.get('sub'), str) or not claims['sub']:
        raise ValueError('ChatGPT returned an invalid sign-in identity.')
    return claims


def _host_record():
    host = read_record(HOST_FILE)
    if not isinstance(host.get('id'), str) or not host['id']:
        host = {'id': 'urn:uuid:' + str(uuid.uuid4())}
        save_record(HOST_FILE, host)
    return host


def _registration_client_id():
    registration = read_record(REGISTRATION_FILE)
    value = registration.get('client_id')
    return value if isinstance(value, str) and value and value != DYNAMIC_CLIENT_ID else ''


def _authorize_url(client_id, host_id, redirect_uri, state, nonce, challenge, session):
    params = {
        'client_id': client_id,
        'ext_agent_host_id': host_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': REQUESTED_SCOPE,
        'resource': RESOURCE,
        'state': state,
        'nonce': nonce,
        'code_challenge_method': 'S256',
        'code_challenge': challenge,
    }
    if client_id == DYNAMIC_CLIENT_ID:
        params['agent_name_hint'] = AGENT_NAME
    if session.get('id_token'):
        params['id_token_hint'] = session['id_token']
    if session.get('email'):
        params['login_hint'] = session['email']
    scopes = _scopes_from(session.get('scopes'))
    if scopes and PLAN_SCOPE not in scopes:
        # The account declined plan usage on an earlier attempt: ask again.
        params['prompt'] = 'consent'
    return AUTHORIZE_URL + '?' + urlencode(params)


def login(report=None):
    report = report or (lambda message: print(message, flush=True))
    with _lock:
        old = read_session()
        host = _host_record()

    pending_client_id = _registration_client_id() or str(old.get('client_id') or '') or DYNAMIC_CLIENT_ID
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = (
                parsed.path == CALLBACK_PATH
                and secrets.compare_digest(params.get('state', [''])[0], state)
            )
            if valid and not result:
                result.update(params)
            text = b'You may return to codelaboon.' if valid else b'Invalid sign-in callback.'
            self.send_response(200 if valid else 400)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(text)

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}{CALLBACK_PATH}'
        url = _authorize_url(pending_client_id, host['id'], redirect, state, nonce, challenge, old)
        report('Complete ChatGPT authorization in your browser. Waiting up to 5 minutes.')
        if not webbrowser.open(url):
            report(url)
        deadline = time.monotonic() + 300
        while not result and time.monotonic() < deadline:
            server.handle_request()

    if not result:
        raise ValueError('ChatGPT sign-in was cancelled or timed out.')
    if result.get('error'):
        error = result['error'][0]
        description = (result.get('error_description') or [''])[0]
        raise ValueError(f'ChatGPT sign-in failed: {error}{(" — " + description) if description else ""}')

    returned_client_id = (result.get('client_id') or [''])[0]
    if pending_client_id == DYNAMIC_CLIENT_ID:
        client_id = returned_client_id
        if not client_id or client_id == DYNAMIC_CLIENT_ID:
            raise ValueError('ChatGPT registration was incomplete: the callback carried no issued client id.')
    else:
        client_id = pending_client_id
        if returned_client_id and returned_client_id != client_id:
            raise ValueError(
                'ChatGPT returned a different client registration. '
                'Sign in again with the saved ChatGPT account, or remove the stored registration to add another.'
            )

    # Persist the issued registration before the token exchange. Without this,
    # any later failure (network, expired code) loses the client id and the
    # retry registers a second agent.
    save_record(REGISTRATION_FILE, {
        'client_id': client_id,
        'ext_agent_host_id': host['id'],
        'subject': old.get('subject'),
        'email': old.get('email'),
    })

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'client_id': client_id,
                'code': (result.get('code') or [''])[0],
                'code_verifier': verifier,
                'redirect_uri': redirect,
                'resource': RESOURCE,
            },
            headers=REQUEST_HEADERS,
            timeout=30,
        )
    except requests.RequestException as error:
        raise ValueError(f'Could not reach OpenAI to finish sign-in: {error}') from error
    if response.status_code != 200:
        raise ValueError(
            f'ChatGPT code exchange failed (HTTP {response.status_code}: {_error_detail(response)}). '
            'Start sign-in again.'
        )

    data = response.json()
    if not isinstance(data.get('id_token'), str):
        raise ValueError('ChatGPT token response carried no ID token. Start sign-in again.')
    claims = validate_identity(data['id_token'], client_id, nonce)
    if old.get('subject') and claims['sub'] != old['subject']:
        raise ValueError(
            'A different ChatGPT account was returned. Existing credentials are preserved; '
            'sign in with the original account.'
        )

    callback_scopes = _scopes_from((result.get('scope') or [''])[0])
    scopes = _scopes_from(data.get('scope')) or callback_scopes or _scopes_from(_unverified_claims(
        str(data.get('access_token') or '')
    ).get('scope'))

    record = {
        'client_id': client_id,
        'ext_agent_host_id': host['id'],
        'subject': claims['sub'],
        'email': claims.get('email'),
        'id_token': data['id_token'],
        'access_token': data.get('access_token', ''),
        'refresh_token': data.get('refresh_token', ''),
        'expires_at': time.time() + int(data.get('expires_in') or 3600),
        'scopes': scopes,
        'token_type': data.get('token_type') or 'Bearer',
    }
    save_record(SESSION_FILE, record)
    save_record(REGISTRATION_FILE, {
        'client_id': client_id,
        'ext_agent_host_id': host['id'],
        'subject': claims['sub'],
        'email': claims.get('email'),
    })

    if PLAN_SCOPE not in scopes:
        raise ValueError(
            'ChatGPT sign-in completed, but ChatGPT plan usage was not granted. '
            'Run `codelaboon login chatgpt` again and allow plan usage.'
        )
    if not record['refresh_token']:
        raise ValueError(
            'ChatGPT sign-in completed, but offline access was not granted, so the session cannot be kept. '
            'Run `codelaboon login chatgpt` again and keep the browser consent tab open.'
        )
    report('ChatGPT connected. Refresh models to load your account catalogue.')
