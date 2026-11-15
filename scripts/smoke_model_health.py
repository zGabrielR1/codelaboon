"""Verify a real model check controls what the subsequent picker may advertise."""
import json
import re
import subprocess
import sys
from native_fixture import ROOT,fixture

failed=[False]


def respond(body,project):
    if failed[0]:return {'role':'assistant','content':'Model did not answer the check'},'stop'
    tool=next((row for row in body.get('messages',[]) if row.get('role')=='tool'),None)
    if tool:return {'role':'assistant','content':tool['content']},'stop'
    nonce=re.search(r'HEALTH_[a-f0-9]+',json.dumps(body['messages'])).group()
    if body.get('tools'):
        return {'role':'assistant','content':None,'tool_calls':[{'id':'health1','type':'function','function':{'name':'health_echo','arguments':json.dumps({'value':nonce})}}]},'tool_calls'
    return {'role':'assistant','content':nonce},'stop'


with fixture('claude',responder=respond) as (project,env,observed):
    env['CODELABOON_MODEL_CHECKS']='1'
    def run(*args):
        return subprocess.run([sys.executable,str(ROOT/'codelaboon/cli.py'),'models',*args],cwd=project,env=env,capture_output=True,text=True,timeout=45)
    checked=run('check','kilo','--force','--require-working','--json')
    assert checked.returncode==0,checked.stderr+checked.stdout
    rows=json.loads(checked.stdout)
    assert rows[0]['status']=='working' and rows[0]['tools'] is True
    listed=run('list','free')
    assert 'kilo/fixture' in listed.stdout,listed.stdout
    failed[0]=True
    checked=run('check','kilo','--force','--require-working','--json')
    assert checked.returncode==1,checked.stdout+checked.stderr
    listed=run('list','free')
    assert 'kilo/fixture' not in listed.stdout,listed.stdout
    print('PASS: real HTTP reply/tool checks admit a model, and a failed recheck removes it from the next picker')
