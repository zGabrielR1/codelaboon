"""Run and restart two durable native swarm cycles with real independent checks."""
import json
from pathlib import Path
import subprocess
import sys
from native_fixture import ROOT, MARKER, fixture
from smoke_swarm import respond

with fixture('jcode', responder=respond) as (project, env, observed):
    driver = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from codelaboon import work
from codelaboon.watch import run
root=Path.cwd()
config=work.initialize(root/'work.json')
options=dict(controller='worker',workers=2,timeout=60,interval=1,cycles=2,model='free')
check=[sys.executable,'-c',"from pathlib import Path; assert 'NATIVE_FIXTURE_37' in Path('marker.txt').read_text()"]
job=work.add(root,'Verify two independent worker lanes',[check],config,options)
run(config,once=True)
state_path=root/'work-runtime/state.json'
state=json.loads(state_path.read_text())
assert state['cycles'][job]==1 and job not in state['done'], state
state['next_run'][job]=0
state_path.write_text(json.dumps(state))
# Reload configuration/state as a restarted supervisor does.
run(config,once=True)
state=json.loads(state_path.read_text())
assert state['cycles'][job]==2 and job in state['done'], state
assert len(list((root/'work-runtime').glob('*/check-0.log')))==2
print('DURABLE_SWARM_CYCLES_VERIFIED')
'''
    result = subprocess.run([sys.executable, '-c', driver, str(ROOT)], cwd=project, env=env,
                            capture_output=True, text=True, timeout=150)
    (ROOT/'.runtime/continuous-swarm-smoke.log').write_text(result.stdout+'\nSTDERR\n'+result.stderr)
    assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-2000:]
    assert 'DURABLE_SWARM_CYCLES_VERIFIED' in result.stdout
    reads = [row for body in observed for row in body.get('messages', [])
             if row.get('role') == 'tool' and MARKER in str(row.get('content'))]
    assert len(reads) >= 4, 'Two native workers per cycle did not reach the fixture'
    print('PASS: two native swarm cycles survive supervisor reload and pass independent acceptance checks')
