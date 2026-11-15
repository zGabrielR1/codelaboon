"""Native full-access and security-profile propagation using disposable local tools."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
from native_fixture import ROOT,fixture

MARKER='POLICY_FIXTURE_ONLY'
for engine in ('codex','jcode'):
    def respond(body,project):
        assert 'authorized pentesting assistant' in json.dumps(body.get('messages',[])),'Security profile absent'
        found=any(message.get('role')=='tool' and MARKER in str(message.get('content')) for message in body['messages'])
        if found:return {'role':'assistant','content':'Verified '+MARKER},'stop'
        name=next(tool['function']['name'] for tool in body.get('tools',[]) if tool['function']['name'].endswith('exec_command') or tool['function']['name']=='bash')
        outside=project.parent/(project.name+'-policy-marker')
        code='from pathlib import Path;p=Path('+repr(str(outside))+');p.write_text('+repr(MARKER)+');print(p.read_text())'
        return {'role':'assistant','content':None,'tool_calls':[{'id':'policy-write','type':'function','function':{'name':name,'arguments':json.dumps({'command' if name=='bash' else 'cmd':shlex.join([sys.executable,'-c',code]),**({} if name=='bash' else {'max_output_tokens':1000})})}}]},'tool_calls'
    with fixture(engine,responder=respond) as (project,env,observed):
        env.update(CODELABOON_WORK_PERMISSIONS='full',CODELABOON_WORK_PROFILE='security',CODELABOON_WORK_TRACE='1')
        args=['exec','--skip-git-repo-check','--json'] if engine=='codex' else ['--model','free','run','--json']
        command=[sys.executable,str(ROOT/'codelaboon/cli.py'),engine,*args,'Scope: disposable local fixture only. Perform the fixture tool check.']
        marker=project.parent/(project.name+'-policy-marker')
        try:
            result=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=120)
            (ROOT/'.runtime'/('worker-policy-'+engine+'.log')).write_text(result.stdout+'\n'+result.stderr)
            assert result.returncode==0,result.stdout[-1500:]+result.stderr[-1500:]
            if engine=='jcode':assert MARKER in json.loads(result.stdout)['text'],'Trace corrupted machine-readable result'
            assert marker.read_text()==MARKER
            assert observed and MARKER in result.stdout
            print('PASS '+engine+': full access writes disposable external marker; security profile reaches model',flush=True)
        finally:marker.unlink(missing_ok=True)
