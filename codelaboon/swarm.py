"""Bounded native Rust swarms, sharing one provider gateway and worker server."""
import argparse
import json
from pathlib import Path
import shlex
import uuid
import time
from codelaboon.paths import data_dir


def execute(task, workers=4, timeout=1800, checks=(), model='free'):
    if not task.strip() or not 1 <= workers <= 1000 or timeout <= 0:
        raise ValueError('Provide a task, 1–1000 workers, and a positive timeout')
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.external_engines import executable
    from codelaboon.jcode_engine import run
    from codelaboon.native_gateway import serve, FREE_COMPATIBLE
    binary = executable('jcode')
    cli = CodelaboonCLI()
    cli.load_providers()
    providers = {name: value for name, value in cli.providers.items() if name in FREE_COMPATIBLE or name == 'local'}
    home = data_dir() / 'swarm/runs' / uuid.uuid4().hex
    home.mkdir(parents=True, mode=0o700)
    instruction = ('Coordinate this coding task. Use the native swarm tool to delegate independent work when useful. '
                   f'Use at most {workers} concurrent workers. Resolve conflicts, retain context, and verify the final result.\n\n' + task)
    deadline = time.monotonic() + timeout
    with serve(providers) as (gateway, url):
        rows = gateway.models(startup=True)
        try:
            code = run(binary, ['--model', model, 'run', instruction], rows, url, gateway.token,
                       workers, max(0.01, deadline-time.monotonic()), home)
        except RuntimeError as error:
            (home / 'error.log').write_text(str(error) + '\n')
            code = 124 if 'time budget' in str(error) else 1
    results = []
    if not code:
        for command in checks:
            from codelaboon.watch import execute as checked_command
            output = home / ('check-' + str(len(results)) + '.log')
            remaining = deadline - time.monotonic()
            check_code = checked_command(command, Path.cwd(), output, remaining) if remaining > 0 else 124
            results.append({'argv': command, 'exit_code': check_code, 'log': str(output)})
            if check_code:
                code = check_code
                break
    (home / 'result.json').write_text(json.dumps({'engine': 'jcode', 'workers_limit': workers,
        'project': str(Path.cwd()), 'exit_code': code, 'checks': results,
        'acceptance': 'passed' if checks and not code else 'failed' if code else 'not_requested'}, indent=2) + '\n')
    return code


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--model', default='free')
    parser.add_argument('--check', action='append', default=[], help='Acceptance command; repeat for multiple checks')
    args = parser.parse_args(arguments)
    raise SystemExit(execute(args.task, args.workers, args.timeout, [shlex.split(item) for item in args.check], args.model))
