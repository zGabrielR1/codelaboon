"""Harmless real sudo/bootstrap test on disposable POSIX CI runners only."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from codelaboon.privilege import create,elevation_command

if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('This fixture runs only on disposable GitHub Actions runners')
if os.name=='nt':
    # Parse the exact UAC script with the platform parser, without displaying UAC
    # or pretending unattended CI can validate interactive human consent.
    command=elevation_command(Path.cwd()/'fixture.json','a'*64,'Windows')
    script=base64.b64decode(command[-1]).decode('utf-16-le')
    validation='$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseInput('+"'"+script.replace("'","''")+"', [ref]$t,[ref]$e)|Out-Null;if($e.Count){throw $e}"
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(validation.encode('utf-16-le')).decode()],check=True)
else:
    with tempfile.TemporaryDirectory(prefix='codelaboon-privilege-ci-') as directory:
        os.environ['CODELABOON_CONFIG_DIR']=directory
        identity,path=create([sys.executable,'-c','import os;assert os.geteuid()==0;print("privilege fixture only")'],'Read root identity in disposable CI; no machine changes',timeout=10)
        command=elevation_command(path,identity);command=['sudo','-n','--',*command[3:]]
        subprocess.run(command,check=True,timeout=20)
        receipt=json.loads(path.with_suffix('.result.json').read_text());assert receipt['exit_code']==0 and receipt['privileged'] is True
        replay=subprocess.run(command,capture_output=True,timeout=20);assert replay.returncode!=0
        from codelaboon.work import add
        from codelaboon.privilege import worker_case
        from codelaboon.watch import run
        project=Path(directory)/'project';project.mkdir()
        config=Path(directory)/'work.json'
        config.write_text(json.dumps({'runtime':'work-runtime','poll_seconds':1,'harnesses':[{'id':'fixture','argv':['{python}','-c','import os;assert os.geteuid()==0;print("root worker fixture")']}],'tasks':[]}))
        task=add(project,'Run read-only root identity fixture',[[sys.executable,'-c','import os;assert os.geteuid()==0']],config,permissions='full',scope='Disposable CI identity check',elevation='root',supervise=False)
        worker_id,worker_path=worker_case(task,config,timeout=20)
        worker_command=elevation_command(worker_path,worker_id);worker_command=['sudo','-n','--',*worker_command[3:]]
        try:
            subprocess.run(worker_command,check=True,timeout=30)
            run(config,once=True)
            assert task in json.loads((Path(directory)/'work-runtime/state.json').read_text())['done']
        finally:
            # Only disposable CI artifacts: return ownership for runner cleanup.
            subprocess.run(['sudo','-n','--','chown','-R',str(os.getuid())+':'+str(os.getgid()),directory],check=True)

print('PASS native elevation bootstrap / platform parser; interactive UAC consent requires manual testing')
