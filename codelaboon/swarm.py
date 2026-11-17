"""Bounded native Rust swarms, sharing one provider gateway and worker server."""
import argparse
import json
import os
from pathlib import Path
import shlex
import uuid
import time
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codelaboon.paths import data_dir


def execute(task, workers=4, timeout=1800, checks=(), model='free', engine='jcode'):
    if not task.strip() or not 1 <= workers <= 1000 or timeout <= 0:
        raise ValueError('Provide a task, 1–1000 workers, and a positive timeout')
    if not all(isinstance(command, (list, tuple)) and command and
               all(isinstance(part, str) for part in command) for command in checks):
        raise ValueError('Acceptance checks must be nonempty argument lists')
    from codelaboon.engine_tasks import ENGINES
    if engine not in ENGINES or (engine!='jcode' and workers!=1):
        raise ValueError('Select a supported engine; portable coordinators require --workers 1')
    home = data_dir() / 'swarm/runs' / uuid.uuid4().hex
    home.mkdir(parents=True, mode=0o700)
    instruction = (('Coordinate this task. Use the native swarm tool to delegate independent work when useful. '
                    f'Use at most {workers} concurrent workers. ' if engine=='jcode' else
                    'Execute as one portable coordinator. Perform analysis, implementation and verification sequentially. '
                    'Use this engine\'s available tools; do not invent unsupported swarm tools. ')+
                   'Resolve conflicts, retain context, and verify the final result.\n\n'+task)
    from codelaboon.execution_policy import profile as task_profile
    if task_profile()=='security':instruction=(Path(__file__).parent/'prompts/security.md').read_text()+'\n\n'+instruction
    deadline = time.monotonic() + timeout
    if engine=='jcode':
        from codelaboon.cli import CodelaboonCLI
        from codelaboon.external_engines import executable
        from codelaboon.jcode_engine import run
        from codelaboon.native_gateway import serve, COMPATIBLE
        binary=executable('jcode');cli=CodelaboonCLI();cli.load_providers()
        providers={name:value for name,value in cli.providers.items() if name in COMPATIBLE}
        with serve(providers) as (gateway,url):
            rows=gateway.models(startup=True)
            try:
                code=run(binary,['--model',model,'run',instruction],rows,url,gateway.token,
                         workers,max(0.01,deadline-time.monotonic()),home)
            except RuntimeError as error:
                (home/'error.log').write_text(str(error)+'\n')
                code=124 if 'time budget' in str(error) else 1
    else:
        from codelaboon.watch import execute as checked_command
        prompt=home/'prompt.md';prompt.write_text(instruction,encoding='utf-8')
        command=[sys.executable,str(Path(__file__).with_name('cloud_worker.py')),'--agent','--engine',engine,
                 '--model',model,'--runtime',str(home),str(prompt)]
        code=checked_command(command,Path.cwd(),home/'output.log',max(0.01,deadline-time.monotonic()),env=dict(os.environ))
        with (home/'output.log').open('rb') as stream:
            stream.seek(0,2);stream.seek(max(0,stream.tell()-65536))
            print(stream.read(65536).decode('utf-8',errors='replace'),flush=True)
    results = []
    if not code:
        for command in checks:
            from codelaboon.watch import execute as checked_command
            output = home / ('check-' + str(len(results)) + '.log')
            remaining = deadline - time.monotonic()
            try:
                check_code = checked_command(command, Path.cwd(), output, remaining) if remaining > 0 else 124
            except OSError as error:
                output.write_text(str(error) + '\n')
                check_code = 127
            results.append({'argv': command, 'exit_code': check_code, 'log': str(output)})
            if check_code:
                code = check_code
                break
    (home / 'result.json').write_text(json.dumps({'engine': engine, 'workers_limit': workers,
        'project': str(Path.cwd()), 'exit_code': code, 'checks': results,
        'acceptance': 'passed' if checks and not code else 'failed' if code else 'not_requested'}, indent=2) + '\n')
    return code


def enqueue(task, workers=4, timeout=1800, checks=(), model='free', controller='local',
            interval=60, cycles=0, config=None, project=None, permissions='default', profile='coding', supervise=None, scope='', review_interval=15, allowed_paths=None, elevation='none',engine='jcode',start_worker=True,execution_settings=None):
    from codelaboon import work
    from codelaboon.work_queue import validate_swarm
    options = validate_swarm(dict(workers=workers, timeout=timeout, model=model,
                                  controller=controller, interval=interval, cycles=cycles,engine=engine))
    if not checks:
        raise ValueError('Continuous swarms require at least one independent --check command')
    from codelaboon.paths import config_dir
    target = Path(config) if config else config_dir()/'work.json'
    if not target.exists():
        work.initialize(target)
    _, _, runtime = work.configuration(target)
    if work.running(runtime):
        info = runtime/'service-info.json'
        features = json.loads(info.read_text()).get('features', []) if info.exists() else []
        if 'continuous-swarm' not in features:
            raise ValueError('The running worker predates continuous swarms. Use work stop, wait until stopped, '
                             'then work start after upgrading; no task was queued.')
    task_id = work.add(project or Path.cwd(), task, checks, target, swarm=options,permissions=permissions,profile=profile,supervise=supervise,scope=scope,review_interval=review_interval,allowed_paths=allowed_paths,elevation=elevation,execution_settings=execution_settings)
    if start_worker:work.start(target)
    print('Continuous swarm: ' + task_id + ' | controller: ' + controller)
    print('Use swarm --status, --pause ID, --resume ID or --stop ID. work enable persists across reboots.')
    return task_id


def control(action, task_id, config=None):
    from codelaboon.work import configuration
    from codelaboon.work_queue import controls
    _, value, root = configuration(config)
    tasks = list(value.get('tasks', []))
    tasks.extend(json.loads(path.read_text()) for path in (root/'inbox').glob('*.json'))
    if not any(task['id'] == task_id and task.get('swarm') for task in tasks):
        raise ValueError('Unknown swarm ID: ' + task_id)
    directory = controls(root, task_id)
    directory.mkdir(parents=True, exist_ok=True)
    if action == 'resume':
        if (directory/'STOP').exists():
            raise ValueError('This swarm was stopped. Queue a new swarm to restart it.')
        (directory/'PAUSE').unlink(missing_ok=True)
    else:
        (directory/('PAUSE' if action == 'pause' else 'STOP')).touch()
    print(action.capitalize() + ': ' + task_id + '. Active cycles and checks finish first.')


def _main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task', nargs='?')
    parser.add_argument('--task-file', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--workers', type=int, help='Native swarm limit; portable engines use one coordinator')
    from codelaboon.engine_tasks import ENGINES
    parser.add_argument('--engine',choices=ENGINES,default='jcode')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--model', default='free')
    parser.add_argument('--execution-settings-file',type=Path,help='JSON worker/planner model and prompt settings, captured before queue publication (--continuous)')
    parser.add_argument('--check', action='append', default=[], help='Independent acceptance command; repeat for multiple checks')
    parser.add_argument('--continuous', action='store_true', help='Queue recurring verified cycles in the background supervisor')
    parser.add_argument('--controller', choices=['local', 'worker'], default='local')
    parser.add_argument('--interval', type=int, default=60, help='Seconds between continuous cycles')
    parser.add_argument('--cycles', type=int, default=0, help='Successful cycle limit; 0 continues until stopped')
    parser.add_argument('--config', help='Background worker configuration')
    parser.add_argument('--project', type=Path, help='Project for a continuous swarm; defaults to current directory')
    parser.add_argument('--elevation',choices=['none','root','administrator'],default='none')
    parser.add_argument('--permissions',choices=['default','full'],default='default')
    parser.add_argument('--profile',choices=['coding','security'],default='coding')
    parser.add_argument('--scope',default='')
    parser.add_argument('--supervise',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--review-interval',type=int,default=15)
    parser.add_argument('--allow-path',action='append',default=[])
    parser.add_argument('--json', action='store_true', help='Machine-readable status')
    parser.add_argument('--watch', action='store_true', help='Refresh --status every two seconds')
    parser.add_argument('--task', dest='task_id', help='Filter --status to one swarm ID')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--status', action='store_true')
    actions.add_argument('--pause', metavar='ID')
    actions.add_argument('--resume', metavar='ID')
    actions.add_argument('--stop', metavar='ID')
    args = parser.parse_args(arguments)
    if args.workers is None:args.workers=4 if args.engine=='jcode' else 1
    if (args.watch or args.task_id) and not args.status:parser.error('--watch/--task belong to --status')
    if args.status or args.pause or args.resume or args.stop:
        if args.task or args.task_file or args.continuous:
            parser.error('Status/control actions do not accept a task')
        if args.status:
            from codelaboon.work_monitor import watch
            watch(args.config,args.task_id,swarm_only=True,follow=args.watch,as_json=args.json)
        else:
            action = next(name for name in ('pause', 'resume', 'stop') if getattr(args, name))
            control(action, getattr(args, action), args.config)
        return
    if bool(args.task) == bool(args.task_file):
        parser.error('Provide one task or --task-file')
    task = args.task_file.read_text(encoding='utf-8') if args.task_file else args.task
    checks = [shlex.split(item) for item in args.check]
    if args.continuous:
        enqueue(task, args.workers, args.timeout, checks, args.model, args.controller,
                args.interval, args.cycles, args.config, args.project,args.permissions,args.profile,args.supervise,args.scope,args.review_interval,args.allow_path,args.elevation,args.engine,execution_settings=json.loads(args.execution_settings_file.read_text(encoding='utf-8')) if args.execution_settings_file else None)
        return
    if args.elevation!='none' or args.permissions!='default' or args.profile!='coding' or args.scope or args.supervise is not None or args.allow_path:
        parser.error('Execution policy options belong to --continuous tasks')
    if args.project or args.config or args.execution_settings_file:
        parser.error('--project/--config belong to continuous mode or status/controls')
    raise SystemExit(execute(task, args.workers, args.timeout, checks, args.model,args.engine))


def main(arguments=None):
    try:
        return _main(arguments)
    except (OSError, ValueError, RuntimeError) as error:
        print('Swarm: ' + str(error), file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
