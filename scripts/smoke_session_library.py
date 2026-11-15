"""Keep one universal ID through native Codex -> OpenCode continuation."""
import json
from pathlib import Path
import subprocess
import sys
from native_fixture import ROOT,fixture
sys.path.insert(0,str(ROOT))
NONCE='CROSS_ENGINE_MEMORY_91'


def respond(body,project):
    assert NONCE in json.dumps(body['messages']),'Prior conversation missing'
    return {'role':'assistant','content':'Still remember '+NONCE},'stop'

with fixture('opencode',responder=respond) as (project,env,observed):
    source=project/'source.json'
    source.write_text(json.dumps({'info':{'id':'ses_original','directory':str(project),'title':'Shared ID'},'messages':[
        {'info':{'role':'user'},'parts':[{'type':'text','text':'Remember '+NONCE}]}]}))
    cli=[sys.executable,str(ROOT/'codelaboon/cli.py'),'sessions']
    result=subprocess.run(cli+['import','--engine','opencode','--source',str(source)],env=env,cwd=project,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    identity=result.stdout.strip()
    for engine in ('codex','opencode'):
        result=subprocess.run(cli+['resume',identity,'--engine',engine,'--prompt','Continue with the saved context.'],env=env,cwd=project,capture_output=True,text=True,timeout=180)
        (ROOT/'.runtime'/('session-library-'+engine+'.log')).write_text(result.stdout+'\n'+result.stderr)
        assert result.returncode==0,result.stdout[-1500:]+result.stderr[-1500:]
        assert NONCE in result.stdout
    import sqlite3
    with sqlite3.connect(project/'data/session-library/sessions.sqlite3') as db:
        assert db.execute('SELECT id FROM sessions').fetchall()==[(identity,)],'Universal ID split/duplicate'
        assert db.execute('SELECT count(*) FROM bindings WHERE session_id=?',(identity,)).fetchone()[0]==3
    print('PASS: one library ID across Codex and OpenCode with original source retained')
