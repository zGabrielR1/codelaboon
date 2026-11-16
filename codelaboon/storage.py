"""Measured, non-destructive project slimming: preserve data outside the source tree."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from codelaboon.paths import cache_dir, config_dir, data_dir, development_dir


def size(path):
    total, seen = 0, set()
    for parent, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(parent) / name).is_symlink()]
        for name in files:
            item = Path(parent) / name
            try:
                stat = item.lstat()
            except FileNotFoundError:
                continue
            key = (stat.st_dev, stat.st_ino)
            if key in seen:
                continue
            seen.add(key)
            total += stat.st_size
    return total


def plan(project):
    project = Path(project).resolve()
    if not (project / 'codelaboon/cli.py').is_file() or not (project / 'pyproject.toml').is_file():
        raise ValueError('Select the Codelaboon source checkout, not a parent projects folder')
    dev = development_dir()
    paths = [
        ('codelaboon/_vendor/opencode', dev / 'vendor/opencode'),
        ('codelaboon/_vendor/oh-my-pi', dev / 'vendor/oh-my-pi'),
        ('forks', dev / 'forks'), ('upstream', dev / 'upstream'),
        ('releases', data_dir() / 'releases'),
        ('opencode-source.tar.gz', dev / 'reference-archives/opencode-source.tar.gz'),
        ('omp-source.tar.gz', dev / 'reference-archives/omp-source.tar.gz'),
        ('.runtime/rc10-published-evidence', data_dir() / 'release-evidence/rc10'),
        ('.runtime/node_modules', dev / 'runtime/node_modules'),
        ('.runtime/ui-config', dev / 'runtime/ui-config'),
        ('.runtime/buildenv', dev / 'runtime/buildenv'),
        ('build', dev / 'build-output'),
        ('.watch/local', config_dir() / 'runtime/local'),
        ('.runtime/work-runtime', config_dir() / 'work-runtime'),
        ('.runtime/work.json', config_dir() / 'work.json'),
        ('.watch', data_dir() / 'legacy-watch'),
    ]
    result = []
    for relative, destination in paths:
        source = project / relative
        if not source.exists():
            continue
        destination = destination.expanduser().resolve()
        if source.is_symlink() or destination.is_relative_to(project):
            raise ValueError('Unsafe source/destination for ' + relative)
        tracked = subprocess.check_output(['git', '-C', str(project), 'ls-files', '-z', '--', relative])
        if tracked:
            raise ValueError('Refusing to relocate tracked release/source inputs: ' + relative)
        result.append({'source': str(source), 'destination': str(destination),
                       'bytes': source.stat().st_size if source.is_file() else size(source)})
    return result


def active_sources(moves):
    """Linux: refuse moving trees used by a live process; expose PIDs, not private argv."""
    roots = [Path(item['source']) for item in moves]
    active = []
    if not Path('/proc').is_dir():
        return active
    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            paths = [Path(os.readlink(process/'cwd'))]
            paths.extend(Path(os.fsdecode(arg)) for arg in (process/'cmdline').read_bytes().split(b'\0')
                         if arg.startswith(b'/'))
            if any(path == root or path.is_relative_to(root) for path in paths for root in roots):
                active.append(int(process.name))
        except (OSError, ValueError):
            continue
    return active


def compact(project, apply=False):
    project = Path(project).resolve()
    moves = plan(project)
    if not apply:
        return {'apply': False, 'bytes_to_relocate': sum(item['bytes'] for item in moves), 'moves': moves}
    from codelaboon.work import running
    runtime = project / '.runtime/work-runtime'
    if runtime.exists() and running(runtime):
        raise ValueError('Stop the idle Codelaboon worker service before relocating its runtime/model')
    active = active_sources(moves)
    if active:
        raise ValueError('Stop processes using relocation sources first: ' + ', '.join(map(str, active)))
    for item in moves:
        if Path(item['destination']).exists():
            raise FileExistsError('Destination already exists; nothing moved: ' + item['destination'])
    journal = data_dir() / 'storage-migrations' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    journal.parent.mkdir(parents=True, exist_ok=True)
    completed = []
    try:
        for item in moves:
            source, destination = Path(item['source']), Path(item['destination'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            completed.append(item)
            journal.write_text(json.dumps({'project': str(project), 'moves': completed}, indent=2) + '\n')
        config = config_dir() / 'work.json'
        if config.is_file() and any(Path(item['source']) == project / '.runtime/work.json' for item in completed):
            value = json.loads(config.read_text())
            for key in ('local_executable', 'local_model'):
                if isinstance(value.get(key), str):
                    try:
                        relative = Path(value[key]).resolve().relative_to(project / '.watch/local')
                    except ValueError:
                        continue
                    value[key] = str(config_dir() / 'runtime/local' / relative)
            config.write_text(json.dumps(value, indent=2) + '\n')
    except BaseException:
        # Every completed move is recorded; no directory or file is deleted.
        raise
    return {'apply': True, 'bytes_relocated': sum(item['bytes'] for item in completed),
            'journal': str(journal), 'moves': completed}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'compact'])
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(arguments)
    if args.apply and args.action != 'compact':
        parser.error('--apply belongs to compact')
    print(json.dumps(compact(args.project, args.apply), indent=2))


if __name__ == '__main__':
    main()
