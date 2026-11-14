"""Run official Claude Code against the local fixture, with no Anthropic account."""
import subprocess
import sys
from native_fixture import ROOT, MARKER, fixture

with fixture('claude', tools=True) as (project, env, observed):
    command = [sys.executable, str(ROOT / 'codelaboon/cli.py'), 'claude', '-p',
               'Read marker.txt using the Read tool, then report its content.',
               '--allowedTools', 'Read', '--max-turns', '4', '--output-format', 'json']
    result = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=120)
    (ROOT / '.runtime/claude-smoke.log').write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-2000:]
    assert any(message.get('role') == 'tool' and MARKER in str(message.get('content'))
               for body in observed for message in body.get('messages', [])), 'No real Read tool result reached backend'
    assert 'Verified ' + MARKER in result.stdout, result.stdout[-2000:]
    print('PASS: Claude Code used the free gateway, read a real file, and completed without a Claude account')
