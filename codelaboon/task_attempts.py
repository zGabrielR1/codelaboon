"""Bounded attempt history and checkpoint-only retries for continuous tasks."""
import json
import math
import os
from pathlib import Path
import time
import tempfile
from codelaboon.work_queue import controls


def history(root,identity):
    from codelaboon.task_diagnostics import failure_label
    rows=[]
    for path in root.glob('*/result.json'):
        if not path.resolve().is_relative_to(root.resolve()):continue
        try:
            with path.open('rb') as stream:raw=stream.read(131073)
            if len(raw)>131072:continue
            row=json.loads(raw)
            if row.get('task')!=identity or type(row.get('started',0)) not in (int,float):continue
            if type(row.get('started',0)) not in (int,float) or not math.isfinite(row.get('started',0)):continue
            rows.append({'id':path.parent.name,**{k:row[k] for k in ('stage','status','exit_code','started','finished','engine','harness','verification') if k in row}})
            if label := failure_label(row):
                rows[-1]['failure_label'] = label
        except (OSError,ValueError,AttributeError):continue
    return sorted(rows,key=lambda row:row.get('started',0),reverse=True)[:50]


def retry(root,task,worker):
    if task.get('elevation','none')!='none' or not task.get('swarm'):raise ValueError('Retry now requires a non-elevated continuous task')
    if worker['running'] and 'task-retry' not in worker.get('service',{}).get('features',[]):raise ValueError('Restart the worker safely after upgrading to enable retry')
    pending=next((row for row in worker['pending'] if row['id']==task['id']),None)
    if not pending or pending.get('stopped') or pending.get('paused') or worker.get('paused'):raise ValueError('Only an unpaused pending task can be retried')
    attempts=history(root,task['id'])
    if not attempts or attempts[0]['status']!='failed':raise ValueError('Retry now requires a finished failed attempt; active work is never duplicated')
    directory=controls(root,task['id']);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/'RETRY.json';row={'attempt':attempts[0]['id'],'created':time.time()}
    fd,temporary=tempfile.mkstemp(prefix='.retry-',dir=directory)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(row,stream)
        os.replace(temporary,path)
    finally:Path(temporary).unlink(missing_ok=True)


def consume(root,tasks,state):
    changed=False;receipts=[]
    for identity,task in tasks.items():
        path=controls(root,identity)/'RETRY.json'
        if not path.exists():continue
        receipts.append(path)
        try:
            request=json.loads(path.read_text(encoding='utf-8'))
            import re
            if not isinstance(request,dict):continue
            if not isinstance(request.get('attempt'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',request['attempt']):continue
            previous=Path(state.get('last_attempts',{}).get(identity,''))
            result=root/request['attempt']/'result.json'
            if not result.resolve().is_relative_to(root.resolve()):continue
            row=json.loads(result.read_text(encoding='utf-8'))
            if not isinstance(row,dict):continue
            if previous.name!=request['attempt'] or not previous.resolve().is_relative_to(root.resolve()):continue
            if row.get('task')!=identity or row.get('status')!='failed' or identity in state.get('done',[]) or task.get('elevation','none')!='none' or not task.get('swarm'):continue
            state['cooldowns'].pop('swarm-'+identity,None);state['next_run'].pop(identity,None);changed=True
        except (OSError,ValueError,KeyError,TypeError):continue
    return changed,receipts
