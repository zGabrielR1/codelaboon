"""Actionable, bounded verification evidence shared by the worker and chat UI."""
import hashlib
import json
import re
from codelaboon.task_conversation import tail
from codelaboon.task_changes import redact


def failed_check(attempt,row):
    checks=row.get('checks',[])
    failed=next((check for check in reversed(checks) if check.get('exit_code',0)),None)
    if failed:
        command=' '.join(str(part) for part in failed.get('argv',[]))
        output=tail(attempt/('check-'+str(failed['index'])+'.log'),5000)
        code=failed.get('exit_code')
    else:
        logs=sorted(attempt.glob('check-*.log'))
        if not logs:return None
        command='Configured project verification';output=tail(logs[-1],5000);code=row.get('exit_code')
    output=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',redact(output)).strip()
    missing=(code==127 or "can't open file" in output.lower() or 'command not found' in output.lower()
             or bool(re.search(r'(?i)(?:python[^\n]*: )?no module named (?:pytest|unittest|tox|nox)(?:[\s.\x27]|$)',output)))
    timeout=code==124 or 'time budget exhausted' in output.lower()
    kind='verification_configuration' if missing else 'verification_timeout' if timeout else 'verification'
    summary=('Verification setup needs attention' if missing else 'Verification ran out of time' if timeout else 'A project check failed')+': '+redact(command)+' (exit '+str(code)+').'
    detail='\n'.join(output.splitlines()[-12:])[-1800:]
    return {'kind':kind,'command':redact(command),'exit_code':code,'summary':summary,'output':detail,
            'signature':hashlib.sha256((command+'\n'+output[-2000:]).encode()).hexdigest()}


def reserve_seconds(task,stage,budget):
    # Keep one cycle bounded, but give independent checks a real share of it.
    if stage=='plan' or not task.get('swarm') or not task.get('verify_argv'):return 0
    return min(120,max(.1,budget*.2))


def record_failure(root,task,state,record,attempt):
    from codelaboon.work_queue import controls
    failures=state.setdefault('check_failures',{})
    if record.get('verification')!='failed':
        if record.get('status')=='succeeded':failures.pop(task['id'],None)
        return
    detail=failed_check(attempt,record)
    if not detail:return
    record['failure_detail']=detail;record['failure_kind']=detail['kind']
    previous=failures.get(task['id'],{})
    count=previous.get('count',0)+1 if previous.get('signature')==detail['signature'] else 1
    failures[task['id']]={'signature':detail['signature'],'count':count}
    pause=detail['kind']=='verification_configuration' or count>=3
    if pause:
        control=controls(root,task['id']);control.mkdir(parents=True,exist_ok=True)
        (control/'PAUSE').touch()
        record['needs_attention']=True
        record['recovery']='Fix the verification command or project issue, then resume this task.' if detail['kind']=='verification_configuration' else 'The same check failed three times. Review the check output or change the model, then resume.'
    else:record['recovery']='The orchestrator receives this check output on its next attempt and can repair the failure.'
