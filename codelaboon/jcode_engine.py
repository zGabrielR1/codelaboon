"""Lean Rust execution with a single Codelaboon gateway and native swarm workers."""
import json
import hashlib
from contextlib import contextmanager
import re
import time
import tomllib
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
    config = home / 'config.toml'
    retained = ''
    if config.exists():
        existing = config.read_text(encoding='utf-8')
        tomllib.loads(existing)  # Refuse to overwrite malformed native preferences.
        chunks = re.split(r'(?m)(?=^\s*\[)', existing)
        retained = ''.join(chunk for chunk in chunks if not (chunk.lstrip().startswith('[features]')
                   or chunk.lstrip().startswith('[providers.codelaboon]')
                   or chunk.lstrip().startswith('[[providers.codelaboon.models]]')))
    config.write_text(retained.rstrip() + '\n' + '\n'.join(lines) + '\n', encoding='utf-8')


@contextmanager
def profile_lock(home):
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (home/'launch.lock').open('a+b') as lock:
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('A Jcode UI already owns this project profile') from error
        yield


@contextmanager
def owned_processes(processes):
    try:
        yield
    finally:
        from codelaboon.watch import terminate
        for process in reversed(processes):
            if process.poll() is None:
                terminate(process)


def server_ready(address):
    if os.name != 'nt':
        import socket
        try:
            with socket.socket(socket.AF_UNIX) as probe:
                probe.settimeout(0.2)
                probe.connect(str(address))
                return True
        except OSError:
            return False
    import ctypes
    stem = ''.join(ch for ch in address.stem if ch.isascii() and (ch.isalnum() or ch in '-_'))[:32] or 'jcode'
    normalized = str(address).replace('\\', '/').translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    pipe = '\\\\.\\pipe\\' + stem + '-' + digest
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.WaitNamedPipeW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    return bool(kernel.WaitNamedPipeW(pipe, 0)) or ctypes.get_last_error() in (121, 231)


def run(binary, arguments, rows, url, token, workers=4, timeout=1800, home=None, interactive=False):
    if not 1 <= workers <= 1000 or (timeout is None and not interactive) or (timeout is not None and timeout <= 0):
        raise ValueError('Workers must be 1–1000 and headless timeout must be positive')
    home = Path(home or data_dir() / 'jcode/runs' / uuid.uuid4().hex)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    prepare(rows, url, home)
    env = dict(os.environ, JCODE_HOME=str(home), CODELABOON_GATEWAY_TOKEN=token,
               JCODE_NO_TELEMETRY='1', JCODE_CHECK_UPDATES='false', JCODE_MEMORY_ENABLED='false',
               JCODE_OPENROUTER_MAX_TOKENS='4096', JCODE_SWARM_MAX_CONCURRENT_AGENTS=str(workers))
    processes, previous = [], {}
    def stopped(signum, frame):
        raise SystemExit(128 + signum)
    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGHUP) if os.name != 'nt' else (signal.SIGTERM,):
            previous[signum] = signal.signal(signum, stopped)
    try:
        with tempfile.TemporaryDirectory(prefix='cb-jcode-', dir='/tmp' if os.name != 'nt' else None) as temporary, owned_processes(processes):
            address = Path(temporary)/'agent.sock'
            command = [binary, '--no-update', '--no-selfdev', '--quiet', '--provider-profile', 'codelaboon',
                       '--socket', str(address)]
            if not any(value in ('--model', '-m') or value.startswith('--model=') for value in arguments):
                command.extend(['--model', 'free'])
            if interactive:
                # Own the server before the UI connects; do not let the native UI create a detached daemon.
                model = 'free'
                for index, value in enumerate(arguments):
                    if value in ('--model', '-m'):
                        model = arguments[index+1]
                    elif value.startswith('--model='):
                        model = value.split('=', 1)[1]
                server_command = [*command, '--model', model, 'serve', '--temporary-server',
                                  '--owner-pid', str(os.getpid())]
                # command has a default model only when arguments do not specify one.
                if '--model' in command:
                    server_command = [*command, 'serve', '--temporary-server', '--owner-pid', str(os.getpid())]
                with (home/'server.log').open('ab') as output:
                    server = subprocess.Popen(server_command, env=env, stdin=subprocess.DEVNULL,
                                              stdout=output, stderr=output, start_new_session=os.name != 'nt')
                processes.append(server)
                deadline = time.monotonic()+20
                while not server_ready(address):
                    if server.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Jcode server did not become ready; see ' + str(home/'server.log'))
                    time.sleep(0.05)
            process = subprocess.Popen([*command, *arguments], env=env, start_new_session=os.name != 'nt')
            processes.append(process)
            try:
                return process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                raise RuntimeError('Lightweight agent exceeded its configured time budget') from error
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
    if 'run' not in arguments:
        key = hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:20]
        home = data_dir()/'jcode/projects'/key
        with profile_lock(home):
            return run(binary, arguments, rows, url, token, timeout=None, home=home, interactive=True)
    return run(binary, arguments, rows, url, token)
