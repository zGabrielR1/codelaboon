"""Authenticated web task operations, backed by the same durable CLI queue."""
import json
from pathlib import Path
import re


def configuration():
    from codelaboon.work import configuration as load
    from codelaboon.paths import config_dir
    if not (config_dir()/'work.json').is_file():return None,None,None
    return load()


def task_records(value, root):
    tasks=list(value.get('tasks',[]))
    for path in (root/'inbox').glob('*.json'):
        try:tasks.append(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,ValueError):continue
    return {task['id']:task for task in tasks if isinstance(task,dict) and isinstance(task.get('id'),str)}


def snapshot():
    from codelaboon.engine_tasks import catalog
    from codelaboon import __version__
    path,value,root=configuration()
    result={'version':__version__,'workspace':str(Path.cwd().resolve()),'configured':bool(path),
            'worker':{'running':False,'paused':False},'engines':catalog(),'tasks':[]}
    if path is None:return result
    from codelaboon.work_monitor import snapshot as monitored
    state=monitored(path)
    records=task_records(value,root)
    pending={task['id']:task for task in state['pending']}
    try:scheduling=json.loads((root/'state.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):scheduling={}
    done=set(scheduling.get('done',[]))
    result['worker']={key:state[key] for key in ('running','paused','completed','service')}
    for identity,task in records.items():
        row=pending.get(identity,{'id':identity,'state':'completed' if identity in done else 'queued',
            'cycles_completed':scheduling.get('cycles',{}).get(identity,0),
            'last_attempt':state['latest_attempts'].get(identity)})
        result['tasks'].append({**row,'title':task.get('prompt','').splitlines()[0][:100] if task.get('prompt') else identity,
            'objective':task.get('prompt','')[:16000],'project':task['project'],'scope':task.get('scope',''),
            'permissions':task.get('permissions','default'),'profile':task.get('profile','coding'),
            'elevation':task.get('elevation','none'),'supervision':task.get('supervision',{'enabled':False}),
            'engine':task.get('swarm',{}).get('engine','jcode') if task.get('swarm') else 'configured harness',
            'swarm':task.get('swarm'),'verification':task.get('verify_argv',[])})
    return result


def selected(identity):
    if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',identity):
        raise ValueError('Invalid task ID')
    path,value,root=configuration()
    if root is None:raise ValueError('No worker configuration yet')
    record=task_records(value,root).get(identity)
    if not record:raise ValueError('Unknown task ID')
    return path,root,record


def logs(identity):
    path,root,_=selected(identity)
    from codelaboon.work_monitor import snapshot as monitored
    state=monitored(path,identity)
    attempt=state['latest_attempts'].get(identity)
    if not attempt:return {'task':identity,'text':'','attempt':None,'truncated':False}
    source=Path(attempt['logs'])/'output.log'
    if not source.resolve().is_relative_to(root.resolve()):raise ValueError('Log path is outside the worker runtime')
    try:
        with source.open('rb') as stream:
            stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-16384));raw=stream.read(16384)
    except FileNotFoundError:raw=b'';size=0
    text=raw.decode('utf-8',errors='replace').replace('\0','<NUL>')
    text=re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))','',text)
    text=re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|access[_-]?token|password)\s*[=:]\s*)[^\s,;]+',r'\1[redacted]',text)
    text=re.sub(r'sk-[A-Za-z0-9_-]+','[redacted]',text)
    return {'task':identity,'text':text,'attempt':Path(attempt['logs']).name,'truncated':size>16384}


def conversation(identity):
    _,root,task=selected(identity)
    from codelaboon.task_conversation import history
    events=[]
    for path in root.glob('*/result.json'):
        try:
            row=json.loads(path.read_text(encoding='utf-8'))
            if row.get('task')==identity:
                events.append({'id':path.parent.name,'created':row.get('started',0),
                    'text':'Attempt '+path.parent.name+' · '+row.get('stage','work')+' · '+row.get('status','unknown')+
                    (' · exit '+str(row['exit_code']) if 'exit_code' in row else '')})
        except (OSError,ValueError):continue
    return {'task':identity,'messages':history(root,identity),'events':sorted(events,key=lambda row:row['created'])[-40:]}


def message(body):
    path,root,task=selected(body.get('task'))
    mode=body.get('mode','guidance')
    if mode!='note':
        if task.get('elevation','none')!='none':raise ValueError('Elevated tasks accept notes only; guidance requires a new reviewed task/case')
        from codelaboon.work import status
        worker=status(path)
        pending=next((row for row in worker.get('pending',[]) if row['id']==task['id']),None)
        if task['id'] in _completed(root) or (pending and pending.get('stopped')):
            raise ValueError('Finished tasks accept notes only; queue a new task for further work')
        if worker.get('running') and 'operator-interventions' not in worker.get('service',{}).get('features',[]):
            raise ValueError('Restart the worker at a safe checkpoint to enable task guidance. Notes are available now.')
    from codelaboon.task_conversation import post
    return post(root,task['id'],body.get('message_id'),body.get('text'),mode)


def _completed(root):
    try:return json.loads((root/'state.json').read_text(encoding='utf-8')).get('done',[])
    except FileNotFoundError:return []


def control(identity,action):
    if action not in ('pause','resume','stop'):raise ValueError('Unsupported task control')
    path,_,task=selected(identity)
    if task.get('swarm'):
        from codelaboon.swarm import control as apply
        apply(action,identity,path)
    else:
        from codelaboon.work import control as apply
        apply(action,path,identity)
    return {'task':identity,'action':action,'message':'Control requested; active work may finish first'}


def enqueue(body):
    if not isinstance(body,dict):raise ValueError('Invalid task request')
    def text(key,limit):
        value=body.get(key,'')
        if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('Provide a valid '+key)
        return value.strip()
    objective=text('objective',12000);project=text('project',4096);scope=text('scope',4096);model=text('model',512)
    if not Path(project).expanduser().is_dir():raise ValueError('Select an existing project directory')
    from codelaboon.engine_tasks import catalog
    engine=body.get('engine','jcode')
    installed=next((row for row in catalog() if row['id']==engine),None)
    if not installed or not installed['installed']:raise ValueError('Install the selected engine before queueing a GUI task')
    permissions=body.get('permissions','default')
    if permissions not in ('default','full') or body.get('profile','security') not in ('coding','security') or body.get('elevation','none') not in ('none','root','administrator'):
        raise ValueError('Invalid task policy')
    if type(body.get('supervise',False)) is not bool:raise ValueError('Invalid supervision selection')
    if permissions=='full' and body.get('confirm_full') is not True:raise ValueError('Explicitly acknowledge full native tool permissions')
    checks=body.get('checks')
    if not isinstance(checks,list) or not checks or len(checks)>20 or any(not isinstance(argv,list) or not argv or len(argv)>100 or any(not isinstance(part,str) or not part or len(part)>4096 for part in argv) for argv in checks):
        raise ValueError('Verification must contain nonempty argument arrays, not shell strings')
    options={key:body.get(key,default) for key,default in (('workers',4 if engine=='jcode' else 1),('timeout',1800),('interval',60),('cycles',0))}
    if any(type(value) is not int for value in options.values()):raise ValueError('Budgets must be whole numbers')
    allowed=body.get('allowed_paths',[])
    if not isinstance(allowed,list) or len(allowed)>100 or any(not isinstance(item,str) for item in allowed):raise ValueError('Invalid file allowlist')
    from codelaboon.swarm import enqueue as add
    identity=add(objective,checks=checks,model=model,controller='worker',project=Path(project).expanduser(),
        permissions=permissions,profile=body.get('profile','security'),scope=scope,
        supervise=body.get('supervise',False),allowed_paths=allowed,
        elevation=body.get('elevation','none'),engine=engine,start_worker=False,**options)
    from codelaboon.work import start
    try:start()
    except (OSError,RuntimeError,ValueError):
        return {'task':identity,'worker_started':False,'message':'Task was queued, but the worker could not start. Run codelaboon work start; do not queue a duplicate.'}
    return {'task':identity,'worker_started':True,'message':'Queued; elevated work awaits a reviewed native privilege case' if body.get('elevation','none')!='none' else 'Queued for the background worker'}
