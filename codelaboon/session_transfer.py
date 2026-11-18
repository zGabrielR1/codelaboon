"""Portable session library and native conversation interchange (no inference)."""
import argparse
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import zlib

from codelaboon.paths import config_dir, data_dir

ENGINES=('opencode','kilo','codex','claude','omp','jcode','crush')


def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')


def text(value):
    if isinstance(value,str):return value
    if not isinstance(value,list):return json.dumps(value,ensure_ascii=False)
    result=[]
    for part in value:
        if not isinstance(part,dict):continue
        kind=part.get('type')
        if kind in ('text','input_text','output_text'):result.append(part.get('text',''))
        elif kind in ('tool_use','toolCall','function_call','custom_tool_call'):
            result.append('[Completed/source tool call '+str(part.get('name',part.get('tool','')))+'] '+json.dumps(part,ensure_ascii=False))
        elif kind in ('tool_result','toolResult','function_call_output','custom_tool_call_output'):
            result.append('[Source tool result] '+text(part.get('content',part.get('output',''))))
        elif kind in ('image','image_url','input_image','file'):
            result.append('[Source attachment retained in portable archive: '+kind+']')
    return '\n'.join(result)


def read_file(path):
    path=Path(path).expanduser().resolve()
    if path.stat().st_size>128*1024*1024:raise ValueError('Session exceeds the 128 MiB import limit')
    raw=path.read_text(encoding='utf-8-sig')
    try:value=json.loads(raw)
    except json.JSONDecodeError:
        value=[]
        lines=raw.splitlines()
        for index,line in enumerate(lines):
            if not line.strip():continue
            try:value.append(json.loads(line))
            except json.JSONDecodeError:
                # A running native agent may have an incomplete final append.
                if index!=len(lines)-1 or raw.endswith('\n'):raise ValueError('Malformed session record at line '+str(index+1))
    return value


def codex_history(path,seen=None,depth=0,value=None):
    """Materialize immutable fork prefixes using native byte boundaries."""
    path=Path(path).resolve();seen=set() if seen is None else seen
    if depth>16 or path in seen:raise ValueError('Cyclic or excessive Codex linked history')
    seen.add(path);rows=read_file(path) if value is None else value
    meta=next((row for row in rows if row.get('type')=='session_meta'),None)
    link=meta.get('payload',{}).get('history_base') if meta else None
    if not link:return rows
    rollout=str(uuid.UUID(link['thread_id']));offset=link.get('end_byte_offset')
    if type(offset) is not int or not 0<=offset<=128*1024*1024:raise ValueError('Invalid Codex history byte boundary')
    root=next((parent.parent for parent in path.parents if parent.name in ('sessions','archived_sessions')),None)
    if root is None:raise ValueError('Cannot locate linked Codex home; preserve its sessions directory when moving the source')
    parent=next((p for directory in (root/'sessions',root/'archived_sessions') for p in directory.glob('**/*.jsonl') if p.name.endswith(rollout+'.jsonl')),None)
    if parent is None:raise ValueError('Missing Codex parent rollout '+rollout)
    with parent.open('rb') as stream:prefix=stream.read(offset)
    if len(prefix)!=offset or (prefix and not prefix.endswith(b'\n')):raise ValueError('Incomplete Codex parent prefix')
    inherited=[json.loads(line) for line in prefix.decode('utf-8').splitlines() if line.strip()]
    inherited=codex_history(parent,seen,depth+1,inherited)
    header=json.loads(json.dumps(meta));header['payload']['history_base']=None
    header['codelaboon_original_metadata']=meta
    header['codelaboon_parent_metadata']=[row for row in inherited if row.get('type')=='session_meta']
    return [header]+[row for row in inherited if row.get('type')!='session_meta']+[row for row in rows if row is not meta]


def decode(engine,value,source=''):
    messages=[];native='';cwd='';title='';timestamp=now()
    if engine in ('opencode','kilo'):
        info=value['info'];native=info['id'];cwd=info.get('directory','');title=info.get('title','')
        source_messages=value.get('messages',[])
        reverted=info.get('revert',{}).get('messageID')
        if reverted:
            if not any(r['info'].get('id')==reverted for r in source_messages):raise ValueError('Reverted source checkpoint is absent')
            source_messages=source_messages[:next(i for i,r in enumerate(source_messages) if r['info'].get('id')==reverted)]
        for row in source_messages:
            info=row['info'];parts=row.get('parts',[]);blocks=[]
            for part in parts:
                if part.get('type')=='text':blocks.append(part.get('text',''))
                elif part.get('type')=='tool':blocks.append('[Source tool record] '+json.dumps(part,ensure_ascii=False))
                elif part.get('type')=='file':blocks.append('[Source attachment] '+json.dumps(part,ensure_ascii=False))
            if blocks:messages.append({'role':info['role'],'content':'\n'.join(blocks)})
    elif engine=='jcode':
        native=value['id'];cwd=value.get('working_dir','');title=value.get('custom_title') or value.get('title','');timestamp=value.get('created_at',timestamp)
        messages=[{'role':row['role'].lower(),'content':text(row.get('content',[]))} for row in value.get('messages',[])]
        compact=value.get('compaction')
        if compact:
            boundary=compact.get('covers_up_to_turn',0)
            messages=[{'role':'user','content':'[Source compaction summary]\n'+compact.get('summary_text','')}]+messages[boundary:]
    elif engine=='crush':
        native=value['session']['id'];title=value['session'].get('title','');cwd=value.get('cwd','')
        records=value.get('messages',[]);summary=value['session'].get('summary_message_id')
        if summary and any(r['id']==summary for r in records):records=records[next(i for i,r in enumerate(records) if r['id']==summary):]
        for row in records:
            parts=json.loads(row['parts']) if isinstance(row['parts'],str) else row['parts'];content=[]
            for part in parts:
                if part.get('type')=='text':content.append(part['data'].get('context','')+part['data'].get('text',''))
                elif part.get('type') in ('tool_call','tool_result'):content.append('[Source tool history] '+json.dumps(part,ensure_ascii=False))
            if content:messages.append({'role':row['role'],'content':'\n'.join(content)})
    else:
        if not isinstance(value,list):raise ValueError('Expected a native JSONL session')
        # OMP is a parent-linked tree; select the active final leaf, not all branches.
        entries=value
        if engine=='omp':
            by_id={r['id']:r for r in value if r.get('type')!='session' and r.get('id')}
            chain=[];entry=next((r for r in reversed(value) if r.get('id') in by_id),None);seen=set()
            while entry and entry['id'] not in seen:
                seen.add(entry['id']);chain.append(entry);entry=by_id.get(entry.get('parentId'))
            entries=[r for r in value if r.get('type')=='session']+list(reversed(chain))
        if engine=='claude':
            conversation=[r for r in value if r.get('type') in ('user','assistant') and not r.get('isSidechain') and r.get('uuid')]
            by_id={r['uuid']:r for r in conversation};chain=[];seen=set();entry=conversation[-1] if conversation else None
            while entry and entry['uuid'] not in seen:
                seen.add(entry['uuid']);chain.append(entry);entry=by_id.get(entry.get('parentUuid'))
            entries=list(reversed(chain))
        for row in entries:
            kind=row.get('type');payload=row.get('payload',{})
            if engine=='codex':
                if kind=='session_meta':
                    if payload.get('history_base'):raise ValueError('Linked Codex history must be materialized before conversion; this file alone is incomplete')
                    native=payload['id'];cwd=payload.get('cwd','');timestamp=payload.get('timestamp',timestamp)
                elif kind=='response_item':
                    if payload.get('type')=='message':messages.append({'role':payload.get('role','user'),'content':text(payload.get('content',[]))})
                    elif payload.get('type') in ('function_call','function_call_output','custom_tool_call','custom_tool_call_output'):
                        messages.append({'role':'assistant','content':'[Source tool history] '+json.dumps(payload,ensure_ascii=False)})
                elif kind=='compacted' and payload.get('message'):
                    # Compaction replaces earlier context; do not replay superseded history.
                    replacement=payload.get('replacement_history')
                    if isinstance(replacement,list) and replacement:
                        header={'type':'session_meta','payload':{'id':native,'cwd':cwd}}
                        messages=decode('codex',[header]+[{'type':'response_item','payload':item} for item in replacement])['messages']
                    else:messages=[{'role':'user','content':'[Source compaction summary]\n'+payload['message']}]
            elif engine=='claude':
                native=row.get('sessionId',native);cwd=row.get('cwd',cwd)
                if kind in ('user','assistant') and isinstance(row.get('message'),dict):
                    message=row['message'];messages.append({'role':message.get('role',kind),'content':text(message.get('content',[]))})
            elif engine=='omp':
                if kind=='session':native=row['id'];cwd=row.get('cwd','');title=row.get('title','');timestamp=row.get('timestamp',timestamp)
                elif kind=='message':
                    message=row['message'];role=message.get('role','assistant')
                    messages.append({'role':role if role in ('user','assistant') else 'assistant','content':text(message.get('content',[]))})
                elif kind=='compaction':
                    summary={'role':'user','content':'[Source compaction summary]\n'+row.get('summary','')}
                    kept=[];keep=False
                    for entry in entries:
                        if entry is row:break
                        if entry.get('id')==row.get('firstKeptEntryId'):keep=True
                        if keep and entry.get('type')=='message':
                            message=entry['message'];role=message.get('role','assistant')
                            kept.append({'role':role if role in ('user','assistant') else 'assistant','content':text(message.get('content',[]))})
                    messages=[summary]+kept
                elif kind=='branch_summary' and row.get('summary'):
                    messages.append({'role':'user','content':'[Source branch summary]\n'+row['summary']})
                elif kind=='custom_message' and row.get('content'):
                    messages.append({'role':'user','content':'[Source context]\n'+text(row['content'])})
    if not native:raise ValueError('Native session identity not found')
    messages=[m for m in messages if m['content']]
    if not messages:raise ValueError('No portable conversation content found')
    title=title or next((m['content'][:100].replace('\n',' ') for m in messages if m['role']=='user'),'Imported session')
    return {'format':'codelaboon.session.v1','id':uuid.uuid4().hex,'title':title,'cwd':cwd,'created_at':timestamp,
            'messages':messages,'origin':{'engine':engine,'native_id':native,'source':str(source)},'archive':value}


@contextmanager
def library():
    root=data_dir()/'session-library';root.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=root/'sessions.sqlite3'
    descriptor=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(descriptor)
    with closing(sqlite3.connect(path,timeout=15)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, cwd TEXT, updated TEXT, document BLOB)')
        db.execute('CREATE TABLE IF NOT EXISTS snapshots (session_id TEXT, engine TEXT, source TEXT, native_id TEXT, archive BLOB, PRIMARY KEY(engine,source,native_id))')
        db.execute('CREATE TABLE IF NOT EXISTS sources (path TEXT PRIMARY KEY, stamp TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS bindings (engine TEXT, source TEXT, native_id TEXT, session_id TEXT, fingerprint TEXT, PRIMARY KEY(engine,source,native_id))')
        db.execute('BEGIN IMMEDIATE')
        yield db


def save(document,identity=None):
    origin=document['origin'];fingerprint=hashlib.sha256(json.dumps(document.get('archive'),sort_keys=True).encode()).hexdigest()
    with library() as db:
        existing=db.execute('SELECT session_id,fingerprint FROM bindings WHERE engine=? AND source=? AND native_id=?',
                            (origin['engine'],origin['source'],origin['native_id'])).fetchone()
        if existing and existing[1]==fingerprint:return existing[0]
        document=dict(document,id=identity or (existing[0] if existing else document['id']))
        prior=db.execute('SELECT document FROM sessions WHERE id=?',(document['id'],)).fetchone()
        if prior:
            metadata=json.loads(zlib.decompress(prior[0]))
            document.update(title=metadata['title'],created_at=metadata['created_at'])
        db.execute('INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)',(document['id'],origin['engine'],origin['source'],origin['native_id'],zlib.compress(json.dumps(document.get('archive'),ensure_ascii=False).encode())))
        document.pop('archive',None)
        db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?)',(document['id'],document['title'],document['cwd'],now(),zlib.compress(json.dumps(document,ensure_ascii=False).encode())))
        db.execute('INSERT OR REPLACE INTO bindings VALUES (?,?,?,?,?)',(origin['engine'],origin['source'],origin['native_id'],document['id'],fingerprint))
    return document['id']


def load(identity):
    with library() as db:row=db.execute('SELECT document FROM sessions WHERE id=?',(identity,)).fetchone()
    if not row:raise ValueError('Unknown universal session ID')
    return json.loads(zlib.decompress(row[0]))


def native_home(engine,private=False):
    if engine=='jcode':
        return data_dir()/'jcode/projects'/hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:20] if private else Path(os.environ.get('JCODE_HOME') or Path.home()/'.jcode')
    if engine=='crush':
        return config_dir()/'crush/projects'/hashlib.sha256(str(Path.cwd().resolve()).encode()).hexdigest()[:16] if private else Path.cwd()/'.crush'
    if private:
        return {'codex':config_dir()/'codex','claude':config_dir()/'claude-code','omp':config_dir()/'omp',
                'opencode':config_dir()/'native/data/opencode','kilo':config_dir()/'kilo/data/kilo'}[engine]
    return {'codex':Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex'),
            'claude':Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home()/'.claude'),
            'omp':Path(os.environ.get('PI_CODING_AGENT_DIR') or Path.home()/'.omp/agent'),
            'opencode':Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'opencode',
            'kilo':Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'kilo'}[engine]


def from_database(engine,path,identity=None):
    # Read via a separate read-only SQLite connection; never write another agent's DB.
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=3)) as db:
        if engine=='crush':
            db.row_factory=sqlite3.Row
            for row in db.execute('SELECT * FROM sessions'+(' WHERE id=?' if identity else ''),(identity,) if identity else ()):
                messages=[dict(m) for m in db.execute('SELECT * FROM messages WHERE session_id=? ORDER BY created_at,rowid',(row['id'],))]
                if messages:
                    metadata=path.parent/'.codelaboon-project.json'
                    cwd=json.loads(metadata.read_text()).get('cwd','') if metadata.exists() else (str(path.parent.parent) if path.parent.name=='.crush' else '')
                    yield decode(engine,{'session':dict(row),'messages':messages,'cwd':cwd},path)
            return
        query='SELECT id, project_id, directory, title, version, time_created, time_updated FROM session'
        args=()
        if identity:query+=' WHERE id=?';args=(identity,)
        for row in db.execute(query,args):
            sid,project,cwd,title,version,created,updated=row
            info={'id':sid,'projectID':project,'directory':cwd,'title':title,'version':version,'time':{'created':created,'updated':updated}}
            messages=[]
            for mid,raw in db.execute('SELECT id,data FROM message WHERE session_id=? ORDER BY time_created,id',(sid,)):
                message=json.loads(raw);message.update(id=mid,sessionID=sid)
                parts=[]
                for pid,rawpart in db.execute('SELECT id,data FROM part WHERE message_id=? ORDER BY time_created,id',(mid,)):
                    part=json.loads(rawpart);part.update(id=pid,sessionID=sid,messageID=mid);parts.append(part)
                messages.append({'info':message,'parts':parts})
            if messages:
                try:yield decode(engine,{'info':info,'messages':messages},path)
                except ValueError:continue


def read_source(engine,source,home=None):
    path=Path(source).expanduser()
    if path.is_file():return decode(engine,codex_history(path) if engine=='codex' else read_file(path),path.resolve())
    # IDs are matched as identities, never interpolated into path patterns or SQL.
    root=Path(home).expanduser() if home else native_home(engine)
    if engine=='codex':
        # Reverted threads keep their UUID but can select a different rollout.
        # Prefer the native index over guessing from an old matching filename.
        for index in root.glob('state_*.sqlite'):
            try:
                with closing(sqlite3.connect(index.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                    active=db.execute('SELECT rollout_path FROM threads WHERE id=?',(source,)).fetchone()
                if active and Path(active[0]).is_file():
                    document=decode(engine,codex_history(active[0]),Path(active[0]).resolve())
                    if document['origin']['native_id']==source:return document
            except sqlite3.Error:continue
    if engine in ('opencode','kilo','crush'):
        for db in root.glob('*.db'):
            found=list(from_database(engine,db,source))
            if found:return found[0]
    else:
        pattern={'codex':'sessions/**/*.jsonl','claude':'projects/*/*.jsonl','omp':'sessions/**/*.jsonl','jcode':'sessions/*.json'}[engine]
        for candidate in root.glob(pattern):
            if source not in candidate.name:continue
            document=decode(engine,codex_history(candidate) if engine=='codex' else read_file(candidate),candidate.resolve())
            if document['origin']['native_id']==source:return document
    raise ValueError('Session not found. Pass an exported file, or --home with the original engine data directory.')


def portable_messages(document):
    # Historical tool records become text. Never present foreign calls as pending
    # tools, copy permission grants, or install source system instructions as policy.
    for message in document['messages']:
        role=message['role'];content=message['content']
        if role not in ('user','assistant'):content='[Historical '+role+' instructions]\n'+content;role='user'
        yield {'role':role,'content':content}


def encode(document,engine,cwd=None,model=None):
    identity=str(uuid.uuid4());stamp=now();cwd=str(Path(cwd or document.get('cwd') or Path.cwd()).expanduser().resolve())
    provider,_,model_id=(model or 'historical/imported-context').partition('/')
    messages=list(portable_messages(document));ms=int(datetime.now(timezone.utc).timestamp()*1000)
    if engine=='jcode':
        return identity,{'id':identity,'parent_id':None,'title':document['title'],'created_at':stamp,'updated_at':stamp,
                         'working_dir':cwd,'messages':[{'id':str(uuid.uuid4()),'role':m['role'],'content':[{'type':'text','text':m['content']}],'timestamp':stamp} for m in messages],
                         **({'provider_key':provider,'model':model_id} if model else {})}
    if engine=='crush':
        return identity,{'session':{'id':identity,'title':document['title'],'created_at':int(ms/1000),'updated_at':int(ms/1000)},'cwd':cwd,
                         'messages':[{'id':str(uuid.uuid4()),'session_id':identity,'role':m['role'],'parts':json.dumps([{'type':'text','data':{'text':m['content']}}]),
                                      'created_at':int(ms/1000)-len(messages)+index,'updated_at':int(ms/1000)-len(messages)+index,'finished_at':int(ms/1000)-len(messages)+index} for index,m in enumerate(messages)]}
    if engine in ('opencode','kilo'):
        identity='ses_'+secrets.token_hex(13);rows=[];parent=None
        for index,message in enumerate(messages):
            mid='msg_'+f'{ms+index:013x}'+secrets.token_hex(6)
            info={'id':mid,'sessionID':identity,'role':message['role'],'time':{'created':ms-len(messages)+index},'agent':'build'}
            if message['role']=='user':info['model']={'providerID':provider,'modelID':model_id};parent=mid
            else:
                if parent is None:
                    # A destination assistant requires a user parent.
                    user={'role':'user','content':'Continue this imported historical conversation.'}
                    parent='msg_'+secrets.token_hex(13)
                    rows.append({'info':{'id':parent,'sessionID':identity,'role':'user','time':{'created':ms},'agent':'build','model':{'providerID':provider,'modelID':model_id}},'parts':[{'id':'prt_'+secrets.token_hex(13),'sessionID':identity,'messageID':parent,'type':'text','text':user['content']}]})
                info.update(parentID=parent,modelID=model_id,providerID=provider,mode='build',path={'cwd':cwd,'root':cwd},cost=0,
                            tokens={'input':0,'output':0,'reasoning':0,'cache':{'read':0,'write':0}},finish='stop')
            rows.append({'info':info,'parts':[{'id':'prt_'+secrets.token_hex(13),'sessionID':identity,'messageID':mid,'type':'text','text':message['content']}]})
        return identity,{'info':{'id':identity,'slug':'imported-'+identity[-8:],'projectID':'global','directory':cwd,'title':document['title'],'version':'1.0.0','time':{'created':ms,'updated':ms}},'messages':rows}
    if engine=='codex':
        rows=[{'timestamp':stamp,'type':'session_meta','payload':{'id':identity,'session_id':identity,'timestamp':stamp,'cwd':cwd,
              'originator':'codex_cli_rs','cli_version':'0.169.0','source':'cli','model_provider':provider if model else 'openai',
              'base_instructions':{'text':'You are a coding agent. Continue the historical conversation using your own tools and permissions.'}}}]
        rows.extend({'timestamp':stamp,'type':'response_item','payload':{'type':'message','role':m['role'],
                     'content':[{'type':'output_text' if m['role']=='assistant' else 'input_text','text':m['content']}]}} for m in messages)
    elif engine=='omp':
        rows=[{'type':'session','version':3,'id':identity,'timestamp':stamp,'cwd':cwd,'title':document['title']}];parent=None
        for m in messages:
            entry={'type':'message','id':secrets.token_hex(8),'parentId':parent,'timestamp':stamp,'message':{
                'role':m['role'],'content':[{'type':'text','text':m['content']}],'timestamp':ms}}
            if m['role']=='assistant':entry['message'].update(api='openai-completions',provider='codelaboon',model='free',stopReason='stop',usage={'input':0,'output':0,'cacheRead':0,'cacheWrite':0,'totalTokens':0,'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0,'total':0}})
            parent=entry['id'];rows.append(entry)
    elif engine=='claude':
        rows=[];parent=None
        for m in messages:
            uid=str(uuid.uuid4());message={'role':m['role'],'content':[{'type':'text','text':m['content']}]}
            if m['role']=='assistant':message.update(id='msg_'+secrets.token_hex(8),type='message',model='free',stop_reason='end_turn',usage={'input_tokens':0,'output_tokens':0})
            rows.append({'type':m['role'],'uuid':uid,'parentUuid':parent,'sessionId':identity,'cwd':cwd,'timestamp':stamp,'version':'2.1.325','isSidechain':False,'userType':'external','message':message});parent=uid
    else:raise ValueError('Unsupported native destination')
    return identity,rows


def write_export(path,value):
    path=Path(path).expanduser().resolve();path.parent.mkdir(parents=True,exist_ok=True)
    # Refuse collisions rather than clobber an existing native session/export.
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        if isinstance(value,list):
            for row in value:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        else:json.dump(value,stream,ensure_ascii=False)
    return path


def install_export(engine,value,identity,home,cwd):
    home=Path(home).expanduser().resolve()
    if engine in ('opencode','kilo'):raise ValueError('Use the native '+engine+' import command to install this export')
    if engine=='crush':
        # The destination's own migrations finish initializing a fresh database.
        # Existing databases receive only new session/message rows in one transaction.
        home.mkdir(parents=True,exist_ok=True);path=home/'crush.db'
        fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
        with closing(sqlite3.connect(path,timeout=10)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY,parent_session_id TEXT,title TEXT NOT NULL,message_count INTEGER NOT NULL DEFAULT 0,prompt_tokens INTEGER NOT NULL DEFAULT 0,completion_tokens INTEGER NOT NULL DEFAULT 0,cost REAL NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL,created_at INTEGER NOT NULL)')
            db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,parts TEXT NOT NULL DEFAULT '[]',model TEXT,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,finished_at INTEGER)")
            row=value['session'];db.execute('INSERT INTO sessions (id,title,created_at,updated_at) VALUES (?,?,?,?)',(row['id'],row['title'],row['created_at'],row['updated_at']))
            for row in value['messages']:
                keys=('id','session_id','role','parts','created_at','updated_at','finished_at')
                db.execute('INSERT INTO messages ('+','.join(keys)+') VALUES (?,?,?,?,?,?,?)',tuple(row[k] for k in keys))
            db.execute('UPDATE sessions SET message_count=(SELECT count(*) FROM messages WHERE session_id=?) WHERE id=?',(identity,identity))
        return path
    if engine=='jcode':relative=Path('sessions')/(identity+'.json')
    elif engine=='codex':relative=Path('sessions')/datetime.now().strftime('%Y/%m/%d')/('rollout-'+now().replace(':','-')+'-'+identity+'.jsonl')
    elif engine=='claude':relative=Path('projects')/re.sub(r'[^A-Za-z0-9]','-',str(Path(cwd).resolve()))/(identity+'.jsonl')
    else:
        # Match OMP's legacy absolute session directory format on both platforms.
        project = re.sub(r'[/\\:]', '-', re.sub(r'^[/\\]', '', str(Path(cwd).resolve())))
        filename = now().replace(':', '-').replace('.', '-') + '_' + identity + '.jsonl'
        relative = Path('sessions') / f'--{project}--' / filename
    return write_export(home/relative,value)


def sync_private():
    """Index changed Codelaboon profiles; independent homes remain opt-in."""
    count=0
    for engine in ENGINES:
        root=data_dir()/'jcode' if engine=='jcode' else (config_dir()/'crush/projects' if engine=='crush' else native_home(engine,True))
        if not root.exists():continue
        pattern='**/sessions/*.json' if engine=='jcode' else ('**/crush.db' if engine=='crush' else '*.db'  if engine in ('opencode','kilo') else ('projects/*/*.jsonl' if engine=='claude' else 'sessions/**/*.jsonl'))
        for path in root.glob(pattern):
            try:
                def signature():
                    result=[]
                    for candidate in (path,Path(str(path)+'-wal')):
                        try:stat=candidate.stat();result.append((stat.st_ino,stat.st_mtime_ns,stat.st_size))
                        except FileNotFoundError:result.append(None)
                    return json.dumps(result)
                stamp=signature()
                with library() as db:previous=db.execute('SELECT stamp FROM sources WHERE path=?',(str(path.resolve()),)).fetchone()
                if previous and previous[0]==stamp:continue
                if engine in ('opencode','kilo','crush'):
                    documents=from_database(engine,path)
                else:documents=[read_source(engine,str(path))]
                for document in documents:save(document);count+=1
                # Never cache a scan if the native process appended during reading.
                if signature()==stamp:
                    with library() as db:db.execute('INSERT OR REPLACE INTO sources VALUES (?,?)',(str(path.resolve()),stamp))
            except (OSError,sqlite3.Error,ValueError,KeyError,TypeError):continue
    return count


def bind(identity,engine,path,native):
    with library() as db:
        source=str(Path(path).resolve())
        existing=db.execute('SELECT session_id FROM bindings WHERE engine=? AND source=? AND native_id=?',(engine,source,native)).fetchone()
        db.execute('INSERT OR REPLACE INTO bindings VALUES (?,?,?,?,?)',(engine,source,native,identity,''))
        db.execute('UPDATE snapshots SET session_id=? WHERE engine=? AND source=? AND native_id=?',(identity,engine,source,native))
        if existing and existing[0]!=identity and not db.execute('SELECT 1 FROM bindings WHERE session_id=?',(existing[0],)).fetchone():
            db.execute('DELETE FROM sessions WHERE id=?',(existing[0],))


def resume(identity,engine,prompt=None,directory=None,model="free"):
    document=load(identity);cwd=Path(directory or document.get('cwd') or Path.cwd()).expanduser().resolve()
    if not cwd.is_dir():raise ValueError('Original project is absent. Export with --cwd to select another project.')
    native,value=encode(document,engine,str(cwd),'codelaboon/'+model)
    previous=Path.cwd()
    from codelaboon.native_tui import launch
    try:
        os.chdir(cwd)
        if engine in ('opencode','kilo'):
            with tempfile.TemporaryDirectory(prefix='codelaboon-session-') as temporary:
                export=write_export(Path(temporary)/'session.json',value)
                result=launch(engine,['import',str(export)])
                if result:raise ValueError('Native session import failed')
            # The importer chooses this project's DB; bind its generated identity
            # before launching so subsequent sync updates the same universal ID.
            databases=list(native_home(engine,True).glob('*.db'))
            target=next((p for p in databases if list(from_database(engine,p,native))),None)
            if target is None:raise ValueError('Native import did not create a readable session')
            bind(identity,engine,target,native)
            args=['--session',native,'--model','codelaboon/'+model]
            return launch(engine,['run',*args,prompt] if prompt is not None else args)
        target=install_export(engine,value,native,native_home(engine,True),str(cwd));bind(identity,engine,target,native)
        args={'codex':['resume',native],'claude':['--resume',native],'omp':['--session',str(target)],'jcode':['--resume',native],'crush':['--session',native]}[engine]
        if prompt is not None:
            args={'codex':['exec','--skip-git-repo-check','resume',native,prompt],
                  'claude':['--resume',native,'-p',prompt],'omp':['--session',str(target),'-p',prompt],
                  'jcode':['--resume',native,'run',prompt],'crush':['run','--session',native,prompt]}[engine]
        return launch(engine,args)
    finally:
        os.chdir(previous)
        sync_private()


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    listing=sub.add_parser('list');listing.add_argument('--json',action='store_true');sub.add_parser('sync')
    res=sub.add_parser('resume');res.add_argument('id');res.add_argument('--engine',choices=ENGINES,default='opencode');res.add_argument('--prompt',help='Run a single continuation headlessly');res.add_argument('--cwd',help='Continue in another project directory')
    imp=sub.add_parser('import');imp.add_argument('--engine',choices=ENGINES,required=True);imp.add_argument('--source',required=True);imp.add_argument('--home')
    export=sub.add_parser('export');export.add_argument('id');export.add_argument('--engine',choices=ENGINES,required=True)
    convert=sub.add_parser('convert');convert.add_argument('--from',dest='source_engine',choices=ENGINES,required=True);convert.add_argument('--source',required=True);convert.add_argument('--home');convert.add_argument('--to',dest='engine',choices=ENGINES,required=True)
    for cmd in (export,convert):
        cmd.add_argument('--output',required=True);cmd.add_argument('--cwd');cmd.add_argument('--install',action='store_true');cmd.add_argument('--target-home');cmd.add_argument('--model',help='Destination provider/model for native OpenCode/Kilo')
    args=parser.parse_args(arguments)
    try:
        if args.action=='resume':raise SystemExit(resume(args.id,args.engine,args.prompt,args.cwd))
        if args.action=='sync':print('Indexed',sync_private(),'native sessions');return
        if args.action=='list':
            sync_private()
            with library() as db:
                rows=[{'id':row[0],'title':row[1],'cwd':row[2]} for row in db.execute('SELECT id,title,cwd FROM sessions ORDER BY updated DESC')]
            if args.json:print(json.dumps(rows,ensure_ascii=False))
            else:
                for row in rows:print('\t'.join(str(row[key]).replace('\n',' ').replace('\t',' ') for key in ('id','title','cwd')))
            return
        if args.action=='import':print(save(read_source(args.engine,args.source,args.home)));return
        document=load(args.id) if args.action=='export' else read_source(args.source_engine,args.source,args.home)
        identity,value=encode(document,args.engine,args.cwd,args.model)
        path=write_export(args.output,value)
        print('Export:',path,'\nNative ID:',identity)
        if args.install:
            installed=install_export(args.engine,value,identity,args.target_home or native_home(args.engine),args.cwd or document['cwd'])
            print('Installed:',installed)
        if args.engine in ('opencode','kilo'):print('Next:',args.engine,'import',str(path),'\nThen:',args.engine,'--session',identity,'--model',args.model or '<your-provider/model>')
        elif args.engine=='codex':print('Next: codex resume',identity,'(after --install into the Codex home)')
        elif args.engine=='claude':print('Next: claude --resume',identity,'(after --install into the Claude home)')
        elif args.engine=='omp':print('Next: omp --session',str(path))
        elif args.engine=='jcode':print('Next: jcode --resume',identity,'(after --install into the Jcode home)')
        else:print('Next: crush --session',identity,'(after --install into the project Crush data directory)')
    except (OSError,ValueError,KeyError,sqlite3.Error) as error:parser.exit(1,'Session transfer: '+str(error)+'\n')
