"""Persistent command scheduler: python -m codelaboon.watch CONFIG.json."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import uuid

from codelaboon.work_queue import ready, swarm_harness, validate_swarm


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(path)


def terminate(process):
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10)
        except subprocess.TimeoutExpired:
            pass
        if process.poll() is None:
            process.kill()
    else:
        import signal
        try:
            os.killpg(process.pid, signal.SIGTERM)
            # A wrapper may exit before its children finish cleaning private native groups.
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                process.poll()  # Reap the direct child while waiting for the group.
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def progress_tail(directory, limit=12000):
    try:
        with (Path(directory)/'output.log').open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell()-limit))
            return stream.read(limit).decode('utf-8', errors='replace')
    except OSError:
        return '(Previous output unavailable; inspect the saved attempt directory.)'


def execute(argv, cwd, output, timeout):
    with output.open('wb') as log:
        process = subprocess.Popen(argv, cwd=cwd, stdout=log,
                                   stderr=subprocess.STDOUT,
                                   start_new_session=os.name != 'nt')
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate(process)
            return 124
        except BaseException:
            terminate(process)
            raise


def run(config_path, once=False):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    base = config_path.parent
    root = (base / config.get('runtime', '.watch')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # An OS lock releases automatically even if the supervisor crashes.
    lock = (root / 'lock').open('a+b')
    lock.seek(0)
    lock.write(b'0')
    lock.flush()
    lock.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise RuntimeError('Another runner owns this runtime directory')
    try:
        supervise(config, base, root, once)
    finally:
        lock.close()


def supervise(config, base, root, once):
    tasks = config['tasks']
    harnesses = config['harnesses']
    if not harnesses:
        raise ValueError('At least one harness required')
    for rows in (tasks, harnesses):
        ids = [row['id'] for row in rows]
        if len(set(ids)) != len(ids):
            raise ValueError('IDs must be unique')
    for task in tasks:
        if not (base / task['project']).resolve().is_dir():
            raise ValueError('Missing project: ' + task['project'])
    for harness in harnesses:
        if not isinstance(harness['argv'], list) or not harness['argv']:
            raise ValueError('argv must be a nonempty argument list')
    orchestrator = config.get('orchestrator')
    if orchestrator:
        for harness in harnesses:
            if harness.get('location') != 'cloud':
                raise ValueError('Orchestrated workers must declare location=cloud')
            if not set(harness.get('stages', [])) <= {'plan', 'build'}:
                raise ValueError('Worker stages must be plan and/or build')
        if not all(any(stage in h.get('stages', []) for h in harnesses) for stage in ('plan', 'build')):
            raise ValueError('Cloud orchestration needs both planning and building workers')
        for task in tasks:
            if not task.get('verify_argv'):
                raise ValueError('Cloud builds require explicit verify_argv checks')
            if not isinstance(task['verify_argv'], list) or not all(
                    isinstance(check, list) and check and all(isinstance(part, str) for part in check)
                    for check in task['verify_argv']):
                raise ValueError('verify_argv must be nonempty lists of string arguments')
    state_path = root / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state.setdefault('done', [])
    state.setdefault('cooldowns', {})
    state.setdefault('task_cursor', 0)
    state.setdefault('harness_cursor', 0)
    state.setdefault('plans', {})
    state.setdefault('last_attempts', {})
    state.setdefault('health', {})
    state.setdefault('cycles', {})
    state.setdefault('next_run', {})
    idle = max(1, float(config.get('poll_seconds', 15)))
    while not (root / 'STOP').exists():
        if (root / 'PAUSE').exists():
            if once:
                return
            time.sleep(min(idle, 30))
            continue
        queued = []
        for item in sorted((root / 'inbox').glob('*.json')):
            try:
                task = json.loads(item.read_text(encoding='utf-8'))
                if (not isinstance(task.get('id'), str) or not task['id']
                        or not isinstance(task.get('prompt'), str)
                        or not (base / task['project']).resolve().is_dir()
                        or not task.get('verify_argv')
                        or not all(isinstance(check, list) and check and
                                   all(isinstance(part, str) for part in check)
                                   for check in task['verify_argv'])):
                    raise ValueError('Invalid queued task')
                if 'swarm' in task:
                    validate_swarm(task['swarm'])
                queued.append(task)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                print(f'Ignoring invalid inbox file {item.name}: {error}', flush=True)
        all_tasks = {t['id']: t for t in tasks}
        for task in queued:
            if task['id'] not in all_tasks:
                all_tasks[task['id']] = task
        pending = [t for t in all_tasks.values() if ready(t, state, root)]
        eligible = [h for h in harnesses if
                    state['cooldowns'].get(h['id'], 0) <= time.time()]
        available = []
        for harness in eligible:
            probe = harness.get('available_argv')
            if probe:
                try:
                    values = {'python': sys.executable, 'runtime': str(root),
                              'source': str(Path(__file__).resolve().parent.parent)}
                    result = subprocess.run([part.format_map(values) for part in probe],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    if result.returncode:
                        continue
                except (OSError, subprocess.TimeoutExpired, KeyError, TypeError):
                    continue
            available.append(harness)
        eligible = available
        if not pending or (not eligible and not any(t.get("swarm") for t in pending)):
            if once:
                return
            time.sleep(min(idle, 30))
            continue
        pending = pending[state['task_cursor'] % len(pending):] + pending[:state['task_cursor'] % len(pending)]
        if eligible:
            eligible = eligible[state['harness_cursor'] % len(eligible):] + eligible[:state['harness_cursor'] % len(eligible)]
        jobs = []
        for candidate in pending:
            swarm = candidate.get('swarm')
            if swarm and (swarm['controller'] == 'worker' or candidate['id'] in state['plans']):
                custom = swarm_harness(candidate)
                if state['cooldowns'].get(custom['id'], 0) <= time.time():
                    jobs.append((candidate, custom, 'build'))
            else:
                stage = ('build' if candidate['id'] in state['plans'] else 'plan') if orchestrator else 'task'
                if swarm and not orchestrator:
                    raise ValueError('Local-controlled swarms require a local orchestrator configuration')
                jobs.extend((candidate, h, stage) for h in eligible
                            if not orchestrator or stage in h.get('stages', []))
        if not jobs:
            if once:
                return
            time.sleep(min(idle, 30))
            continue
        direct = lambda job: job[0].get('swarm', {}).get('controller') == 'worker' or not orchestrator
        if direct(jobs[0]):
            task, harness, stage = jobs[0]
        else:
            jobs = [job for job in jobs if not direct(job)][:16]
            metadata = [{'task': t['id'], 'project': t['project'],
                         'stage': s, 'harness': h['id'], 'model': h.get('model', 'auto'),
                         'health': state['health'].get(h['id'], {}),
                         'capabilities': h.get('capabilities', [])} for t, h, s in jobs]
            try:
                from codelaboon.local_router import choose
                selection = choose(orchestrator, metadata)
            except (OSError, ValueError, KeyError, IndexError) as error:
                save(root / 'router-error.json', {'time': time.time(), 'error': str(error)})
                print('Local router unavailable; no cloud dispatch: ' + str(error), flush=True)
                if once:
                    raise
                state['task_cursor'] += 1  # An offline local router must not starve worker-controlled jobs.
                save(state_path, state)
                time.sleep(min(idle, 30))
                continue
            task, harness, stage = jobs[selection]
        project = (base / task['project']).resolve()
        attempt = root / str(uuid.uuid4())
        attempt.mkdir()
        prompt = attempt / 'prompt.md'
        content = task['prompt']
        if task.get('swarm'):
            content += ('\n\nContinuous objective, verified cycle ' + str(state['cycles'].get(task['id'], 0)+1) +
                        '. Review previous progress and make the next useful increment. Do not redo completed work. '
                        'Keep work within this objective; verify changes and report progress and blockers.')
        if stage in ('plan', 'build'):
            content = ('Stage: ' + stage + '\nProject: ' + str(project) + '\n\n' + content +
                       '\n\nRespect project instructions. Do not deploy, publish, or commit. ')
            if stage == 'plan':
                content += ('Produce a concrete implementation plan and acceptance checks. '
                            'Do not implement or edit files. Output only the plan.\n')
            else:
                if task['id'] in state['plans']:
                    plan = Path(state['plans'][task['id']])
                    content += '\nCloud-authored plan:\n' + plan.read_text(encoding='utf-8')
                content += '\nImplement the plan and run these checks:\n' + json.dumps(task['verify_argv'])
            previous = state['last_attempts'].get(task['id'])
            if previous:
                content += '\nPrevious attempt logs (inspect if needed): ' + previous
                if task.get('swarm'):
                    content += '\nBounded previous progress summary:\n' + progress_tail(previous)
        prompt.write_text(content, encoding='utf-8')
        values = {'python': sys.executable, 'project': str(project),
                  'source': str(Path(__file__).resolve().parent.parent),
                  'runtime': str(root), 'stage': stage,
                  'prompt': content, 'prompt_file': str(prompt)}
        argv = [part.format_map(values) for part in harness['argv']]
        record = {'task': task['id'], 'harness': harness['id'], 'stage': stage,
                  'started': time.time(), 'status': 'running'}
        save(attempt / 'result.json', record)
        print(f"Running {task['id']} with {harness['id']}", flush=True)
        build_started = time.monotonic()
        try:
            code = execute(argv, project, attempt / 'output.log',
                           max(1, float(harness.get('timeout_seconds', 1800))))
        except OSError as error:
            (attempt / 'output.log').write_text(str(error), encoding='utf-8')
            code = 127
        if code == 0 and stage in ('plan', 'build'):
            output = attempt / 'output.log'
            if not output.exists() or not output.read_text(encoding='utf-8', errors='replace').strip():
                code = 125
        if code == 0 and stage != 'plan':
            for number, check in enumerate(task.get('verify_argv', [])):
                try:
                    remaining = (task['swarm']['timeout'] - (time.monotonic()-build_started)
                                 if task.get('swarm') else float(task.get('verify_timeout_seconds', 600)))
                    if remaining <= 0:
                        code = 124
                        (attempt / f'check-{number}.log').write_text('Cycle time budget exhausted')
                    else:
                        code = execute(check, project, attempt / f'check-{number}.log', remaining)
                except OSError as error:
                    (attempt / f'check-{number}.log').write_text(str(error), encoding='utf-8')
                    code = 127
                if code:
                    break
        record.update(status='succeeded' if code == 0 else 'failed',
                      exit_code=code, finished=time.time())
        health = state['health'].setdefault(harness['id'], {'succeeded': 0, 'failed': 0})
        health['succeeded' if code == 0 else 'failed'] += 1
        health['last_seconds'] = round(record['finished'] - record['started'], 2)
        health['last_exit_code'] = code
        save(attempt / 'result.json', record)
        if code == 0:
            if stage == 'plan':
                state['plans'][task['id']] = str(attempt / 'output.log')
            else:
                state['cycles'][task['id']] = state['cycles'].get(task['id'], 0) + 1
                swarm = task.get('swarm')
                if swarm and (not swarm['cycles'] or state['cycles'][task['id']] < swarm['cycles']):
                    state['plans'].pop(task['id'], None)
                else:
                    state['done'].append(task['id'])
        else:
            state['cooldowns'][harness['id']] = time.time() + max(
                1, float(harness.get('cooldown_seconds', 3600)))
        if task.get('swarm') and stage != 'plan':
            state['next_run'][task['id']] = time.time() + task['swarm']['interval']
        state['last_attempts'][task['id']] = str(attempt)
        state['task_cursor'] += 1
        state['harness_cursor'] += 1
        save(state_path, state)
        if once:
            return
        time.sleep(min(idle, 30))


def main():
    def stopped(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stopped)
    if os.name != 'nt':
        signal.signal(signal.SIGHUP, stopped)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    try:
        run(args.config, args.once)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
