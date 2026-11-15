"""Focused native Codex CLI and editor app-server inference checks."""
import json
import os
import subprocess
import sys
from native_fixture import ROOT,REPLY,MARKER,fixture

def respond(body,project):
    found=any(message.get('role')=='tool' and MARKER in str(message.get('content')) for message in body.get('messages',[]))
    if found:return {'role':'assistant','content':REPLY},'stop'
    tools=body.get('tools',[])
    tool=next((tool['function']['name'] for tool in tools if tool['function']['name'].endswith('exec_command')),None)
    if not tool:raise AssertionError('Native Codex shell tool missing: '+str([t['function']['name'] for t in tools]))
    return {'role':'assistant','content':None,'tool_calls':[{'id':'codex_read','type':'function','function':{
        'name':tool,'arguments':json.dumps({'cmd':'cat marker.txt','max_output_tokens':1000})}}]},'tool_calls'

with fixture('codex',responder=respond) as (project,env,observed):
    command=[sys.executable,str(ROOT/'codelaboon/cli.py'),'codex','exec','--skip-git-repo-check','--json','Read marker.txt using the shell, then reply briefly.']
    result=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=90)
    (ROOT/'.runtime/codex-smoke.log').write_text(result.stdout+'\n'+result.stderr)
    assert result.returncode==0,result.stderr[-2500:]+result.stdout[-2500:]
    assert REPLY in result.stdout,result.stdout[-2500:]
    assert any(m.get('role')=='tool' and MARKER in str(m.get('content')) for b in observed for m in b.get('messages',[])), 'No real shell tool result'
    print('PASS: native Codex exec uses Codelaboon without OpenAI login')
