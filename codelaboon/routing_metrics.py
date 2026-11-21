"""Private task-aware routing observations; no prompts, keys or raw errors."""
from contextlib import closing,contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from codelaboon.paths import config_dir

TASKS=('general','coding','planning','security')
_LOCK=threading.RLock();_CACHE=[None,0,{}]


def task_class(messages=(),default=None):
    explicit=os.environ.get('CODELABOON_ROUTING_TASK')
    if explicit in TASKS:return explicit
    if default=='security':return default
    words=' '.join(str(row.get('content',''))[-2000:] for row in list(messages)[-4:]).lower()
    if any(word in words for word in ('pentest','vulnerability','security audit','authorized targets')):return 'security'
    if any(word in words for word in ('stage: plan','implementation plan','plan before')):return 'planning'
    if any(word in words for word in ('code','test','implement','refactor','debug','repository')):return 'coding'
    return default if default in TASKS else 'general'


def enabled():return os.environ.get('CODELABOON_METRICS','1')!='0'
def key(name,provider,model,task):
    from codelaboon.model_health import scope
    return scoped_key(scope(name,provider),model,task)


def scoped_key(scope, model, task):
    return hashlib.sha256((scope+'/'+model+'/'+task).encode()).hexdigest()


@contextmanager
def database():
    root=config_dir();root.mkdir(parents=True,exist_ok=True,mode=0o700);path=root/'routing.sqlite3'
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
    with _LOCK,closing(sqlite3.connect(path,timeout=.2)) as db,db:
        db.execute('CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, provider TEXT, model TEXT, task TEXT, updated REAL, data TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY)')
        yield db
    _CACHE[1]=0


def valid_row(value):
    if not isinstance(value,dict):return {}
    result={}
    for name in ('ok','failed','cancelled','tool_responses','checks_passed','checks_failed'):
        number=value.get(name,0)
        result[name]=number if type(number) is int and 0<=number<=10**12 else 0
    for name in ('seconds','first_byte','first_token','tokens_per_second'):
        values=value.get(name,[])
        result[name]=[v for v in values[-64:] if type(v) in (int,float) and math.isfinite(v) and 0<=v<=10**9] if isinstance(values,list) else []
    return result


def rows():
    if not enabled():return {}
    path=config_dir()/'routing.sqlite3'
    if not path.exists():return {}
    if _CACHE[0]==str(path) and _CACHE[1]>time.monotonic():return _CACHE[2]
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.05)) as db:
            result={identity:dict(valid_row(json.loads(data)),provider=provider,model=model,task=task) for identity,provider,model,task,data in db.execute('SELECT id,provider,model,task,data FROM observations ORDER BY updated DESC LIMIT 2048')}
        result={k:v for k,v in result.items() if isinstance(v,dict)}
    except (OSError,sqlite3.Error,ValueError,TypeError):result={}
    _CACHE[:]=[str(path),time.monotonic()+2,result];return result


def observe(name,provider,model,task,status,seconds,first_byte=None,first_token=None,tokens=None,tools=False):
    if not enabled():return
    identity=key(name,provider,model,task)
    try:
        with database() as db:
            previous=db.execute('SELECT data FROM observations WHERE id=?',(identity,)).fetchone();row=valid_row(json.loads(previous[0])) if previous else {}
            row[status]=row.get(status,0)+1
            if status=='ok':
                for label,value in [('seconds',seconds),('first_byte',first_byte),('first_token',first_token)]:
                    if isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=86400:row[label]=(row.get(label,[])+[round(value,4)])[-64:]
                if isinstance(tokens,int) and tokens>=0 and seconds>0:row['tokens_per_second']=(row.get('tokens_per_second',[])+[round(tokens/seconds,3)])[-64:]
                if tools:row['tool_responses']=row.get('tool_responses',0)+1
            db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)',(identity,name,model,task,time.time(),json.dumps(row)))
            db.execute('DELETE FROM observations WHERE id IN (SELECT id FROM observations ORDER BY updated DESC LIMIT -1 OFFSET 2048)')
        trace=os.environ.get('CODELABOON_ROUTING_TRACE')
        if trace and status=='ok':
            path=Path(trace)
            if not path.exists() or path.stat().st_size<65536:
                with os.fdopen(os.open(path,os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600),'a') as stream:stream.write(json.dumps({'key':identity,'task':task})+'\n')
    except (OSError,sqlite3.Error,ValueError,TypeError):pass


def feedback(trace,passed):
    if not enabled() or not Path(trace).exists():return
    try:
        path=Path(trace);content=path.read_bytes()[:65536];identities={json.loads(line)['key'] for line in content.splitlines()}
        marker=hashlib.sha256((str(path.resolve())).encode()).hexdigest()
        with database() as db:
            if db.execute('SELECT 1 FROM feedback WHERE id=?',(marker,)).fetchone():return
            for identity in identities:
                previous=db.execute('SELECT data FROM observations WHERE id=?',(identity,)).fetchone()
                if not previous:continue
                row=valid_row(json.loads(previous[0]));label='checks_passed' if passed else 'checks_failed';row[label]=row.get(label,0)+1
                db.execute('UPDATE observations SET data=?,updated=? WHERE id=?',(json.dumps(row),time.time(),identity))
            db.execute('INSERT INTO feedback VALUES (?)',(marker,))
            db.execute('DELETE FROM feedback WHERE rowid IN (SELECT rowid FROM feedback ORDER BY rowid DESC LIMIT -1 OFFSET 8192)')
    except (OSError,sqlite3.Error,ValueError,KeyError):pass


def percentile(values,fraction):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    return values[min(len(values)-1,int((len(values)-1)*fraction))] if values else None


def adjustment(name,provider,model,task):
    return score(rows().get(key(name,provider,model,task),{}), task, preset())


def score(row, task, routing_preset):
    success=row.get('ok',0);fail=row.get('failed',0)
    if success+fail<2:return 0.0
    reliability=(success+1)/(success+fail+2)
    quality=(row.get('checks_passed',0)+1)/(row.get('checks_passed',0)+row.get('checks_failed',0)+2)
    delay=percentile(row.get('first_token',[]) or row.get('first_byte',[]) or row.get('seconds',[]),.5)
    speed=1/(1+delay) if delay is not None else .5
    # Bound learned influence; diagnostic probes are not model intelligence scores.
    quality_weight,speed_weight={'fast':(.15,.25),'balanced':(.25,.10),'deep':(.40,.03)}[routing_preset]
    if task=='security':quality_weight=max(.30,quality_weight)
    return .20*(reliability-.5)+quality_weight*(quality-.5)+speed_weight*(speed-.5)


def report():
    result=[]
    for row in rows().values():
        result.append({k:row.get(k,0) for k in ('provider','model','task','ok','failed','cancelled','tool_responses','checks_passed','checks_failed') } | {
            'first_token_p50':percentile(row.get('first_token',[]),.5),'first_token_p95':percentile(row.get('first_token',[]),.95),
            'response_p50':percentile(row.get('seconds',[]),.5),'tokens_per_second_p50':percentile(row.get('tokens_per_second',[]),.5)})
    return result


class MeasuredResponse:
    def __init__(self,response,name,provider,model,task,started):
        self.response=response;self.name=name;self.provider=provider;self.model=model;self.task=task;self.started=started
        self.first_byte=None;self.first_token=None;self.tokens=None;self.tools=False;self.has_output=False;self.error=False;self.done=False;self.pending=b''
    def __getattr__(self,name):return getattr(self.response,name)
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def parse(self,value,streaming=True):
        if not isinstance(value,dict):return
        if value.get('error'):self.error=True
        usage=value.get('usage') or {}
        if not isinstance(usage,dict):usage={}
        if isinstance(usage.get('completion_tokens'),int):self.tokens=usage['completion_tokens']
        choices=value.get('choices',[])
        for choice in choices if isinstance(choices,list) else []:
            if not isinstance(choice,dict):continue
            delta=choice.get('delta',choice.get('message',{}))
            if not isinstance(delta,dict):continue
            self.tools=self.tools or bool(delta.get('tool_calls'))
            self.has_output=self.has_output or bool(delta.get('content') or delta.get('reasoning_content') or delta.get('tool_calls'))
            if streaming and self.first_token is None and (delta.get('content') or delta.get('reasoning_content') or delta.get('tool_calls')):self.first_token=time.monotonic()-self.started
    def finish(self,status):
        if self.done:return
        self.done=True
        observe(self.name,self.provider,self.model,self.task,status,time.monotonic()-self.started,self.first_byte,self.first_token,self.tokens,self.tools)
    def iter_content(self,*args,**kwargs):
        document=bytearray()
        try:
            for chunk in self.response.iter_content(*args,**kwargs):
                if chunk and self.first_byte is None:self.first_byte=time.monotonic()-self.started
                raw=chunk.encode('utf-8') if isinstance(chunk,str) else chunk
                if len(document)<262144:document.extend(raw[:262144-len(document)])
                self.pending+=raw
                while b'\n' in self.pending:
                    line,self.pending=self.pending.split(b'\n',1)
                    if line.startswith(b'data:') and line[5:].strip()!=b'[DONE]':
                        try:self.parse(json.loads(line[5:]))
                        except (ValueError,TypeError):pass
                if len(self.pending)>262144:self.pending=b''
                yield chunk
            if document.lstrip().startswith(b'{'):
                try:self.parse(json.loads(document))
                except (ValueError,TypeError):pass
            self.finish('ok' if 200<=self.response.status_code<300 and not self.error and self.has_output else 'failed')
        except BaseException:
            self.finish('cancelled' if __import__('sys').exc_info()[0] is GeneratorExit else 'failed');raise
    def iter_lines(self,chunk_size=512,decode_unicode=False,delimiter=None):
        pending=b''
        for chunk in self.iter_content(chunk_size=chunk_size):
            pending+=chunk
            separator=delimiter.encode() if isinstance(delimiter,str) else delimiter or b'\n'
            while separator in pending:
                line,pending=pending.split(separator,1);line=line.rstrip(b'\r')
                yield line.decode(getattr(self,'encoding',None) or 'utf-8',errors='replace') if decode_unicode else line
        if pending:yield pending.decode(getattr(self,'encoding',None) or 'utf-8',errors='replace') if decode_unicode else pending
    def json(self):
        try:
            value=self.response.json();self.parse(value,streaming=False)
            self.finish('ok' if 200<=self.response.status_code<300 and not self.error and self.has_output else 'failed');return value
        except BaseException:self.finish('failed');raise
    def close(self):
        self.finish('cancelled');self.response.close()

def preset():
    value=os.environ.get('CODELABOON_ROUTING_PRESET')
    if value is None:
        try:value=json.loads((config_dir()/'routing.json').read_text()).get('preset','balanced')
        except (OSError,ValueError,AttributeError):value='balanced'
    return value if value in ('fast','balanced','deep') else 'balanced'


def main(arguments=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['status','configure']);parser.add_argument('--preset',choices=['fast','balanced','deep']);parser.add_argument('--json',action='store_true');args=parser.parse_args(arguments)
    if args.action=='configure':
        if not args.preset:parser.error('configure requires --preset')
        from codelaboon.watch import save
        root=config_dir();root.mkdir(parents=True,exist_ok=True,mode=0o700);save(root/'routing.json',{'preset':args.preset})
    print(json.dumps({'preset':preset(),'observations':report(),'interpretation':'Observed latency and task-check outcomes; sparse models retain curated priors.'},indent=2))
