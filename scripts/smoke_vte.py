"""Verify installed native UIs in VTE, used by Fedora Ptyxis/GNOME Terminal.

Requires GTK 3, VTE 2.91 and Python GI. Run under xvfb-run in headless CI.
"""
import argparse
import json
import sys
import os
from pathlib import Path
import shutil
import signal
import time

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
from gi.repository import GLib, Gtk, Vte

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from native_fixture import ROOT, REPLY, fixture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine', choices=['opencode', 'crush'], default='opencode')
engine = parser.parse_args().engine

artifacts = ROOT / '.runtime/ui-qa'
artifacts.mkdir(parents=True, exist_ok=True)
prompt = 'vte-native-history-check'

with fixture(engine) as (project, env, observed):
    window = Gtk.Window(title='Codelaboon VTE integration check')
    window.set_default_size(1100, 700)
    terminal = Vte.Terminal()
    window.add(terminal)
    window.show_all()
    children = []
    failure = []
    state = 'home'
    sent = 0.0
    deadline = time.monotonic() + 90

    def spawned(term, pid, error, data):
        if error:
            failure.append(str(error))
        if pid > 0:
            children.append(pid)

    def screen():
        if hasattr(terminal, 'get_text_format'):
            return terminal.get_text_format(Vte.Format.TEXT) or ''
        return terminal.get_text(None, None)[0] or ''

    def poll():
        global state, sent
        value = screen()
        (artifacts / (engine + '-vte-' + state + '.txt')).write_text(value, encoding='utf-8')
        if failure or time.monotonic() > deadline:
            failure.append('VTE did not complete stage: ' + state)
            Gtk.main_quit()
            return False
        if engine == 'crush' and 'Yep!' in value and 'Nope' in value:
            terminal.feed_child(b'n')
        home = ('Ask anything' in value and 'c o d e l a b o o n' in value) if engine == 'opencode' else ('free (Auto)' in value and 'Codelaboon' in value)
        if state == 'home' and home:
            terminal.feed_child(prompt.encode())
            state, sent = 'typed', time.monotonic()
        elif state == 'typed' and time.monotonic() - sent > 0.3:
            terminal.feed_child(b'\r')
            state = 'reply'
        elif state == 'reply' and REPLY in value and observed:
            terminal.feed_child(b'\x1b[A')
            state = 'history'
        elif state == 'history' and value.count(prompt) >= 2:
            state = 'complete'
            Gtk.main_quit()
            return False
        return True

    command = ([shutil.which('codelaboon'), 'tui', '--', '--model', 'codelaboon/local/fixture']
               if engine == 'opencode' else [shutil.which('codelaboon'), 'crush'])
    terminal.spawn_async(pty_flags=Vte.PtyFlags.DEFAULT, working_directory=str(project), argv=command,
                         envv=[key + '=' + value for key, value in env.items()],
                         spawn_flags=GLib.SpawnFlags.DEFAULT, timeout=15000,
                         callback=spawned, user_data=None)
    GLib.timeout_add(100, poll)
    try:
        Gtk.main()
    finally:
        for pid in children:
            try:
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        window.destroy()
    assert state == 'complete' and not failure, '; '.join(failure) or state
    result = {'terminal': 'VTE', 'engine': engine, 'home': True, 'response': True, 'prompt_recall': True,
              'native_model_requests': len(observed)}
    (artifacts / (engine + '-vte.json')).write_text(json.dumps(result, indent=2) + '\n')
    print('PASS ' + json.dumps(result))
