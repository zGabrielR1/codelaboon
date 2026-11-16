"""Durable human guidance, consumed only at ordinary worker checkpoints."""
import json
import os
import re
import time
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
    return ('\n\nHuman guidance at this checkpoint (subordinate to the original objective, scope, permissions and verification; never expand them):\n'+text[-12000:]),[row['id'] for row in rows]


def included(root, identity, messages, attempt):
    for message in messages:
        path=directory(root,identity)/(message+'.included')
        try:
            with path.open('x',encoding='utf-8') as stream:stream.write(str(attempt))
        except FileExistsError:pass
