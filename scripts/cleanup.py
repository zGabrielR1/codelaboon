"""Remove regenerable Codelaboon build output and Python caches."""

import argparse
import os
from pathlib import Path
import shutil
import stat


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ('codelaboon', 'config', 'examples', 'providers', 'scripts', 'tests')
CACHES = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
EXTERNAL_DIRS = {'_vendor', 'forks', 'node_modules', 'upstream', 'venv'}


def safe_path(path):
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        return False
    attributes = getattr(path.lstat(), 'st_file_attributes', 0)
    return not attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT


def artifacts():
    root_dirs = [ROOT / name for name in ('build', 'dist', *sorted(CACHES))]
    root_dirs.extend(sorted(ROOT.glob('*.egg-info')))
    for path in root_dirs:
        if path.is_dir() and safe_path(path):
            yield path
    yield from bytecode(ROOT)

    for name in SOURCE_DIRS:
        source = ROOT / name
        if not source.is_dir() or not safe_path(source):
            continue
        for directory, dirs, files in os.walk(source):
            parent = Path(directory)
            for child in sorted(dirs):
                path = parent / child
                if not safe_path(path) or child in EXTERNAL_DIRS or child.endswith('.local'):
                    dirs.remove(child)
                elif child in CACHES:
                    dirs.remove(child)
                    yield path
                elif child.startswith('.'):
                    dirs.remove(child)
            yield from bytecode(parent, files)


def bytecode(directory, filenames=None):
    paths = directory.iterdir() if filenames is None else (directory / name for name in filenames)
    for path in sorted(paths):
        if path.suffix in {'.pyc', '.pyo'} and path.is_file() and safe_path(path):
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='List paths without removing them.')
    args = parser.parse_args()
    for path in artifacts():
        print(path.relative_to(ROOT))
        if not args.dry_run:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


if __name__ == '__main__':
    main()
