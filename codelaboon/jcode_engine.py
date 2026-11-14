"""Lean Rust execution with a single Codelaboon gateway and native swarm workers."""
import json
import os
from pathlib import Path
import subprocess
import signal
import threading
import tempfile
import uuid

from codelaboon.paths import data_dir


def prepare(rows, url, home):
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    lines = ['[features]', 'check_updates = false', 'memory = false', 'swarm = true',
             '[providers.codelaboon]', 'type = "openai-compatible"', 'auth = "bearer"',
             'base_url = ' + quote(url), 'api_key_env = "CODELABOON_GATEWAY_TOKEN"',
             'requires_api_key = true', 'default_model = "free"', 'model_catalog = true',
             'supports_reasoning_effort = false', 'disable_reasoning_heuristics = true']
    for row in rows:
        if row['api'] == 'chat':
            lines.extend(['[[providers.codelaboon.models]]', 'id = ' + quote(row['id']),
                          'context_window = ' + ('8192' if row['id'].startswith('local/') else '32768'),
                          'reasoning = false', 'input = ["text"]'])
    (home / 'config.toml').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(binary, arguments, rows, url, token, workers=4, timeout=1800, home=None):
    if not 1 <= workers <= 1000 or timeout <= 0:
        raise ValueError('Workers must be 1–1000 and timeout must be positive')
    home = Path(home or data_dir() / 'jcode/runs' / uuid.uuid4().hex)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    prepare(rows, url, home)
    env = dict(os.environ, JCODE_HOME=str(home), CODELABOON_GATEWAY_TOKEN=token,
               JCODE_NO_TELEMETRY='1', JCODE_CHECK_UPDATES='false', JCODE_MEMORY_ENABLED='false',
               JCODE_OPENROUTER_MAX_TOKENS='4096', JCODE_SWARM_MAX_CONCURRENT_AGENTS=str(workers))
    with tempfile.TemporaryDirectory(prefix='cb-jcode-', dir='/tmp' if os.name != 'nt' else None) as temporary:
        command = [binary, '--no-update', '--no-selfdev', '--quiet', '--provider-profile', 'codelaboon',
                   '--socket', str(Path(temporary) / 'agent.sock')]
        if not any(value in ('--model', '-m') or value.startswith('--model=') for value in arguments):
            command.extend(['--model', 'free'])
        command.extend(arguments)
        process = subprocess.Popen(command, env=env, start_new_session=os.name != 'nt')
        previous = {}
        def stopped(signum, frame):
            raise SystemExit(128 + signum)
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGHUP) if os.name != 'nt' else (signal.SIGTERM,):
                previous[signum] = signal.signal(signum, stopped)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            from codelaboon.watch import terminate
            terminate(process)
            raise RuntimeError('Lightweight agent exceeded its configured time budget')
        except BaseException:
            from codelaboon.watch import terminate
            terminate(process)
            raise
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


def launch(binary, arguments, profile, local_only, rows, url, token):
    if local_only:
        # Preserve the local-only gateway route while using the same native harness.
        default = rows[0]['id']
        arguments = ['--model', default, *arguments]
    if profile == 'security':
        prompt = (Path(__file__).parent / 'prompts/security.md').read_text()
        if arguments[:1] in (['run'], ('run',)):
            arguments = [*arguments[:-1], prompt + '\n\n' + arguments[-1]]
    return run(binary, arguments, rows, url, token)
