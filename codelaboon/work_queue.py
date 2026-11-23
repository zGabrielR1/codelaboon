"""Shared durable scheduling rules for the service, supervisor and status UI."""
import hashlib
import json
from pathlib import Path
import time


def controls(root, task_id):
    return Path(root) / 'task-controls' / hashlib.sha256(task_id.encode()).hexdigest()


def task_index(configured, root, *, project_root=None, on_invalid=None):
    """Choose one record per ID before testing whether its project is runnable."""
    tasks = {}
    for task in configured:
        tasks.setdefault(task['id'], task)
    claimed = set(tasks)
    for item in sorted((root / 'inbox').glob('*.json')):
        try:
            task = json.loads(item.read_text(encoding='utf-8'))
            validate_inbox_task(task)
            identity = task['id']
            if identity in claimed:
                continue
            claimed.add(identity)
            if project_root is not None and not (project_root / task['project']).resolve().is_dir():
                raise ValueError('Project directory unavailable')
        except (OSError, RuntimeError, ValueError) as error:
            if on_invalid is not None:
                on_invalid(item, error)
            continue
        tasks[identity] = task
    return tasks


def validate_inbox_task(task):
    if not isinstance(task, dict):
        raise ValueError('Expected a task object')
    for field in ('id', 'project', 'prompt'):
        value = task.get(field)
        if not isinstance(value, str) or (field != 'prompt' and not value):
            raise ValueError(f'Invalid task {field}')
        value.encode('utf-8')
    checks = task.get('verify_argv')
    if not isinstance(checks, list) or not checks or not all(
            isinstance(check, list) and check and all(isinstance(part, str) for part in check)
            for check in checks):
        raise ValueError('verify_argv must contain nonempty lists of string arguments')
    for field in ('execution_settings', 'supervision'):
        if field in task and not isinstance(task[field], dict):
            raise ValueError(f'Expected a task {field} object')
    if 'swarm' in task:
        validate_swarm(task['swarm'])


def ready(task, state, root, now=None):
    control = controls(root, task['id'])
    return (task.get('elevation','none')=='none' and task['id'] not in state.get('done', [])
            and not (control / 'PAUSE').exists() and not (control / 'STOP').exists() and not (control/'DELETED.json').exists()
            and state.get('next_run', {}).get(task['id'], 0) <= (time.time() if now is None else now))


def validate_swarm(options):
    if not isinstance(options, dict) or options.get('controller') not in ('local', 'worker'):
        raise ValueError('Swarm controller must be local or worker')
    for key, minimum, maximum in (('workers', 1, 1000), ('timeout', 1, 86400),
                                  ('interval', 1, 86400), ('cycles', 0, 1000000)):
        value = options.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f'Swarm {key} must be {minimum}–{maximum}')
    if not isinstance(options.get('model'), str) or not options['model'].strip():
        raise ValueError('A swarm model is required')
    from codelaboon.engine_tasks import ENGINES
    engine=options.get('engine','jcode')
    foreground = options.get('foreground_desktop', False)
    if not isinstance(foreground, bool):
        raise ValueError('Foreground desktop must be a boolean')
    if foreground and engine not in ('jcode', 'opencode', 'kilo', 'codex', 'claude', 'crush'):
        raise ValueError('Foreground desktop requires Jcode, OpenCode, Kilo, Codex, Claude or Crush')
    if engine not in ENGINES:raise ValueError('Unsupported task engine')
    if engine=='devin' and (not options['model'].startswith('devin/') or not options['model'].split('/',1)[1]):raise ValueError('Use devin/account-default or devin/MODEL for a native account task')
    if engine!='jcode' and options['workers']!=1:
        raise ValueError('Portable engine coordinators require --workers 1; Jcode supports the native worker pool')
    return options


def swarm_harness(task):
    options = validate_swarm(task['swarm'])
    return {'id': 'swarm-' + task['id'], 'location': 'local' if options.get('foreground_desktop') else 'cloud', 'stages': ['build'],
            'model': options['model'], 'capabilities': ['native-swarm'] if options.get('engine','jcode')=='jcode' else ['portable-coordinator'],
            'timeout_seconds': options['timeout'] + 15, 'cooldown_seconds': max(30, options['interval']),
            'argv': ['{python}', '{source}/codelaboon/swarm.py', '--task-file', '{prompt_file}',
                     '--workers', str(options['workers']), '--timeout', str(options['timeout']),
                     '--model', options['model'],'--engine',options.get('engine','jcode')]}
