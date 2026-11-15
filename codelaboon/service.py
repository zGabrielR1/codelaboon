"""Own and restart the local routing server and cloud-worker supervisor."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import signal
import time
import urllib.error
import urllib.request

from codelaboon.watch import terminate
from codelaboon.paths import config_dir


def router_ready():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open('http://127.0.0.1:18765/v1/models', timeout=2) as response:
            return any(row['id'] == 'local-router' for row in json.load(response)['data'])
    except (OSError, ValueError, KeyError):
        return False


def pending_work(config, runtime):
    """Keep the router model unloaded while the durable worker has no runnable tasks."""
    if (runtime / 'PAUSE').exists() or (runtime / 'STOP').exists():
        return False
    try:
        state = json.loads((runtime / 'state.json').read_text()) if (runtime / 'state.json').exists() else {}
        tasks = list(config.get('tasks', []))
        tasks.extend(json.loads(path.read_text()) for path in (runtime / 'inbox').glob('*.json'))
        from codelaboon.work_queue import ready
        return any(ready(task, state, runtime) and (task.get('swarm', {}).get('controller') != 'worker' or task.get('supervision',{}).get('enabled'))
                   for task in tasks)
    except (OSError, ValueError, KeyError, TypeError):
        return True  # Let the supervisor diagnose malformed state; do not silently drop work.


def serve(config_path):
    config_path = Path(config_path).resolve()
    source = Path(__file__).resolve().parent.parent
    config = json.loads(config_path.read_text(encoding='utf-8'))
    runtime = (config_path.parent / config['runtime']).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    local = config_dir() / 'runtime/local'
    local.mkdir(parents=True, exist_ok=True)
    name = 'llama-server.exe' if os.name == 'nt' else 'llama-server'
    linux = local / 'llama-linux/llama-b12360/llama-server'
    executable = Path(config.get('local_executable') or shutil.which(name) or
                      (linux if os.name != 'nt' and linux.is_file() else local / 'llama' / name))
    model = Path(config.get('local_model') or local / 'router.gguf')
    if pending_work(config, runtime) and not router_ready() and (not executable.is_file() or not model.is_file()):
        raise FileNotFoundError('Install a native llama-server and the optional local router model, '
                                'or start an external local-router server on port 18765. '
                                'Windows: python scripts/setup_orchestrator.py')
    lock = (runtime / 'service.lock').open('a+b')
    lock.write(b'0')
    lock.flush()
    lock.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    server = None
    worker = None
    awake = None
    try:
        if os.name == 'nt' and config.get('keep_awake', True):
            import ctypes
            awake = ctypes.windll.kernel32.SetThreadExecutionState
            awake(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; allow display sleep.
        (runtime / 'service.pid').write_text(str(os.getpid()))
        from codelaboon import __version__
        from codelaboon.watch import save
        save(runtime/'service-info.json', {'version': __version__, 'pid': os.getpid(),
                                           'features': ['continuous-swarm','task-execution-policy','active-supervision','privilege-cases']})
        with (local / 'service-server.log').open('ab') as server_log, \
                (runtime / 'supervisor.log').open('ab') as worker_log:
            while not (runtime / 'STOP').exists():
                if server is not None and server.poll() is not None:
                    server = None
                demand = pending_work(config, runtime)
                if server is not None and not demand:
                    terminate(server)
                    server = None
                if demand and server is None and not router_ready():
                    server = subprocess.Popen([
                        str(executable), '-m', str(model), '--host', '127.0.0.1',
                        '--port', '18765', '--alias', 'local-router', '-c', '4096',
                        '-t', '2', '--reasoning', 'off'],
                        stdout=server_log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                        start_new_session=os.name != 'nt')
                    (local / 'server.pid').write_text(str(server.pid))
                if worker is None or worker.poll() is not None:
                    worker = subprocess.Popen([
                        sys.executable, '-m', 'codelaboon.watch', str(config_path)], cwd=source,
                        stdout=worker_log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                        start_new_session=os.name != 'nt')
                    (runtime / 'supervisor.pid').write_text(str(worker.pid))
                time.sleep(5)
            # STOP is graceful: let the active cloud attempt and checks finish.
            while worker is not None and worker.poll() is None:
                time.sleep(1)
    finally:
        for child in (worker, server):
            if child is not None and child.poll() is None:
                terminate(child)
        if awake is not None:
            awake(0x80000000)
        lock.close()


def background(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    runtime = (config_path.parent / config['runtime']).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    if (runtime / 'STOP').exists():
        raise RuntimeError('Remove the runtime STOP file before starting')
    with (runtime / 'service.stdout.log').open('ab') as output, \
            (runtime / 'service.stderr.log').open('ab') as errors:
        process = subprocess.Popen([
            sys.executable, '-m', 'codelaboon.service', str(config_path)],
            cwd=Path(__file__).resolve().parent.parent,
            stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            if os.name == 'nt' else 0, start_new_session=os.name != 'nt')
    print('Started service PID ' + str(process.pid) + '; logs: ' + str(runtime))


def main():
    def stopped(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stopped)
    if os.name != 'nt':
        signal.signal(signal.SIGHUP, stopped)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--background', action='store_true')
    args = parser.parse_args()
    if args.background:
        background(args.config)
        return
    try:
        serve(args.config)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
