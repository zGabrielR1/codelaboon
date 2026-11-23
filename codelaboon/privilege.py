"""Expiring, explicitly approved root/administrator execution cases."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import time

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codelaboon.paths import config_dir


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_hash(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def store():
    root=config_dir()/'privilege-cases';root.mkdir(parents=True,exist_ok=True,mode=0o700);return root


def create(argv,scope,cwd=None,ttl=300,timeout=1800,payload=None):
    if not scope.strip() or not 1<=ttl<=86400 or not 1<=timeout<=86400:raise ValueError('Provide scope and bounded expiry/timeout')
    if not isinstance(argv,list) or not argv or any(not isinstance(v,str) or '\0' in v for v in argv):raise ValueError('Provide an exact argv array')
    program=shutil.which(argv[0]) or argv[0];program=Path(program).resolve(strict=True)
    if not program.is_file():raise ValueError('Executable is not a file')
    if os.name=='nt' and program.suffix.lower()!='.exe':raise ValueError('Windows elevated cases require a native .exe executable')
    cwd=str(Path(cwd or Path.cwd()).resolve(strict=True))
    environment={key:str(value) for key,value in os.environ.items() if key in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','LANG','LC_ALL')}
    environment.update(CODELABOON_CONFIG_DIR=str(config_dir().resolve()))
    # Only explicitly selected Codelaboon paths are carried to an elevated worker.
    for key in ('CODELABOON_CACHE_DIR','CODELABOON_DATA_DIR'):
        if os.environ.get(key):environment[key]=os.environ[key]
    case={'format':1,'nonce':secrets.token_hex(16),'created':time.time(),'expires':time.time()+ttl,
          'timeout':timeout,'scope':scope.strip(),'cwd':cwd,'argv':[str(program),*argv[1:]],
          'program_sha256':file_hash(program),'environment':environment,'platform':platform.system(),
          'owner_uid':os.getuid() if hasattr(os,'getuid') else None,'owner_gid':os.getgid() if hasattr(os,'getgid') else None}
    if payload is not None:
        case['worker']=payload;case['entry']=str(Path(__file__).resolve());case['entry_sha256']=file_hash(__file__)
        # Root's isolated interpreter uses the reviewed installed package and its
        # installed dependencies. This is a real privilege grant, not a sandbox.
        case['python_paths']=[str(Path(p).resolve()) for p in sys.path if p and Path(p).is_dir()]
    identity=digest(case);path=store()/(identity+'.json')
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:json.dump(case,stream)
    return identity,path


def load(path,identity):
    path=Path(path).resolve();raw=path.read_bytes()
    if len(raw)>2*1024*1024:raise ValueError('Privilege case exceeds bounds')
    case=json.loads(raw)
    if digest(case)!=identity:raise ValueError('Case changed since approval')
    if case.get('format')!=1 or case.get('platform')!=platform.system():raise ValueError('Case platform/format mismatch')
    if not isinstance(case.get('scope'),str) or not case['scope'].strip() or not 1<=case.get('timeout',0)<=86400:raise ValueError('Invalid case scope/timeout')
    if not isinstance(case.get('argv'),list) or not case['argv'] or any(not isinstance(v,str) or '\0' in v for v in case['argv']):raise ValueError('Invalid case argv')
    if not isinstance(case.get('expires'),(int,float)) or case['expires']<time.time():raise ValueError('Privilege case expired')
    if file_hash(case['argv'][0])!=case['program_sha256']:raise ValueError('Case executable changed')
    if case.get('worker') and file_hash(case['entry'])!=case['entry_sha256']:raise ValueError('Worker entry changed')
    return path,case


def is_admin():
    if os.name=='nt':
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    return os.geteuid()==0


# Isolated stdlib bootstrap: read once, validate approved data and executable,
# claim once, then execute the exact command. No shell interpolation on POSIX.
BOOTSTRAP=r'''
import base64,hashlib,json,os,pathlib,signal,subprocess,sys,time,ctypes
path=pathlib.Path(sys.argv[1]).resolve();expected=sys.argv[2]
raw=path.read_bytes();case=json.loads(raw)
actual=hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':')).encode()).hexdigest()
if actual!=expected or case['expires']<time.time():raise SystemExit('Changed or expired privilege case')
admin=bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name=='nt' else os.geteuid()==0
if not admin:raise SystemExit('Native administrator/root authorization was not granted')
def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
if sha(case['argv'][0])!=case['program_sha256']:raise SystemExit('Executable changed')
if case.get('worker') and sha(case['entry'])!=case['entry_sha256']:raise SystemExit('Worker entry changed')
claim=path.with_suffix('.used');fd=os.open(claim,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
if os.name!='nt':os.fchown(fd,case['owner_uid'],case['owner_gid'])
os.close(fd)
argv=case['argv'];environment=case['environment']
if case.get('worker'):
 environment=dict(environment,PYTHONPATH=os.pathsep.join(case['python_paths']))
 argv=[case['argv'][0],case['entry'],'_worker',str(path),expected]
started=time.time();code=1
try:
 p=subprocess.Popen(argv,cwd=case['cwd'],env=environment,start_new_session=os.name!='nt')
 try:code=p.wait(timeout=case['timeout'])
 except subprocess.TimeoutExpired:
  if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
  else:
   try:os.killpg(p.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:
    try:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
  p.wait();code=124
finally:
 receipt=path.with_suffix('.result.json')
 with os.fdopen(os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:
  json.dump({'case':expected,'exit_code':code,'started':started,'finished':time.time(),'privileged':True},out)
  if os.name!='nt':os.fchown(out.fileno(),case['owner_uid'],case['owner_gid'])
raise SystemExit(code)
'''


def elevation_command(path,identity,system=None):
    system=system or platform.system();argv=[sys.executable,'-I','-c',BOOTSTRAP,str(Path(path).resolve()),identity]
    if system in ('Linux','Darwin'):return ['sudo','-k','--',*argv]
    if system=='Windows':
        def quote(value):return "'"+value.replace("'","''")+"'"
        args=subprocess.list2cmdline(argv[1:])
        script="$ErrorActionPreference='Stop';$p=Start-Process -FilePath "+quote(argv[0])+" -ArgumentList "+quote(args)+" -Verb RunAs -Wait -PassThru;exit $p.ExitCode"
        return ['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()]
    raise ValueError('Native elevation is supported on Linux, macOS and Windows')


def run_case(path,identity,dry_run=False):
    path,case=load(path,identity)
    if path.with_suffix('.used').exists():raise ValueError('Privilege case was already consumed')
    command=elevation_command(path,identity)
    if dry_run:return {'case':identity,'scope':case['scope'],'argv':case['argv'],'cwd':case['cwd'],'expires':case['expires'],'mechanism':'UAC' if os.name=='nt' else 'sudo','worker':bool(case.get('worker'))}
    if not sys.stdin.isatty():raise ValueError('Approve privileged cases from an interactive terminal; background workers cannot self-approve')
    try:return subprocess.call(command)
    finally:
        if os.name!='nt':subprocess.run(['sudo','-k'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)


def worker_case(task_id,config=None,ttl=300,timeout=1800):
    from codelaboon.work import configuration
    from codelaboon.work_queue import controls, task_index
    path,value,runtime=configuration(config)
    task = task_index(value.get('tasks', []), runtime).get(task_id)
    if not task or task.get('elevation') not in ('root','administrator'):raise ValueError('Queue an explicitly elevated task first')
    state_path=runtime/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {}
    directory=controls(runtime,task_id)
    if task_id in state.get('done',[]) or any((runtime/name).exists() or (directory/name).exists() for name in ('PAUSE','STOP')):raise ValueError('Completed, paused or stopped tasks cannot create privilege cases')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    config_snapshot={k:value[k] for k in ('orchestrator','harnesses','local_executable','local_model','local_context') if k in value}
    payload={'task':task,'task_sha256':digest(task),'configuration':config_snapshot,'receipt_directory':str(directory.resolve())}
    return create([sys.executable],task['scope'],task['project'],ttl,timeout,payload)


def elevated_worker(path,identity):
    path,case=load(path,identity)
    if not is_admin():raise ValueError('Privileged worker requires native root/administrator authorization')
    from codelaboon.watch import run,save
    payload=case['worker'];task=dict(payload['task']);task.pop('elevation',None)
    task['_privileged_case']=True
    if task.get('swarm'):task['swarm']=dict(task['swarm'],cycles=1)
    runtime=path.parent/(identity+'-runtime');runtime.mkdir(mode=0o700)
    from contextlib import nullcontext
    from codelaboon.local_runtime import session
    context=session(payload['configuration']) if payload['configuration'].get('orchestrator') else nullcontext(None)
    with context as controller:
        configuration=dict(payload['configuration'],runtime=str(runtime),tasks=[task],poll_seconds=1)
        if controller:configuration['orchestrator']=controller
        config_path=runtime/'approved-work.json';save(config_path,configuration)
        os.environ.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=case['cwd'])
        outcome=1
        for _ in range(4):
            run(config_path,once=True)
            state=json.loads((runtime/'state.json').read_text()) if (runtime/'state.json').exists() else {}
            if task['id'] in state.get('done',[]):outcome=0;break
            if (runtime/'task-controls').exists() and any((runtime/'task-controls').glob('*/PAUSE')):break
    receipt=Path(payload['receipt_directory'])/('privileged-'+identity+'.json')
    result={'case':identity,'task':task['id'],'task_sha256':payload['task_sha256'],'exit_code':outcome,'finished':time.time()}
    with os.fdopen(os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:
        json.dump(result,stream)
        if os.name!='nt':os.fchown(stream.fileno(),case['owner_uid'],case['owner_gid'])
    return outcome


def main(arguments=None):
    args=sys.argv[1:] if arguments is None else arguments
    if args[:1]==['_worker']:raise SystemExit(elevated_worker(args[1],args[2]))
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('list').add_argument('--json',action='store_true')
    create_cmd=commands.add_parser('create');create_cmd.add_argument('--argv-json',required=True);create_cmd.add_argument('--scope',required=True);create_cmd.add_argument('--cwd');create_cmd.add_argument('--ttl',type=int,default=300);create_cmd.add_argument('--timeout',type=int,default=1800)
    task=commands.add_parser('worker-case');task.add_argument('task_id');task.add_argument('--config');task.add_argument('--ttl',type=int,default=300);task.add_argument('--timeout',type=int,default=1800)
    execute=commands.add_parser('run');execute.add_argument('file');execute.add_argument('--approve',required=True);execute.add_argument('--dry-run',action='store_true')
    options=parser.parse_args(args)
    try:
        if options.action=='list':
            rows=[]
            for path in store().glob('*.json'):
                if path.name.endswith('.result.json'):continue
                try:
                    value=json.loads(path.read_text());identity=digest(value)
                    rows.append({'id':identity,'file':str(path),'scope':value['scope'],'argv':value['argv'],'expires':value['expires'],'used':path.with_suffix('.used').exists(),'expired':value['expires']<time.time()})
                except (OSError,ValueError,KeyError):continue
            print(json.dumps(rows,indent=2) if options.json else '\n'.join(row['id']+' '+row['scope'] for row in rows));return
        if options.action=='create':identity,path=create(json.loads(options.argv_json),options.scope,options.cwd,options.ttl,options.timeout)
        elif options.action=='worker-case':identity,path=worker_case(options.task_id,options.config,options.ttl,options.timeout)
        else:
            result=run_case(options.file,options.approve,options.dry_run)
            if isinstance(result,dict):print(json.dumps(result,indent=2));return
            raise SystemExit(result)
        print(json.dumps({'case':identity,'file':str(path),'scope':json.loads(path.read_text())['scope'],'approval':'Review this case, then privilege run FILE --approve CASE_ID. Native OS authentication is required.'},indent=2))
    except (OSError,ValueError,KeyError,TypeError) as error:parser.exit(1,'Privilege case: '+str(error)+'\n')


if __name__=='__main__':
    if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    main()
