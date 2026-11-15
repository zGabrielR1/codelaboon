"""Native session import/resume checks with isolated deterministic inference."""
import json
from pathlib import Path
import subprocess
import sys
from native_fixture import ROOT,fixture
sys.path.insert(0,str(ROOT))
from codelaboon.session_transfer import decode,encode,install_export,write_export

NONCE='CROSS_ENGINE_MEMORY_91'
source={'info':{'id':'ses_source','title':'Cross engine memory','directory':''},'messages':[
    {'info':{'role':'user'},'parts':[{'type':'text','text':'Remember '+NONCE}]},
    {'info':{'role':'assistant'},'parts':[{'type':'text','text':'I will remember '+NONCE}]}]}

def respond(body,project):
    serialized=json.dumps(body.get('messages',[]))
    assert NONCE in serialized,'Destination did not load imported history'
    return {'role':'assistant','content':'Resumed '+NONCE},'stop'

for engine in (sys.argv[1:] or ['codex','opencode','kilo','claude','omp','jcode','crush']):
    with fixture(engine,responder=respond) as (project,env,observed):
        source['info']['directory']=str(project)
        document=decode('opencode',source)
        identity,value=encode(document,engine,str(project),'codelaboon/free')
        driver=[sys.executable,str(ROOT/'codelaboon/cli.py')]
        if engine in ('opencode','kilo'):
            output=write_export(project/'transfer.json',value)
            prefix=driver+(['tui','--engine','opencode','--'] if engine=='opencode' else ['kilo'])
            imported=subprocess.run(prefix+['import',str(output)],cwd=project,env=env,capture_output=True,text=True,timeout=180)
            assert imported.returncode==0,imported.stdout[-1500:]+imported.stderr[-1500:]
            command=prefix+['run','--session',identity,'--model','codelaboon/free','Continue the previous conversation.']
        else:
            home=project/'config'/('claude-code' if engine=='claude' else engine)
            if engine=='jcode':
                import hashlib
                home=project/'data/jcode/projects'/hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:20]
            if engine=='crush':
                import hashlib
                home=project/'config/crush/projects'/hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16]
            target=install_export(engine,value,identity,home,str(project))
            if engine=='codex':command=driver+['codex','exec','--skip-git-repo-check','resume',identity,'Continue the previous conversation.']
            elif engine=='claude':command=driver+['claude','--resume',identity,'-p','Continue the previous conversation.']
            elif engine=='jcode':command=driver+['jcode','--resume',identity,'run','Continue the previous conversation.']
            elif engine=='crush':command=driver+['crush','run','--session',identity,'Continue the previous conversation.']
            else:command=driver+['omp','--session',str(target),'-p','Continue the previous conversation.']
        result=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=180)
        log=ROOT/'.runtime'/('session-transfer-'+engine+'.log');log.write_text(result.stdout+'\n'+result.stderr)
        assert result.returncode==0,str(log)+'\n'+result.stdout[-1800:]+result.stderr[-1800:]
        assert observed and NONCE in result.stdout,str(log)+' did not resume'
        print('PASS native '+engine+' resumed historical context',flush=True)
