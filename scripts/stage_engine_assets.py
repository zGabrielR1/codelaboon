"""Stage verified source-engine modules next to the thin core release artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=root / 'dist')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
for info in json.loads((root / 'codelaboon/_vendor/engines.json').read_text())['engines'].values():
    source = root / 'codelaboon/_vendor' / (info['name'] + '.tar.gz')
    with source.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == info['sha256'], 'Source asset hash differs from manifest'
    shutil.copy2(source, args.out / info['asset'])
    print(info['asset'])
