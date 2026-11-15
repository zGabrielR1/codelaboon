"""Verify the editor's native binary through the exact Codelaboon wrapper contract."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from native_fixture import ROOT, MARKER, fixture

with fixture('claude',tools=True) as (project,env,observed):
    (project/'.claude').mkdir()
    (project/'.claude/settings.json').write_text(json.dumps({'env':{'ANTHROPIC_BASE_URL':'http://127.0.0.1:9','ANTHROPIC_API_KEY':'project-key-not-for-codelaboon'}}))
    bundled=list((Path.home()/'.vscode/extensions').glob('anthropic.claude-code-*/resources/native-binary/claude'))
    binary=str(bundled[0]) if bundled else shutil.which('claude',path=env['PATH'])
    assert binary,'Install the official Claude CLI/extension before this check'
    driver='import sys;sys.path.insert(0,sys.argv.pop(1));from codelaboon.ide import claude_wrapper;claude_wrapper()'
    command=[sys.executable,'-c',driver,str(ROOT),binary,'-p','Read marker.txt using the Read tool, then report its content.',
             '--model','sonnet','--allowedTools','Read','--max-turns','4','--output-format','stream-json','--verbose']
    result=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=120)
    (ROOT/'.runtime/ide-wrapper-smoke.log').write_text(result.stdout+'\nSTDERR\n'+result.stderr)
    assert result.returncode==0,result.stderr[-2000:]+result.stdout[-2000:]
    events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert any(event.get('type')=='result' and MARKER in str(event) for event in events),'No SDK result'
    assert any(row.get('role')=='tool' and MARKER in str(row.get('content')) for body in observed for row in body.get('messages',[])),'Native IDE tool result missing'
    print('PASS: official editor Claude binary, built-in model alias, SDK JSON stream and native file tool use Codelaboon')
