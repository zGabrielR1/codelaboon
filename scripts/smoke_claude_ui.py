"""Check Claude Code onboarding-free startup, free model picker and a native reply."""
import json
import shlex
import subprocess
import sys
import time
import uuid
from native_fixture import ROOT, REPLY, fixture

artifacts = ROOT / '.runtime/ui-qa'
artifacts.mkdir(parents=True, exist_ok=True)
socket = 'codelaboon-claude-' + uuid.uuid4().hex


def tmux(*args):
    return subprocess.check_output(['tmux', '-L', socket, *args], text=True)


def screen(label):
    value = tmux('capture-pane', '-p', '-t', 'qa')
    (artifacts / ('claude-' + label + '.txt')).write_text(value)
    return value


def wait(label, predicate):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = screen(label)
        if predicate(value):
            return value
        # Trust only the disposable fixture project; product permissions stay native.
        if 'Yes, I trust this folder' in value:
            tmux('send-keys', '-t', 'qa', 'Down', 'Enter')
            time.sleep(0.5)
        time.sleep(0.2)
    raise AssertionError('Claude UI stage failed: ' + label)


with fixture('claude') as (project, env, observed):
    command = ['env', 'CODELABOON_CONFIG_DIR=' + env['CODELABOON_CONFIG_DIR'],
               'PATH=' + env['PATH'], sys.executable, str(ROOT / 'codelaboon/cli.py'), 'claude']
    try:
        tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'qa', '-x', '160', '-y', '44',
             '-c', str(project), shlex.join(command))
        tmux('set-option', '-t', 'qa', 'remain-on-exit', 'on')
        home = wait('home', lambda value: 'free (Auto)' in value and 'Claude Code v' in value and '❯' in value and 'trust this folder' not in value)
        assert 'Select login method' not in home and 'Choose the text style' not in home
        tmux('send-keys', '-t', 'qa', '-l', 'claude-free-ui-check')
        time.sleep(0.3)
        tmux('send-keys', '-t', 'qa', 'Enter')
        wait('reply', lambda value: REPLY in value)
        tmux('send-keys', '-t', 'qa', '-l', '/model')
        time.sleep(0.3)
        tmux('send-keys', '-t', 'qa', 'Enter')
        wait('models', lambda value: 'free (Auto)' in value and ('kilo' in value.lower() or 'pollinations' in value.lower()))
        result = {'engine': 'claude', 'onboarding_skipped': True, 'subscription_required': False,
                  'response': True, 'free_model_picker': True, 'native_model_requests': len(observed)}
        (artifacts / 'claude-free-ui.json').write_text(json.dumps(result, indent=2) + '\n')
        print('PASS ' + json.dumps(result))
    finally:
        subprocess.run(['tmux', '-L', socket, 'kill-server'], capture_output=True)
