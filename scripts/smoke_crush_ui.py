"""Check Crush's native free-model UI, prompt recall, model picker and themes."""
import json
import shlex
import subprocess
import sys
import time
import uuid
from native_fixture import ROOT, REPLY, fixture

artifacts = ROOT / '.runtime/ui-qa'
artifacts.mkdir(parents=True, exist_ok=True)
socket = 'codelaboon-crush-' + uuid.uuid4().hex


def tmux(*args):
    return subprocess.check_output(['tmux', '-L', socket, *args], text=True, env=env)


def wait(label, predicate):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = tmux('capture-pane', '-p', '-t', 'qa')
        (artifacts / ('crush-' + label + '.txt')).write_text(value)
        if 'Yep!' in value and 'Nope' in value:
            tmux('send-keys', '-t', 'qa', 'n')
            time.sleep(0.3)
        if predicate(value):
            return value
        time.sleep(0.2)
    raise AssertionError('Crush UI stage failed: ' + label)


with fixture('crush') as (project, env, observed):
    command = ['env', 'CODELABOON_MODEL_CHECKS=0', 'CODELABOON_CONFIG_DIR=' + env['CODELABOON_CONFIG_DIR'],
               'PATH=' + env['PATH'], sys.executable, str(ROOT / 'codelaboon/cli.py'), 'crush']
    try:
        tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'qa', '-x', '160', '-y', '44',
             '-c', str(project), shlex.join(command))
        tmux('set-option', '-t', 'qa', 'remain-on-exit', 'on')
        wait('home', lambda value: 'free (Auto)' in value and 'Codelaboon' in value)
        prompt = 'crush-native-history-check'
        tmux('send-keys', '-t', 'qa', '-l', prompt)
        time.sleep(0.3)
        tmux('send-keys', '-t', 'qa', 'Enter')
        wait('reply', lambda value: REPLY in value)
        tmux('send-keys', '-t', 'qa', 'Up')
        wait('history', lambda value: value.count(prompt) >= 2)
        tmux('send-keys', '-t', 'qa', 'C-u', 'C-l')
        wait('models', lambda value: 'free (Auto)' in value and ('kilo' in value.lower() or 'pollinations' in value.lower()))
        tmux('send-keys', '-t', 'qa', 'Escape')
        time.sleep(0.3)
        tmux('send-keys', '-t', 'qa', 'C-p')
        wait('commands', lambda value: 'Commands' in value)
        tmux('send-keys', '-t', 'qa', '-l', 'Themes')
        time.sleep(0.2)
        tmux('send-keys', '-t', 'qa', 'Enter')
        wait('themes', lambda value: 'Themes' in value and 'charmtone-panther' in value and 'gruvbox-dark' in value)
        tmux('send-keys', '-t', 'qa', '-l', 'gruvbox-dark')
        time.sleep(0.2)
        tmux('send-keys', '-t', 'qa', 'Enter')
        time.sleep(0.3)
        assert observed, 'No model request reached the fixture'
        profile = project / 'config/crush'
        assert any('gruvbox-dark' in path.read_text() for path in profile.rglob('*.json')), 'Theme choice was not persisted'
        assert list(profile.rglob('*.db')), 'No native project session database was persisted'
        result = {'engine': 'crush', 'home': True, 'response': True, 'prompt_recall': True,
                  'free_model_picker': True, 'themes': True, 'native_model_requests': len(observed)}
        (artifacts / 'crush-ui.json').write_text(json.dumps(result, indent=2) + '\n')
        print('PASS ' + json.dumps(result))
    finally:
        subprocess.run(['tmux', '-L', socket, 'kill-server'], capture_output=True)
