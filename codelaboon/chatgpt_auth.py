"""ChatGPT plan sign-in using OpenAI's public OSS registration flow."""
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
RESOURCE = 'https://api.openai.com/v1'
TOKEN_URL = ISSUER + '/api/accounts/oauth/token'
_lock = threading.RLock()


def directory():
    return Path(os.environ.get('CODELABOON_CONFIG_DIR', str(Path.home()/'.config'/'codelaboon')))


def read_session():
    try:
        return json.loads((directory()/'chatgpt-session.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def save_record(name, data):
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root/name
    # Create a private file before writing credentials; replace atomically.
    temporary = root/(name + '.' + secrets.token_hex(8) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def access_token():
    with _lock:
        session = read_session()
        if not session:
            return ''
        if session['expires_at'] < time.time()+60:
            response = requests.post(TOKEN_URL, data={'grant_type':'refresh_token','client_id':session['client_id'],'refresh_token':session['refresh_token'],'resource':RESOURCE}, timeout=30)
            if response.status_code != 200:
                raise ValueError('ChatGPT session expired. Run codelaboon login chatgpt again.')
            data = response.json()
            if 'scope' in data and 'chatgpt.tokens.use.direct' not in data['scope'].split():
                raise ValueError('ChatGPT plan permission is missing. Sign in again.')
            session.update(access_token=data['access_token'], refresh_token=data.get('refresh_token',session['refresh_token']),expires_at=time.time()+int(data['expires_in']))
            save_record('chatgpt-session.json',session)
        return session['access_token']


def validate_identity(token, client_id, nonce):
    key = jwt.PyJWKClient(ISSUER+'/.well-known/jwks.json', timeout=15).get_signing_key_from_jwt(token)
    claims = jwt.decode(token,key.key,algorithms=['RS256'],audience=client_id,issuer=ISSUER,options={'require':['sub','exp','iat','nonce']},leeway=5)
    if claims['nonce'] != nonce or not isinstance(claims['sub'],str) or not claims['sub']:
        raise ValueError('Invalid ChatGPT sign-in identity')
    return claims


def login(report=None):
    report = report or (lambda message: print(message, flush=True))
    with _lock:
        old = read_session()
        host_path = directory()/'chatgpt-host.json'
        host = json.loads(host_path.read_text()) if host_path.exists() else {'id':'urn:uuid:'+str(uuid.uuid4())}
        if not host_path.exists():
            save_record('chatgpt-host.json',host)
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def do_GET(self):
            params = parse_qs(urlsplit(self.path).query)
            valid = urlsplit(self.path).path == '/auth/callback' and secrets.compare_digest(params.get('state',[''])[0],state)
            if valid and not result:
                result.update(params)
            text = b'You may return to codelaboon.' if valid else b'Invalid sign-in callback.'
            self.send_response(200 if valid else 400)
            self.send_header('Content-Type','text/plain')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(text)

    with HTTPServer(('127.0.0.1',0),Callback) as server:
        server.timeout = 1
        redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
        params = dict(client_id=old.get('client_id','dynamic_agent_client'),ext_agent_host_id=host['id'],response_type='code',redirect_uri=redirect,scope='openid profile email offline_access resource.invoke chatgpt.tokens.use.direct',resource=RESOURCE,state=state,nonce=nonce,code_challenge_method='S256',code_challenge=challenge)
        if old:
            params['id_token_hint']=old['id_token']
        else:
            params['agent_name_hint']='codelaboon'
        url = ISSUER+'/api/accounts/authorize?'+urlencode(params)
        report('Complete ChatGPT authorization in your browser. Waiting up to 5 minutes.')
        if not webbrowser.open(url):
            report(url)
        deadline = time.monotonic()+300
        while not result and time.monotonic()<deadline:
            server.handle_request()
    if not result or 'error' in result:
        raise ValueError('ChatGPT sign-in was cancelled or timed out.')
    client_id = result.get('client_id',[old.get('client_id','')])[0]
    if not client_id or client_id == 'dynamic_agent_client' or (old and client_id != old['client_id']):
        raise ValueError('ChatGPT registration returned an invalid client ID.')
    response = requests.post(TOKEN_URL,data={'grant_type':'authorization_code','client_id':client_id,'code':result.get('code',[''])[0],'code_verifier':verifier,'redirect_uri':redirect,'resource':RESOURCE},timeout=30)
    if response.status_code != 200:
        raise ValueError('ChatGPT code exchange failed. Start sign-in again.')
    data = response.json()
    claims = validate_identity(data['id_token'],client_id,nonce)
    if old and claims['sub'] != old['subject']:
        raise ValueError('A different ChatGPT account was returned. Existing session preserved.')
    if 'chatgpt.tokens.use.direct' not in data.get('scope','').split():
        raise ValueError('ChatGPT plan usage was not authorized.')
    record = dict(client_id=client_id,subject=claims['sub'],id_token=data['id_token'],access_token=data['access_token'],refresh_token=data['refresh_token'],expires_at=time.time()+int(data['expires_in']))
    with _lock:
        save_record('chatgpt-session.json',record)
    report('ChatGPT connected. Refresh models to load your account catalogue.')
