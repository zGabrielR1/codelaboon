"""Shared durable scheduling rules for the service, supervisor and status UI."""
import hashlib
from pathlib import Path
import time


def controls(root, task_id):
    return Path(root) / 'task-controls' / hashlib.sha256(task_id.encode()).hexdigest()


def ready(task, state, root, now=None):
    control = controls(root, task['id'])
    return (task.get('elevation','none')=='none' and task['id'] not in state.get('done', [])
            and not (control / 'PAUSE').exists() and not (control / 'STOP').exists()
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
    if engine not in ENGINES:raise ValueError('Unsupported task engine')
    if engine!='jcode' and options['workers']!=1:
        raise ValueError('Portable engine coordinators require --workers 1; Jcode supports the native worker pool')
    return options


def swarm_harness(task):
    options = validate_swarm(task['swarm'])
    return {'id': 'swarm-' + task['id'], 'location': 'cloud', 'stages': ['build'],
            'model': options['model'], 'capabilities': ['native-swarm'] if options.get('engine','jcode')=='jcode' else ['portable-coordinator'],
            'timeout_seconds': options['timeout'] + 15, 'cooldown_seconds': max(30, options['interval']),
            'argv': ['{python}', '{source}/codelaboon/swarm.py', '--task-file', '{prompt_file}',
                     '--workers', str(options['workers']), '--timeout', str(options['timeout']),
                     '--model', options['model'],'--engine',options.get('engine','jcode')]}
