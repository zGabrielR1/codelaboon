"""Control the persistent worker without keeping the terminal open."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import time
import uuid

from codelaboon.watch import save
from codelaboon.paths import config_dir

SOURCE = Path(__file__).resolve().parent.parent


def configuration(path=None):
    if path is None:
        installed = config_dir() / 'work.json'
        if not installed.exists():
            raise ValueError('Initialize the background worker with codelaboon work init')
        path = installed
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8'))
    return path, config, (path.parent / config.get('runtime', '.watch')).resolve()


def initialize(path=None):
    target = Path(path).resolve() if path else config_dir() / 'work.json'
    if target.exists():
        raise ValueError('Worker configuration already exists: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    worker = ['{python}', '{source}/codelaboon/cloud_worker.py', '--provider', 'free',
              '--model', 'free', '--runtime', '{runtime}', '{prompt_file}']
    builder = ['{python}', '{source}/codelaboon/cloud_worker.py', '--agent', '--model', 'free',
               '--runtime', '{runtime}', '{prompt_file}']
    save(target, {'runtime': 'work-runtime', 'poll_seconds': 15,
        'orchestrator': {'url': 'http://127.0.0.1:18765/v1/chat/completions', 'model': 'local-router'},
        'harnesses': [
            {'id': 'free-planner', 'location': 'cloud', 'stages': ['plan'], 'argv': worker},
            {'id': 'rust-builder', 'location': 'cloud', 'stages': ['build'], 'argv': builder}],
        'tasks': []})
    print('Created ' + str(target))
    return target


def running(root):
    path = root / 'service.lock'
    if not path.exists():
        return False
    with path.open('r+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock, fcntl.LOCK_UN)
        except OSError:
            return True
    return False


def status(path=None):
    path, config, root = configuration(path)
    state_path = root / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    tasks = list(config.get('tasks', []))
    for item in sorted((root / 'inbox').glob('*.json')):
        tasks.append(json.loads(item.read_text(encoding='utf-8')))
    done = set(state.get('done', []))
    active = []
    for item in root.glob('*/result.json'):
        result = json.loads(item.read_text(encoding='utf-8'))
        if result.get('status') == 'running':
            active.append({'task': result['task'], 'stage': result['stage'],
                           'harness': result['harness'], 'logs': str(item.parent)})
    alive = running(root)
    return {'running': alive, 'stop_requested': (root / 'STOP').exists(),
            'paused': (root / 'PAUSE').exists(), 'config': str(path),
            'runtime': str(root), 'completed': len(done),
            'pending': [{'id': task['id'], 'project': task['project'],
                         'stage': 'build' if task['id'] in state.get('plans', {}) else 'plan'}
                        for task in tasks if task['id'] not in done],
            'active_or_interrupted_attempts': active,
            'cooldowns': {key: round(until - time.time()) for key, until in
                          state.get('cooldowns', {}).items() if until > time.time()}}


def start(path=None):
    path, _, root = configuration(path)
    if running(root):
        print('Already running. Use work status or work resume.')
        return
    root.mkdir(parents=True, exist_ok=True)
    (root / 'STOP').unlink(missing_ok=True)
    from codelaboon.service import background
    background(path)


def control(action, path=None):
    _, _, root = configuration(path)
    root.mkdir(parents=True, exist_ok=True)
    if action in ('stop', 'pause'):
        (root / ('STOP' if action == 'stop' else 'PAUSE')).touch()
        print(action.capitalize() + ' requested; the active attempt finishes first.')
    elif action == 'resume':
        (root / 'PAUSE').unlink(missing_ok=True)
        print('Resumed scheduling. Use work start if the service is stopped.')


def add(project, instruction, checks, path=None):
    path, _, root = configuration(path)
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('Project directory does not exist')
    if not instruction.strip() or not checks or not all(
            isinstance(check, list) and check and all(isinstance(p, str) for p in check)
            for check in checks):
        raise ValueError('An instruction and at least one acceptance command are required')
    task_id = 'instruction-' + uuid.uuid4().hex
    task = {'id': task_id, 'project': str(project), 'prompt': instruction,
            'verify_argv': checks}
    inbox = root / 'inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    save(inbox / (task_id + '.json'), task)
    print('Queued ' + task_id + '. The running worker picks it up automatically.')
    return task_id


def inspect(path=None):
    result = status(path)
    state = 'stopped'
    if result['running']:
        state = 'stopping' if result['stop_requested'] else 'paused' if result['paused'] else 'running'
    print(f"Worker: {state} | completed: {result['completed']} | pending: {len(result['pending'])}")
    for attempt in result['active_or_interrupted_attempts']:
        print('Attempt: {task} / {stage} / {harness}\nLogs: {logs}'.format_map(attempt))
    for task in result['pending']:
        print('Queued: {id} / {stage} / {project}'.format_map(task))
    if result['cooldowns']:
        print('Cloud cooldowns (seconds): ' + json.dumps(result['cooldowns']))
    print('Runtime: ' + result['runtime'])


def menu(path=None):
    while True:
        inspect(path)
        print('\nstart | pause | resume | stop | add | status | logs | exit')
        try:
            action = input('work> ').strip().lower()
            if action in ('exit', 'quit', 'q'):
                return
            if action == 'start':
                start(path)
            elif action in ('pause', 'resume', 'stop'):
                control(action, path)
            elif action == 'add':
                project = input('Project directory: ').strip()
                instruction = input('Instruction: ').strip()
                check = input('Acceptance command (for example: python -m unittest discover -s tests): ')
                add(project, instruction, [shlex.split(check)], path)
            elif action == 'logs':
                logs(path)
        except (OSError, ValueError, EOFError) as error:
            print(str(error))
            if isinstance(error, EOFError):
                return


def logs(path=None):
    _, _, root = configuration(path)
    for name in ('supervisor.log', 'service.stderr.log'):
        target = root / name
        if target.exists():
            print(name + ':\n' + '\n'.join(target.read_text(encoding='utf-8', errors='replace').splitlines()[-30:]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='menu',
                        choices=['menu', 'init', 'enable', 'disable', 'start', 'stop', 'pause', 'resume', 'status', 'logs', 'add'])
    parser.add_argument('instruction', nargs='?')
    parser.add_argument('--config')
    parser.add_argument('--project')
    parser.add_argument('--check', action='append', default=[])
    parser.add_argument('--checks-json', help='Exact JSON array of argument arrays')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.action == 'init':
        initialize(args.config)
    elif args.action == 'enable':
        from codelaboon.autostart import enable
        path, _, root = configuration(args.config)
        (root / 'STOP').unlink(missing_ok=True)
        print('Autostart registered: ' + str(enable(path)))
    elif args.action == 'disable':
        from codelaboon.autostart import disable
        disable()
    elif args.action == 'menu':
        menu(args.config)
    elif args.action == 'start':
        start(args.config)
    elif args.action in ('stop', 'pause', 'resume'):
        control(args.action, args.config)
    elif args.action == 'status':
        if args.json:
            print(json.dumps(status(args.config), indent=2))
        else:
            inspect(args.config)
    elif args.action == 'logs':
        logs(args.config)
    elif args.action == 'add':
        if not args.project or not args.instruction:
            parser.error('add requires --project and an instruction')
        checks = json.loads(args.checks_json) if args.checks_json else [shlex.split(c) for c in args.check]
        if not checks:
            parser.error('provide --check or --checks-json')
        add(args.project, args.instruction, checks, args.config)


if __name__ == '__main__':
    main()
