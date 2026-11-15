"""Verify the optional native Jcode UI, gateway, durable profile and server ownership."""
import hashlib
from pathlib import Path
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from native_fixture import ROOT, REPLY, fixture

artifacts = ROOT/'.runtime/ui-qa'
artifacts.mkdir(parents=True, exist_ok=True)
socket = 'codelaboon-jcode-' + uuid.uuid4().hex


def tmux(*args):
    return subprocess.check_output(['tmux', '-L', socket, *args], text=True, env=env)


def wait(label, predicate):
    deadline = time.monotonic()+45
    welcomed = False
    while time.monotonic() < deadline:
        value = tmux('capture-pane', '-p', '-t', 'qa')
        (artifacts/('jcode-'+label+'.txt')).write_text(value)
        if label == 'home' and not welcomed and 'How would you like to begin?' in value:
            # Fresh native profiles show a welcome chooser before the model UI.
            # Select the new session in this isolated fixture project.
            tmux('send-keys', '-t', 'qa', 'Right', 'Enter')
            welcomed = True
        if predicate(value):
            return value
        time.sleep(0.2)
    raise AssertionError('Jcode UI stage failed: '+label)


with fixture('jcode') as (project, env, observed):
    profile=os.environ.get('CODELABOON_UI_PROFILE','coding')
    assert profile in ('coding','security')
    env['CODELABOON_WORK_PROFILE']=profile
    assignments = [key+'='+env[key] for key in ('CODELABOON_CONFIG_DIR', 'CODELABOON_DATA_DIR', 'CODELABOON_MODEL_CHECKS',
                   'CODELABOON_JCODE_BIN', 'PATH','CODELABOON_WORK_PROFILE') if key in env]
    command = ['env', *assignments, sys.executable, str(ROOT/'codelaboon/cli.py'), 'jcode']
    try:
        tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'qa', '-x', '160', '-y', '44',
             '-c', str(project), shlex.join(command))
        tmux('set-option', '-t', 'qa', 'remain-on-exit', 'on')
        wait('home', lambda value: 'free' in value.lower() and ('jcode' in value.lower() or 'codelaboon' in value.lower()))
        prompt = 'jcode-native-history-check'
        tmux('send-keys', '-t', 'qa', '-l', prompt)
        tmux('send-keys', '-t', 'qa', 'Enter')
        wait('reply', lambda value: REPLY in value)
        assert observed, 'No native UI request reached the gateway'
        if profile=='security':assert 'authorized pentesting assistant' in json.dumps(observed[0]['messages']),'Native additive security overlay absent'
        key = hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:20]
        profile = project/'data/jcode/projects'/key
        assert list((profile/'sessions').glob('*.json')), 'No persistent native session'
        sessions = list((profile/'sessions').glob('*.json'))
        registry = json.loads((profile/'servers.json').read_text())
        server_pids = [info['pid'] for info in registry.values()]
        assert server_pids, 'No owned native server registered'
        tmux('kill-session', '-t', 'qa')
        deadline = time.monotonic()+10
        def live(pid):
            stat = Path('/proc')/str(pid)/'stat'
            return stat.exists() and stat.read_text().split(') ',1)[1][0] != 'Z'
        while any(live(pid) for pid in server_pids) and time.monotonic()<deadline:
            time.sleep(0.1)
        assert not any(live(pid) for pid in server_pids), 'Owned Jcode server leaked after UI exit'
        time.sleep(0.2)
        # A new UI/server must load the previous native session from the same project profile.
        resumed = [*command, '--resume', sessions[0].stem]
        tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'qa', '-x', '160', '-y', '44',
             '-c', str(project), shlex.join(resumed))
        tmux('set-option', '-t', 'qa', 'remain-on-exit', 'on')
        wait('resumed', lambda value: REPLY in value and prompt in value)
        result = {'engine':'jcode','native_ui':True,'free_gateway':True,'saved_session_resume':True,
                  'owned_server_cleanup':True,'native_model_requests':len(observed)}
        (artifacts/'jcode-ui.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS '+json.dumps(result))
    finally:
        subprocess.run(['tmux', '-L', socket, 'kill-server'], capture_output=True)
