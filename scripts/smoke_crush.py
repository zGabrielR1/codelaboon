"""Exercise Crush's real file tool through the Codelaboon free gateway."""
import subprocess
import sys
from native_fixture import ROOT, MARKER, fixture

with fixture('crush', tools=True) as (project, env, observed):
    command = [sys.executable, str(ROOT / 'codelaboon/cli.py'), 'crush', 'run', '--quiet',
               'Read marker.txt using the view tool, then report its content.']
    for attempt in range(2):
        start = len(observed)
        result = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=120)
        (ROOT / '.runtime/crush-smoke.log').write_text(result.stdout + '\nSTDERR\n' + result.stderr)
        assert result.returncode == 0, result.stderr[-2500:] + result.stdout[-1500:]
        assert any(message.get('role') == 'tool' and MARKER in str(message.get('content'))
                   for body in observed[start:] for message in body.get('messages', [])), 'No real view result reached backend'
        assert 'Verified ' + MARKER in result.stdout, result.stdout[-2000:]
    print('PASS: Crush used the free gateway, read a real file, and completed across two launches')
