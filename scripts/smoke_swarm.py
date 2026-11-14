"""Exercise actual native child agents, shared gateway, tools, and completion reports."""
import json
import subprocess
import sys
import time
from native_fixture import ROOT, MARKER, fixture

completed = set()


def calls(*items):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'fixture_' + str(index), 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(parameters)}}
        for index, (name, parameters) in enumerate(items)]}, 'tool_calls'


def respond(body, project):
    messages = body.get('messages', [])
    user = str(messages[2].get('content', '')) if len(messages) > 2 else ''
    worker = next((name for name in ('LANE_ALPHA', 'LANE_BETA', 'LANE_OVERFLOW') if name in user), None)
    previous = [call for row in messages if row.get('role') == 'assistant' for call in row.get('tool_calls', [])]
    actions = [json.loads(call['function']['arguments']).get('action') for call in previous
               if call['function']['name'] == 'swarm']
    if worker:
        found = any(row.get('role') == 'tool' and MARKER in str(row.get('content')) for row in messages)
        if not found:
            time.sleep(0.2)  # Keep both workers live while the coordinator probes the hard cap.
            return calls(('read', {'file_path': str(project/'marker.txt')}))
        completed.add(worker)
        if 'report' not in actions:
            return calls(('swarm', {'action': 'report', 'status': 'completed', 'message': worker + ' verified ' + MARKER}))
        return {'role': 'assistant', 'content': worker + ' verified ' + MARKER}, 'stop'
    if 'spawn' not in actions:
        return calls(*[('swarm', {'action': 'spawn', 'label': name.lower(), 'spawn_mode': 'headless',
                                 'model': 'inherit', 'prompt': name + ': Read marker.txt and report completed.'})
                       for name in ('LANE_ALPHA', 'LANE_BETA', 'LANE_OVERFLOW')])
    if 'await_members' not in actions:
        return calls(('swarm', {'action': 'await_members', 'target_status': ['completed'], 'timeout_minutes': 1}))
    if len(completed) < 2:
        time.sleep(0.25)
        return calls(('swarm', {'action': 'status'}))
    if not any(call['function']['name'] == 'todo' for call in previous):
        return calls(('todo', {'todos': []}))
    return {'role': 'assistant', 'content': 'SWARM_VERIFIED ' + ','.join(sorted(completed))}, 'stop'


with fixture('jcode', responder=respond) as (project, env, observed):
    # Keep test sessions outside durable personal state.
    env['CODELABOON_DATA_DIR'] = str(project/'data')
    result = subprocess.run([sys.executable, str(ROOT/'codelaboon/cli.py'), 'swarm',
                             'Verify two independent worker lanes.', '--workers', '2', '--timeout', '100'],
                            cwd=project, env=env, capture_output=True, text=True, timeout=115)
    (ROOT/'.runtime/swarm-smoke.log').write_text(result.stdout+'\nSTDERR\n'+result.stderr+
        '\nREQUESTS: '+str(len(observed)))
    assert result.returncode == 0, result.stderr[-2500:] + result.stdout[-1500:]
    assert completed == {'LANE_ALPHA', 'LANE_BETA'}, (completed, result.stdout[-2000:])
    assert any('live-agent limit reached' in str(row.get('content'))
               for body in observed for row in body.get('messages', []) if row.get('role') == 'tool'), 'Native worker cap not enforced'
    assert 'SWARM_VERIFIED' in result.stdout, result.stdout[-2000:]
    assert any(row.get('role') == 'tool' and 'completed' in str(row.get('content'))
               for body in observed for row in body.get('messages', [])), 'No native completion report'
    print('PASS: two native Rust workers read a file and reported completion through one gateway; excess worker rejected')
