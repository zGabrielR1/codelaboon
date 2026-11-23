"""Prevent optional engine bundles/dependency trees from growing the core artifacts."""
from pathlib import Path
import sys
import tarfile
import zipfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')
artifacts = [*root.glob('codelaboon-*.whl'), *root.glob('codelaboon-1*.tar.gz')]
assert len(artifacts) == 2, 'Expected one core wheel and one core source distribution'
for path in artifacts:
    if path.suffix == '.whl':
        names = zipfile.ZipFile(path).namelist()
    else:
        with tarfile.open(path) as archive:
            names = archive.getnames()
    assert any(name.endswith('codelaboon/_vendor/engines.json') for name in names), 'Missing engine manifest'
    vendor_files = [name for name in names if '/_vendor/' in name]
    assert all(name.endswith('/_vendor/engines.json') for name in vendor_files), path
    assert not any(name.endswith('.tar.gz') or 'node_modules' in Path(name).parts for name in names), path
    assert path.stat().st_size < 1024*1024, f'Core artifact exceeds 1 MiB: {path}'
    print(f'PASS thin core {path.name}: {path.stat().st_size} bytes')
