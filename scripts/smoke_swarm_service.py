"""Verify continuous swarm CLI controls against the real owned background service."""
import json
import subprocess
import sys
import time
from native_fixture import ROOT, fixture
from smoke_swarm import respond


def until(predicate, timeout=40):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError('Continuous service did not reach expected state')


with fixture('jcode',responder=respond) as (project,env,observed):
    # Create only isolated test state; do not touch the user's registered service.
    sys.path.insert(0,str(ROOT))
    from codelaboon.work import initialize
    config=initialize(project/'work.json')
    value=json.loads(config.read_text())
    value['poll_seconds']=1
    config.write_text(json.dumps(value))
    runtime=project/'work-runtime'
    command=[sys.executable,str(ROOT/'codelaboon/cli.py'),'swarm']
    def cli(*args):
        result=subprocess.run([*command,*args,'--config',str(config)],cwd=project,env=env,
                              capture_output=True,text=True,timeout=20)
        assert result.returncode==0,result.stderr
        return result.stdout
    with (ROOT/'.runtime/swarm-service-smoke.log').open('w') as output:
        process=subprocess.Popen([sys.executable,'-m','codelaboon.service',str(config)],cwd=ROOT,
                                 env=env,stdout=output,stderr=output,start_new_session=True)
        try:
            until(lambda:(runtime/'service-info.json').exists())
            cli('Verify two independent worker lanes','--continuous','--controller','worker',
                '--workers','2','--cycles','2','--interval','2','--timeout','60',
                '--check',sys.executable+" -c 'from pathlib import Path; assert Path(\"marker.txt\").is_file()'")
            task=json.loads(next((runtime/'inbox').glob('*.json')).read_text())['id']
            def state():
                path=runtime/'state.json'
                return json.loads(path.read_text()) if path.exists() else {}
            until(lambda:state().get('cycles',{}).get(task)==1)
            cli('--pause',task)
            time.sleep(2.2)
            assert state()['cycles'][task]==1,'Paused swarm ran another cycle'
            status=json.loads(cli('--status','--json'))
            assert status['pending'][0]['paused']
            cli('--resume',task)
            until(lambda:task in state().get('done',[]))
            assert state()['cycles'][task]==2
            assert len(list(runtime.glob('*/check-0.log')))==2
            assert not (project/'config/runtime/local/server.pid').exists(),'Worker control loaded local model'
            print('PASS: real background service ran two native cycles; CLI pause/resume/status and acceptance passed')
        finally:
            (runtime/'STOP').touch()
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise AssertionError('Owned test service failed graceful cleanup')
