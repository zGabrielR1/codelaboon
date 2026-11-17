"""Read-only task monitoring and log following across recurring attempts."""
import json
from pathlib import Path
import sys
import time


def read(path, default):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def snapshot(config=None, task_id=None, swarm_only=False):
    from codelaboon.work import status
    state = status(config)
    root = Path(state['runtime'])
    tasks = [row for row in state['pending'] if (not task_id or row['id']==task_id) and (not swarm_only or row.get('swarm'))]
    selected_ids={row['id'] for row in tasks}
    attempts = {}
    for path in root.glob('*/result.json'):
        row = read(path, {})
        identity = row.get('task')
        if not identity or (task_id and identity != task_id) or (swarm_only and not task_id and identity not in selected_ids):
            continue
        if not isinstance(row.get('started',0),(int,float)):continue
        if row.get('started',0) >= attempts.get(identity,{}).get('started',0):
            attempts[identity] = {key:row[key] for key in ('status','stage','exit_code','started','finished','harness','verification','failure_detail','needs_attention','recovery','phase') if key in row}
            attempts[identity]['logs'] = str(path.parent)
    for row in tasks:
        latest = attempts.get(row['id'])
        row['last_attempt'] = latest
        row['cooldown_seconds'] = state['cooldowns'].get('swarm-'+row['id'], 0)
        if row['stopped']: label='stopped'
        elif row['paused'] or state['paused']: label='paused'
        elif row.get('elevation','none') != 'none': label='awaiting elevation approval'
        elif latest and latest.get('status') == 'running': label='active attempt' if state['running'] else 'interrupted attempt'
        elif latest and latest.get('status') == 'failed': label='retry wait' if row['cooldown_seconds'] else 'failed; awaiting retry'
        elif row.get('next_run',0)>time.time(): label='waiting for next cycle'
        else: label='queued'
        row['state'] = label
    state['pending'] = tasks
    state['latest_attempts'] = attempts
    if task_id and not tasks:
        done = read(root/'state.json', {}).get('done', [])
        state['selected_task'] = {'id':task_id,'state':'completed' if task_id in done else 'not found in pending queue'}
    return state


def render(state, watching=False):
    label = 'paused' if state['paused'] else 'running' if state['running'] else 'stopped'
    print('Worker: '+label+' | '+time.strftime('%H:%M:%S'))
    for row in state['pending']:
        print(f"\n{row['id']}\n  {row['state']} | verified cycles: {row.get('cycles_completed',0)}")
        print('  Project: '+row['project'])
        print(f"  Profile: {row.get('profile','coding')} | permissions: {row.get('permissions','default')} | elevation: {row.get('elevation','none')}")
        if row['cooldown_seconds']: print(f"  Retry cooldown: {row['cooldown_seconds']} seconds")
        latest = row['last_attempt']
        if latest:
            print(f"  Last attempt: {latest.get('status','unknown')} | exit: {latest.get('exit_code','-')}")
            print('  Logs: '+latest['logs'])
        else:
            print('  No attempts recorded yet')
    if state.get('selected_task'):
        print(state['selected_task']['id']+': '+state['selected_task']['state'])
    if watching:print('\nCtrl+C closes this view; the task continues.')


def watch(config=None, task_id=None, swarm_only=False, follow=True, as_json=False, interval=2):
    try:
        while True:
            state = snapshot(config, task_id, swarm_only)
            if as_json:
                print(json.dumps(state), flush=True)
            else:
                if follow and sys.stdout.isatty(): print('\033[2J\033[H', end='')
                render(state,follow)
            if not follow: return
            time.sleep(interval)
    except KeyboardInterrupt:
        return


def logs(config=None, task_id=None, follow=False, lines=30):
    from codelaboon.work import configuration
    _,_,root=configuration(config)
    offsets={}
    waiting=False
    try:
        while True:
            if task_id:
                state=snapshot(config,task_id)
                attempt=state['latest_attempts'].get(task_id)
                paths=[Path(attempt['logs'])/'output.log'] if attempt else []
            else:
                paths=[root/'supervisor.log',root/'service.stderr.log']
            found=False
            for path in paths:
                try:
                    size=path.stat().st_size
                    first=path not in offsets
                    position=max(0,size-65536) if first else offsets[path]
                    if size<position:position=0
                    with path.open('rb') as stream:
                        stream.seek(position);raw=stream.read(65536);offsets[path]=stream.tell()
                except OSError:
                    continue
                found=True
                if first:
                    print('\n== '+str(path)+' ==',flush=True)
                    if not raw:print('(no output yet)',flush=True)
                if raw:
                    text=raw.decode('utf-8',errors='replace')
                    if first:text='\n'.join(text.splitlines()[-lines:])+'\n'
                    print(text,end='',flush=True)
            if not found and not waiting:
                print('Waiting for task output...' if task_id else 'No worker logs yet.',flush=True)
                waiting=True
            if not follow:return
            time.sleep(1)
    except KeyboardInterrupt:
        return
