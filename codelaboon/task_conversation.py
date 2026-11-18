"""Durable human guidance, consumed only at ordinary worker checkpoints."""
import json
import os
import re
import time
from pathlib import Path
import tempfile
import math
from codelaboon.work_queue import controls


def directory(root, identity):
    path=controls(root,identity)/'messages'
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def history(root, identity):
    rows=[]
    for path in directory(root,identity).glob('*.json'):
        try:
            row=json.loads(path.read_text(encoding='utf-8'))
            if path.with_suffix('.included').exists():
                row['delivery']='Included in attempt '+path.with_suffix('.included').read_text(encoding='utf-8')
            else:row['delivery']='Saved note' if row['mode']=='note' else 'Queued for next attempt'
            rows.append(row)
        except (OSError,ValueError,KeyError):continue
    return sorted(rows,key=lambda row:(row['created'],row['id']))[-100:]


def post(root, identity, message_id, text, mode='guidance'):
    if not isinstance(message_id,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}',message_id):raise ValueError('Invalid message ID')
    if not isinstance(text,str) or not text.strip() or len(text)>4096:raise ValueError('Message must contain 1–4096 characters')
    if mode not in ('guidance','note'):raise ValueError('Unsupported message mode')
    row={'id':message_id,'text':text.strip(),'mode':mode,'created':time.time()}
    path=directory(root,identity)/(message_id+'.json')
    try:
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        previous=json.loads(path.read_text(encoding='utf-8'))
        if (previous['text'],previous['mode'])!=(row['text'],mode):raise ValueError('Message ID reused with different content')
        return previous
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:json.dump(row,stream)
    return row


def context(root, task):
    # Privileged cases are immutable approval snapshots, never live chat sessions.
    if task.get('elevation','none')!='none' or task.get('_privileged_case'):return '',[]
    rows=[row for row in history(root,task['id']) if row['mode']=='guidance'][-16:]
    text='\n'.join(row['text'] for row in rows)
    if not text:return '',[]
    replies=[row for row in attempt_events(root,task['id']) if row.get('kind')=='reply' and not row.get('partial')][-4:]
    transcript='\n\nRecent orchestrator replies:\n'+'\n\n'.join(row['text'] for row in replies) if replies else ''
    return ('\n\nHuman guidance at this checkpoint (subordinate to the original objective, scope, permissions and verification; never expand them):\n'+text[-12000:]+transcript[-12000:]),[row['id'] for row in rows]


def included(root, identity, messages, attempt):
    for message in messages:
        path=directory(root,identity)/(message+'.included')
        try:
            with path.open('x',encoding='utf-8') as stream:stream.write(str(attempt))
        except FileExistsError:pass


def save_reply(text,partial=False):
    """Persist actual model output separately from command/debug output."""
    target=os.environ.get('CODELABOON_TASK_REPLY_FILE')
    if not target or not isinstance(text,str) or not text.strip():return
    path=Path(target)
    if partial:path=path.with_name('reply.partial.txt')
    fd,temporary=tempfile.mkstemp(prefix='.reply-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(text[:48000])
        os.replace(temporary,path)
        if not partial:path.with_name('reply.partial.txt').unlink(missing_ok=True)
    finally:Path(temporary).unlink(missing_ok=True)


def pending_turns(root,tasks,state):
    """New human turns wake completed conversations only at scheduler checkpoints."""
    changed=False
    for identity,task in tasks.items():
        control=controls(root,identity)
        if task.get('elevation','none')!='none' or not task.get('swarm') or (control/'STOP').exists():continue
        unread=[row for row in history(root,identity) if row['mode']=='guidance' and row['delivery']=='Queued for next attempt']
        if not unread:continue
        if identity in state.get('done',[]):state['done'].remove(identity);changed=True
        for key in ('next_run','plans'):
            if identity in state.get(key,{}):state[key].pop(identity);changed=True
        # Never reset provider cooldowns or override explicit pause/stop controls.
    return changed


def tail(path,limit=16000):
    try:
        if Path(path).is_symlink():return ''
        with Path(path).open('rb') as stream:
            stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-limit))
            return stream.read(limit).decode('utf-8',errors='replace')
    except OSError:return ''


def failure_kind(text):
    lower=text.lower()
    if 'file not found: execute the attached task specification' in lower:return 'engine_arguments'
    if any(value in lower for value in ('no free coding model','no free model is configured','admission failed','http 429','status: 429','429 too many','rate limit','rate_limit','overloaded_error')):return 'provider_unavailable'
    return 'execution'


def attempt_events(root,identity):
    """The durable conversation contains real plans/replies and honest status turns."""
    from codelaboon.task_changes import redact
    result=[]
    for source in Path(root).glob('*/result.json'):
        if not source.resolve().is_relative_to(Path(root).resolve()):continue
        try:
            if source.stat().st_size>131072:continue
            row=json.loads(source.read_text(encoding='utf-8'))
            if row.get('task')!=identity:continue
            attempt=source.parent;started=row.get('started',0);finished=row.get('finished',started)
            if any(type(value) not in (int,float) or not math.isfinite(value) for value in (started,finished)):continue
            state=row.get('status','unknown');phase=row.get('phase','working');engine=row.get('engine','worker')
            text={'planning':'The orchestrator is preparing the next work plan.',
                  'working':'The orchestrator is coordinating '+(engine+' workers.' if engine!='worker' else 'the workers.'),
                  'verifying':'The workers have replied. Independent checks are running.'}.get(phase,'The task is running.')
            if state!='running':text='Work started with '+engine+'.'
            result.append({'id':attempt.name+'-started','created':started,'role':'orchestrator','kind':'status','text':text})
            plan=attempt/'orchestrator-plan.md'
            if plan.is_file():result.append({'id':attempt.name+'-plan','created':min(plan.stat().st_mtime,row.get('finished',time.time())),'role':'orchestrator','kind':'plan','text':redact(tail(plan,24000))})
            reply_path=attempt/'reply.txt';partial=not reply_path.is_file()
            if partial:reply_path=attempt/'reply.partial.txt'
            reply=tail(reply_path,48000)
            if reply:result.append({'id':attempt.name+'-reply','created':min(reply_path.stat().st_mtime,row.get('finished',time.time())),
                'role':'orchestrator','kind':'reply','text':redact(reply),'engine':engine,'partial':partial})
            if state=='failed':
                output=tail(attempt/'output.log')+'\n'+tail(attempt/'orchestrator.log');kind=row.get('failure_kind') or failure_kind(output)
                if kind=='provider_unavailable':text='The local gateway is reachable, but free providers are rate limited or unavailable. No paid model was used. The orchestrator will retry after the cooldown; you can choose another model in Models & prompts.'
                elif kind=='engine_arguments':text='The engine treated the task instruction as a filename. Update Codelaboon to use the corrected OpenCode/Kilo launcher, then retry this conversation.'
                elif row.get('verification')=='failed':
                    from codelaboon.task_diagnostics import failed_check
                    detail=row.get('failure_detail') or failed_check(attempt,row)
                    text=(detail['summary']+'\n'+detail['output'] if detail else 'A project check failed. Open Attempts to inspect the check output.')+'\n'+row.get('recovery','The orchestrator receives the check output on its next attempt.')
                    kind=detail['kind'] if detail else 'verification'
                else:text='The worker did not finish this attempt. Open Attempts for the engine output; your task and messages are saved.'
                result.append({'id':attempt.name+'-result','created':finished,'role':'orchestrator','kind':'error','text':text,'failure_kind':kind})
            elif state=='succeeded':
                text='Planning is complete. The workers will execute the plan.' if row.get('stage')=='plan' else 'This cycle passed its independent checks. The orchestrator will continue automatically if more cycles are scheduled; you can reply here to continue the conversation.'
                result.append({'id':attempt.name+'-result','created':finished,'role':'orchestrator','kind':'status','text':text})
        except (OSError,ValueError,TypeError,KeyError):continue
    return sorted(result,key=lambda row:(row['created'],row['id']))[-120:]
