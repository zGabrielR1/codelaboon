"""Explicit GitHub device OAuth, matching the pinned OpenCode upstream plugin."""
import json
import os
import time
import webbrowser
import requests
from codelaboon.paths import config_dir

CLIENT_ID='Ov23li8tweQw6odWQebz'


def credential():
    value=os.environ.get('COPILOT_GITHUB_TOKEN','').strip()
    if value:return value
    try:
        row=json.loads((config_dir()/'copilot-session.json').read_text(encoding='utf-8'))
        return row['access_token'] if isinstance(row,dict) and isinstance(row.get('access_token'),str) else ''
    except (OSError,ValueError):return ''


def login(notify=None,report=None):
    client_id=os.environ.get('CODELABOON_COPILOT_CLIENT_ID',CLIENT_ID)
    headers={'Accept':'application/json','User-Agent':'codelaboon'}
    response=requests.post('https://github.com/login/device/code',json={'client_id':client_id,'scope':'read:user'},headers=headers,timeout=15,allow_redirects=False)
    response.raise_for_status();row=response.json()
    code=row['user_code'];uri=row['verification_uri']
    if uri!='https://github.com/login/device':raise ValueError('Unexpected GitHub verification URI')
    status={'verification_uri':uri,'user_code':code}
    if notify:notify(status)
    else:
        message='GitHub Copilot OAuth (upstream OpenCode app). Open '+uri+' and enter '+code
        if report:report(message)
        else:print(message,flush=True)
        webbrowser.open(uri)
    interval=max(1,int(row.get('interval',5)))+3;deadline=time.monotonic()+min(900,int(row.get('expires_in',900)))
    while time.monotonic()<deadline:
        time.sleep(interval)
        response=requests.post('https://github.com/login/oauth/access_token',json={'client_id':client_id,'device_code':row['device_code'],'grant_type':'urn:ietf:params:oauth:grant-type:device_code'},headers=headers,timeout=15,allow_redirects=False)
        response.raise_for_status();answer=response.json()
        token=answer.get('access_token')
        if isinstance(token,str) and token:
            from codelaboon.freebuff_auth import save_record
            save_record('copilot-session.json',{'access_token':token});return
        error=answer.get('error')
        if error=='slow_down':interval+=5
        elif error!='authorization_pending':raise ValueError('GitHub authorization failed: '+str(error))
    raise ValueError('GitHub device authorization expired')
