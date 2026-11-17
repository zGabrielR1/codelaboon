"""Tasks as ordinary chat sessions, shared by the browser and native engines."""
import datetime
import os
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

from codelaboon import task_api
from codelaboon.task_conversation import directory,tail


def document(identity):
    _,_,record=task_api.selected(identity)
    state=task_api.snapshot()
    task=next((row for row in state['tasks'] if row['id']==identity),None)
    if task is None:raise ValueError('Task not found')
    conversation=task_api.conversation(identity)
    rows=[{'id':'objective','role':'user','content':record['prompt'],'created':0}]
    rows.extend({'id':row['id'],'role':'user','content':row['text'],'created':row['created'],
                 'delivery':row.get('delivery',''),'note':row.get('mode')=='note'} for row in conversation['messages'])
    rows.extend({'id':row['id'],'role':'assistant','content':row['text'],'created':row['created'],
                 'partial':row.get('partial',False),'kind':row.get('kind')}
                for row in conversation['events'] if row.get('kind') in ('reply','plan'))
    errors=[row for row in conversation['events'] if row.get('kind')=='error']
    latest=max((row['created'] for row in conversation['events']),default=0)
    return {'task':task,'worker':state['worker'],'messages':sorted(rows,key=lambda row:(row['created'],row['id'])),
            'latest_error':errors[-1]['text'] if errors and errors[-1]['created']>=latest else '',
            'activity':task.get('state','queued')}


def model_rows():
    try:
        state=task_api.snapshot()
        return [{'id':'task/'+row['id'],'name':'Task: '+row['title'],'api':'chat'} for row in state['tasks']]
    except (OSError,ValueError):return []


def native_document(identity):
    config,root,_=task_api.selected(identity)
    value=document(identity)
    project=Path(value['task']['project']).expanduser()
    if not project.is_absolute():project=(config.parent if config else Path.cwd())/project
    stable=str(uuid.uuid5(uuid.NAMESPACE_URL,str(directory(root,identity).resolve())))
    return {'format':'codelaboon.session.v1','id':stable,'title':value['task']['title'],
            'cwd':str(project.resolve()),'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'messages':[{'role':row['role'],'content':row['content']} for row in value['messages'] if not row.get('note')],
            'origin':{'engine':'task','native_id':identity,'source':str(root.resolve())},
            'archive':{'task':identity,'messages':value['messages']}}


def user_text(messages):
    for message in reversed(messages):
        if message.get('role')!='user':continue
        value=message.get('content','')
        if isinstance(value,str):return value
        if isinstance(value,list):return '\n'.join(part.get('text','') for part in value if isinstance(part,dict) and part.get('type') in ('text','input_text'))
    raise ValueError('Send a user message to the task conversation')


class TaskResponse:
    """OpenAI chat transport: the engine is a client, the orchestrator owns tools."""
    status_code=200
    codelaboon_google_oauth=False
    encoding='utf-8'

    def __init__(self,identity,body):
        self.identity=identity;self.model=body['model'];self.streaming=bool(body.get('stream'))
        self.headers={'Content-Type':'text/event-stream' if self.streaming else 'application/json'}
        self.closed=threading.Event();self.reply=None
        self.message_id='engine-'+hashlib.sha256(json.dumps(body.get('messages',[]),sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:48]
        text=user_text(body.get('messages',[])).strip()
        if not text:raise ValueError('Task message must not be empty')
        self.immediate=''
        if text.startswith('/task '):
            command=text[6:].strip()
            if command in ('pause','resume','stop'):self.immediate=task_api.control(identity,command)['message']
            elif command=='start':self.immediate=task_api.worker_control('start')['message']
            elif command=='status':self.immediate=self.status_text(document(identity))
            else:raise ValueError('Task commands: /task status, /task start, /task pause, /task resume, /task stop')
            return
        receipt=task_api.message({'task':identity,'message_id':self.message_id,'text':text,'mode':'guidance'})
        self.immediate=receipt.get('execution_error','')
        state=document(identity)
        if state['worker'].get('paused') or state['activity']=='paused':
            self.immediate='Your message is saved. '+self.status_text(state)+' Resume the task with /task resume; use /task start if the worker is stopped.'

    @staticmethod
    def status_text(value):
        return 'Task: '+value['activity']+'. Background worker: '+('running' if value['worker']['running'] else 'stopped')+'.'

    def chunks(self):
        if self.immediate:yield self.immediate;return
        _,root,_=task_api.selected(self.identity)
        marker=directory(root,self.identity)/(self.message_id+'.included')
        sent='';active=None;planned=None;deadline=time.monotonic()+3600;checkpoint=0
        while not self.closed.is_set() and time.monotonic()<deadline:
            if time.monotonic()>=checkpoint:
                value=document(self.identity);checkpoint=time.monotonic()+5
                if value['worker'].get('paused') or value['activity'] in ('paused','stopped'):
                    yield '\n\n'+self.status_text(value)+' Your message remains saved.';return
            if marker.is_file():
                attempt=active or root/marker.read_text(encoding='utf-8').strip()
                if planned is not None:
                    candidates=[]
                    for source in root.glob('*/result.json'):
                        if not source.resolve().is_relative_to(root.resolve()):continue
                        try:row=json.loads(source.read_text(encoding='utf-8'))
                        except (OSError,ValueError):continue
                        if row.get('task')==self.identity and row.get('stage')!='plan' and row.get('started',0)>=planned:
                            candidates.append((row['started'],source.parent))
                    if not candidates:
                        yield None;self.closed.wait(1);continue
                    active=min(candidates)[1];attempt=active;planned=None;sent=''
                    yield '\n\n'

                if not attempt.resolve().is_relative_to(root.resolve()):raise ValueError('Invalid task attempt')
                reply=tail(attempt/'reply.txt',48000) or tail(attempt/'reply.partial.txt',48000) or tail(attempt/'orchestrator-plan.md',24000)
                if reply.startswith(sent) and reply!=sent:yield reply[len(sent):];sent=reply
                try:result=json.loads((attempt/'result.json').read_text(encoding='utf-8'))
                except (OSError,ValueError):result={}
                if result.get('status')=='succeeded' and result.get('stage')=='plan':
                    planned=result.get('finished',result.get('started',0))
                    yield None;self.closed.wait(1);continue
                if result.get('status') in ('succeeded','failed','paused','redirected'):
                    if result['status']!='succeeded':
                        value=document(self.identity)
                        yield '\n\n'+(value['latest_error'] or self.status_text(value))
                    elif not sent:yield 'This orchestration step finished. The task continues according to its scheduling and verification policy.'
                    return
            yield None  # SSE heartbeat while work continues independently.
            self.closed.wait(1)
        if not self.closed.is_set():yield '\n\nThe task is still queued or running. Open its chat to follow progress; no duplicate work was started.'

    def json(self):
        if self.reply is None:self.reply=''.join(text for text in self.chunks() if text)
        return {'id':'chatcmpl-'+self.message_id,'object':'chat.completion','created':int(time.time()),'model':self.model,
                'choices':[{'index':0,'message':{'role':'assistant','content':self.reply},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':0,'completion_tokens':0}}

    def iter_content(self,chunk_size=None):
        if not self.streaming:yield json.dumps(self.json()).encode();return
        for text in self.chunks():
            if text is None:yield b': task work is active\n\n';continue
            yield ('data: '+json.dumps({'id':'chatcmpl-'+self.message_id,'object':'chat.completion.chunk','model':self.model,
                'choices':[{'index':0,'delta':{'content':text},'finish_reason':None}]})+'\n\n').encode()
        yield ('data: '+json.dumps({'id':'chatcmpl-'+self.message_id,'object':'chat.completion.chunk','model':self.model,
            'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode()

    def iter_lines(self,decode_unicode=False,**kwargs):
        for chunk in self.iter_content():
            for line in chunk.splitlines():yield line.decode() if decode_unicode else line

    def close(self):self.closed.set()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def open_native(engine,identity):
    from codelaboon.session_transfer import save,resume
    value=native_document(identity)
    session=save(value,identity=value['id'])
    previous=os.environ.get('CODELABOON_TASK_CHAT_MODEL')
    os.environ['CODELABOON_TASK_CHAT_MODEL']='task/'+identity
    try:return resume(session,engine,model='task/'+identity)
    finally:
        if previous is None:os.environ.pop('CODELABOON_TASK_CHAT_MODEL',None)
        else:os.environ['CODELABOON_TASK_CHAT_MODEL']=previous
