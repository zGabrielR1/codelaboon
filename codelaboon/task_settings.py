"""Versioned per-task execution choices, sampled only at attempt checkpoints."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import uuid
from codelaboon.work_queue import controls


def defaults(task):
    if task.get('execution_settings'):
        return {key:value for key,value in task['execution_settings'].items() if key!='revision'}
    return {'worker_model':task.get('swarm',{}).get('model','free'),
            'orchestrator_mode':'worker','orchestrator_model':'free',
            'worker_system_prompt':'','orchestrator_system_prompt':''}


def validate(values):
    if not isinstance(values,dict) or set(values)!={'worker_model','orchestrator_mode','orchestrator_model','worker_system_prompt','orchestrator_system_prompt'}:
        raise ValueError('Provide all five execution settings; policy fields cannot be edited here')
    result=dict(values)
    for key in ('worker_model','orchestrator_model'):
        value=result[key]
        if not isinstance(value,str) or not value.strip() or len(value)>512 or any(ord(ch)<32 for ch in value):raise ValueError('Invalid '+key)
        result[key]=value.strip().removeprefix('codelaboon/')
    if result['worker_model']!='free' and '/' not in result['worker_model']:raise ValueError('Worker model must be free or PROVIDER/MODEL (local/MODEL for local inference)')
    if result['orchestrator_mode'] not in ('worker','cloud','local'):raise ValueError('Choose worker, cloud or local orchestration')
    model=result['orchestrator_model']
    if result['orchestrator_mode']=='local' and not model.startswith('local/'):raise ValueError('Local orchestration requires local/MODEL; no cloud fallback is allowed')
    if result['orchestrator_mode']=='cloud' and (model.startswith('local/') or (model!='free' and '/' not in model)):raise ValueError('Cloud orchestration requires free or PROVIDER/MODEL')
    for key in ('worker_system_prompt','orchestrator_system_prompt'):
        if not isinstance(result[key],str) or len(result[key])>12000 or '\0' in result[key]:raise ValueError('Invalid '+key+' (maximum12000 characters)')
    return result


def read(root,task):
    path=controls(root,task['id'])/'execution-settings.json'
    try:return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return {'revision':task.get('execution_settings',{}).get('revision','initial'),'values':defaults(task),'updated':None,'history':[]}


def write(root,task,values,expected):
    values=validate(values)
    if task.get('swarm',{}).get('engine')=='devin' and (not values['worker_model'].startswith('devin/') or not values['worker_model'].split('/',1)[1]):raise ValueError('Devin requires a native devin/MODEL, not free Auto or a different provider')
    if not task.get('swarm'):raise ValueError('Execution settings currently apply to continuous swarm tasks')
    if task.get('elevation','none')!='none' or task.get('_privileged_case'):raise ValueError('Elevated task settings are immutable; queue a new reviewed task/case')
    directory=controls(root,task['id']);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    # An OS lock releases on crashes; every writer (web, terminal, CLI) shares it.
    with (directory/'settings.lock').open('a+b') as lock:
        lock.write(b'0');lock.flush();lock.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        previous=read(root,task)
        if previous['revision']!=expected:raise ValueError('Settings changed in another session. Reload before saving.')
        revision=uuid.uuid4().hex
        changes=[key for key in values if values[key]!=previous['values'][key]]
        row={'revision':revision,'values':values,'updated':time.time(),
             'history':(previous.get('history',[])+[{'revision':revision,'time':time.time(),'fields':changes}])[-50:]}
        descriptor,temporary=tempfile.mkstemp(prefix='.settings-',dir=directory)
        try:
            with os.fdopen(descriptor,'w',encoding='utf-8') as stream:json.dump(row,stream)
            os.replace(temporary,directory/'execution-settings.json')
        finally:Path(temporary).unlink(missing_ok=True)
        return row


def apply(root,task):
    if task.get('elevation','none')!='none' or task.get('_privileged_case'):return task
    row=read(root,task)
    if row['revision']=='initial':return task
    values=validate(row['values'])
    result=copy.deepcopy(task)
    result['execution_settings']={**values,'revision':row['revision']}
    result['swarm']['model']=values['worker_model']
    # Explicit planning is performed inside the bounded attempt, not the legacy router.
    result['swarm']['controller']='worker'
    return result


def system_text(task,values):
    prompt=values.get('worker_system_prompt','')
    if not prompt:return ''
    return prompt+'\n\nTask authority remains fixed. Never expand the objective, scope, OS privileges or tool permissions.\nAuthorized scope: '+task.get('scope','')+'\nIndependent checks: '+json.dumps(task.get('verify_argv',[]))
