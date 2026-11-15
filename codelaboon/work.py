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
    with path.open('r+b' if os.name=='nt' else 'rb') as lock:
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
    from codelaboon.work_queue import controls
    def task_status(task):
        control = controls(root, task['id'])
        return {'id': task['id'], 'project': task['project'],
                'stage': 'build' if task['id'] in state.get('plans', {}) or task.get('swarm', {}).get('controller') == 'worker' else 'plan',
                'swarm': task.get('swarm'), 'cycles_completed': state.get('cycles', {}).get(task['id'], 0),
                'next_run': state.get('next_run', {}).get(task['id'], 0),
                'paused': (control/'PAUSE').exists(), 'stopped': (control/'STOP').exists(),
                'permissions':task.get('permissions','default'),'profile':task.get('profile','coding'),
                'scope':task.get('scope',''),'elevation':task.get('elevation','none'),'supervision':task.get('supervision',{'enabled':False})}
    alive = running(root)
    info = root/'service-info.json'
    service_info = json.loads(info.read_text()) if info.exists() else {}
    return {'running': alive, 'service': service_info, 'stop_requested': (root / 'STOP').exists(),
            'paused': (root / 'PAUSE').exists(), 'config': str(path),
            'runtime': str(root), 'completed': len(done),
            'pending': [task_status(task) for task in tasks if task['id'] not in done],
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


def control(action, path=None, task_id=None):
    _, config, root = configuration(path)
    if task_id:
        tasks=list(config.get('tasks',[]))+[json.loads(p.read_text()) for p in (root/'inbox').glob('*.json')]
        if not any(task['id']==task_id for task in tasks):raise ValueError('Unknown task ID')
        from codelaboon.work_queue import controls
        directory=controls(root,task_id);directory.mkdir(parents=True,exist_ok=True)
        if action=='resume':
            if (directory/'STOP').exists():raise ValueError('Stopped tasks require a new queued task')
            (directory/'PAUSE').unlink(missing_ok=True)
            (directory/'RESET_SUPERVISION').touch()
        else:(directory/('STOP' if action=='stop' else 'PAUSE')).touch()
        print(action.capitalize()+': '+task_id)
        return
    root.mkdir(parents=True, exist_ok=True)
    if action in ('stop', 'pause'):
        (root / ('STOP' if action == 'stop' else 'PAUSE')).touch()
        print(action.capitalize() + ' requested; the active attempt finishes first.')
    elif action == 'resume':
        (root / 'PAUSE').unlink(missing_ok=True)
        print('Resumed scheduling. Use work start if the service is stopped.')


def add(project, instruction, checks, path=None, swarm=None, permissions='default', profile='coding', supervise=None, scope='', review_interval=15, allowed_paths=None, elevation='none'):
    path, config, root = configuration(path)
    if swarm is not None:
        from codelaboon.work_queue import validate_swarm
        validate_swarm(swarm)
        if swarm['controller'] == 'local' and not config.get('orchestrator'):
            raise ValueError('Local-controlled swarms require an orchestrator in work configuration')
    if permissions not in ('default','full') or profile not in ('coding','security'):raise ValueError('Invalid execution policy')
    if elevation not in ('none','root','administrator'):raise ValueError('Invalid elevation selection')
    if not isinstance(scope,str):raise ValueError('Scope must be text')
    if elevation!='none' and (permissions!='full' or not scope.strip()):raise ValueError('Elevated tasks require --permissions full and explicit --scope')
    if profile=='security' and not scope.strip():raise ValueError('Security tasks require an explicit --scope')
    if supervise is None:supervise=bool(config.get('orchestrator')) and (not swarm or swarm.get('controller')!='worker')
    if supervise and not config.get('orchestrator'):raise ValueError('Active supervision requires a local orchestrator configuration')
    from codelaboon.supervision import validate
    validate({'enabled':bool(supervise),'interval':review_interval,'allowed_paths':allowed_paths or []})
    if allowed_paths and not supervise:raise ValueError('Allowed-path enforcement requires supervision')
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('Project directory does not exist')
    if not instruction.strip() or not checks or not all(
            isinstance(check, list) and check and all(isinstance(p, str) for p in check)
            for check in checks):
        raise ValueError('An instruction and at least one acceptance command are required')
    if (supervise or permissions!='default' or profile!='coding') and running(root):
        info=root/'service-info.json';features=json.loads(info.read_text()).get('features',[]) if info.exists() else []
        required={'task-execution-policy'} | ({'active-supervision'} if supervise else set()) | ({'privilege-cases'} if elevation!='none' else set())
        if not required.issubset(features):raise ValueError('Restart the background worker after upgrading before queuing supervised/policy tasks; nothing was queued')
    task_id = 'instruction-' + uuid.uuid4().hex
    task = {'id': task_id, 'project': str(project), 'prompt': instruction,
            'verify_argv': checks}
    if elevation!='none':task['elevation']=elevation
    if permissions!='default':task['permissions']=permissions
    if profile!='coding':task['profile']=profile
    if scope.strip():task['scope']=scope.strip()
    if supervise:task['supervision']={'enabled':True,'interval':review_interval,'allowed_paths':allowed_paths or []}
    if swarm is not None:
        task['swarm'] = swarm
    inbox = root / 'inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    save(inbox / (task_id + '.json'), task)
    print('Queued ' + task_id + ('. Awaiting an explicit privilege worker-case and native OS approval.' if elevation!='none' else '. The running worker picks it up automatically.'))
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
        label = 'Awaiting elevation approval' if task.get('elevation','none')!='none' else 'Stopped' if task['stopped'] else 'Paused' if task['paused'] else 'Queued'
        print((label + ': {id} / {stage} / {project}').format_map(task))
        print('  permissions='+task.get('permissions','default')+' | profile='+task.get('profile','coding')+' | supervision='+('local' if task.get('supervision',{}).get('enabled') else 'off'))
        if task.get('swarm'):
            print('  Swarm: ' + task['swarm']['controller'] + ' | verified cycles: ' + str(task['cycles_completed']))
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
    parser.add_argument('--elevation',choices=['none','root','administrator'],default='none',help='Queue awaiting an explicitly approved native privileged case')
    parser.add_argument('--permissions',choices=['default','full'],default='default',help='Full disables agent approval gates; it does not grant root')
    parser.add_argument('--profile',choices=['coding','security'],default='coding')
    parser.add_argument('--scope',default='',help='Allowed objective/targets; required for security tasks')
    parser.add_argument('--supervise',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--review-interval',type=int,default=15)
    parser.add_argument('--allow-path',action='append',default=[],help='Relative file pattern; pause if observed edits leave this list')
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
        control(args.action, args.config,args.instruction)
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
        add(args.project, args.instruction, checks, args.config,permissions=args.permissions,profile=args.profile,supervise=args.supervise,scope=args.scope,review_interval=args.review_interval,allowed_paths=args.allow_path,elevation=args.elevation)


if __name__ == '__main__':
    main()
