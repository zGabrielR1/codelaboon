"""Verify a native Rust worker executes a real tool through the free gateway."""
import subprocess
import sys
from native_fixture import ROOT, MARKER, fixture

with fixture('jcode', tools=True) as (project, env, observed):
    result = subprocess.run([sys.executable, str(ROOT/'codelaboon/cli.py'), 'jcode', 'run', '--json',
                             'Read marker.txt using the read tool, then report its content.'],
                            cwd=project, env=env, capture_output=True, text=True, timeout=120)
    (ROOT/'.runtime/jcode-smoke.log').write_text(result.stdout+'\nSTDERR\n'+result.stderr)
    assert result.returncode == 0, result.stderr[-3000:] + result.stdout[-1000:]
    assert any(message.get('role') == 'tool' and MARKER in str(message.get('content'))
               for body in observed for message in body.get('messages', [])), 'No native tool result reached model'
    assert 'Verified '+MARKER in result.stdout, result.stdout[-2000:]
    print('PASS: Jcode Rust worker read a file through the shared Codelaboon gateway')
