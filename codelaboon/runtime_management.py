"""Offline runtime status, explicit repair and updater maintenance."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import uuid

from codelaboon.paths import config_dir

ENGINES = ('opencode', 'omp')


def location(engine):
    from codelaboon.engine_assets import record
    from codelaboon.paths import development_dir
    info = record(engine)
    if os.environ.get('CODELABOON_DEV_RUNTIME') == '1':
        return development_dir()/'vendor'/info['name']
    return config_dir()/'runtime'/f"{info['name']}-{info['sha256'][:16]}"


def inspect(engine):
    from codelaboon.native_tui import dependency_snapshot
    root = location(engine)
    row = {'engine':engine, 'path':str(root), 'state':'not_installed',
           'message':'Prepared on first launch', 'repair_command':f'codelaboon runtime repair --engine {engine}'}
    try:
        root.stat()
    except FileNotFoundError:
        return row
    except OSError:
        row.update(state='unavailable', message='Runtime directory cannot be accessed; check filesystem permissions')
        return row
    try:
        current = dependency_snapshot(root)
        marker = json.loads((root/'.codelaboon-ready').read_text(encoding='utf-8'))
        if not isinstance(marker, dict) or marker.get('format') != 3:
            row.update(state='needs_verification', message='Setup needs startup verification')
        elif marker.get('dependency_manifests') != current:
            row.update(state='damaged', message='Dependency manifests changed or are missing')
        else:
            row.update(state='ready', message=f"{len(current)} dependency manifests verified")
    except FileNotFoundError:
        row.update(state='needs_verification', message='Dependencies or startup receipt are missing')
    except (OSError, ValueError, TypeError):
        row.update(state='damaged', message='Dependency manifests or startup receipt could not be validated')
    return row


def read_receipt():
    try:
        value = json.loads((config_dir()/'last-update.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def save_receipt(success, runtimes):
    from codelaboon import __version__
    root = config_dir()
    root.mkdir(parents=True, exist_ok=True)
    temporary = root/('.last-update-'+uuid.uuid4().hex+'.tmp')
    value = {'format':1, 'time':time.time(), 'version':__version__, 'success':bool(success), 'runtimes':runtimes}
    try:
        with os.fdopen(os.open(temporary, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600), 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
        temporary.replace(root/'last-update.json')
    finally:
        temporary.unlink(missing_ok=True)


def maintain(prepare=None):
    """Repair existing source runtimes; prepare absent engines only if requested."""
    from codelaboon.native_tui import setup
    rows = []
    failures = []
    engines = list(ENGINES)
    if prepare and prepare not in engines:
        engines.append(prepare)
    for engine in engines:
        row = inspect(engine) if engine in ENGINES else {'engine':engine,'state':'not_installed'}
        if row['state'] == 'ready':
            print(f"  [ok] {engine}: {row['message']}")
        elif row['state'] == 'not_installed' and engine != prepare:
            print(f'  [skip] {engine}: not installed; kept lazy')
        else:
            print(f'  [repair] {engine}: preparing and verifying startup', flush=True)
            try:
                setup(engine)
                row = inspect(engine) if engine in ENGINES else {'engine':engine,'state':'ready'}
                if row['state'] != 'ready':
                    raise RuntimeError('Runtime verification did not produce a valid ready receipt')
                row['action'] = 'repaired'
                print(f'  [ok] {engine}: startup verified')
            except Exception as error:
                rows.append({'engine':engine, 'state':'repair_failed'})
                failures.append((engine, error))
                print(f'{engine} runtime repair failed: {error}', file=sys.stderr)
                print(f'Retry: {row.get("repair_command", f"codelaboon tui --engine {engine} --setup")}', file=sys.stderr)
                continue
        rows.append({key:row[key] for key in ('engine','state','action') if key in row})
    save_receipt(not failures, rows)
    if failures:
        failed_engines = ', '.join(engine for engine, _ in failures)
        raise RuntimeError(f'Runtime repair failed for {failed_engines}') from failures[0][1]


def show_status(engines=ENGINES, overview=False):
    from codelaboon import __version__
    print(f'Codelaboon {__version__}')
    if overview:
        print('Workspace: '+str(Path.cwd().resolve()))
    for engine in engines:
        row = inspect(engine)
        print(f"  {engine:<10} {row['state'].replace('_', ' '):<20} {row['message']}")
        if row['state'] not in ('ready', 'not_installed'):
            print('             '+row['repair_command'])
    receipt = read_receipt()
    if receipt:
        try:
            when = datetime.fromtimestamp(receipt['time'], timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        except (ValueError, TypeError, KeyError, OSError, OverflowError):
            when = 'unknown time'
        print(f"Last update: {receipt.get('version', 'unknown')} at {when} - {'verified' if receipt.get('success') else 'needs attention'}")
    else:
        print('Last update: no receipt yet')
    if overview:
        print('\nContinue work: codelaboon tui --continue')
        print('Security mode: codelaboon tui --profile security')
        print('Diagnostics:   codelaboon doctor')


def main(arguments=None, overview=False):
    parser = argparse.ArgumentParser(description=__doc__)
    if overview:
        parser.add_argument('--json', action='store_true')
        args = parser.parse_args(arguments)
        if args.json:
            from codelaboon import __version__
            print(json.dumps({'version':__version__,'workspace':str(Path.cwd().resolve()),
                'runtimes':[inspect(engine) for engine in ENGINES], 'last_update':read_receipt()}, indent=2))
        else:
            show_status(overview=True)
        return
    commands = parser.add_subparsers(dest='action', required=True)
    status = commands.add_parser('status');status.add_argument('--engine', choices=ENGINES);status.add_argument('--json', action='store_true')
    repair = commands.add_parser('repair');repair.add_argument('--engine', choices=ENGINES, default='opencode');repair.add_argument('--force', action='store_true', help='Rebuild all dependencies using a fresh cache, even if manifests are valid')
    maintenance = commands.add_parser('maintain', help=argparse.SUPPRESS);maintenance.add_argument('--prepare', choices=(*ENGINES,'kilo','claude','crush','jcode','codex'))
    args = parser.parse_args(arguments)
    try:
        if args.action == 'status':
            engines = (args.engine,) if args.engine else ENGINES
            if args.json: print(json.dumps([inspect(engine) for engine in engines], indent=2))
            else: show_status(engines)
        elif args.action == 'repair':
            from codelaboon.native_tui import setup
            setup(args.engine, force=args.force)
            if inspect(args.engine)['state'] != 'ready': raise RuntimeError('Runtime is still not ready')
            print(args.engine+' runtime is ready. Start with: codelaboon'+(' omp' if args.engine=='omp' else ''))
        else:
            maintain(args.prepare)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, 'Runtime maintenance: '+str(error)+'\n')


if __name__ == '__main__':
    main()
