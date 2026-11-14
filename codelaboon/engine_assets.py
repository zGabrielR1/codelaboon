"""Lazy, pinned native-source assets; engine dependency trees never belong in core."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import requests
from codelaboon.paths import cache_dir

VENDOR = Path(__file__).parent / '_vendor'


def record(engine):
    return json.loads((VENDOR / 'engines.json').read_text())['engines'][engine]


def archive_for(engine):
    info = record(engine)
    sources = [VENDOR / (info['name'] + '.tar.gz')]
    if os.environ.get('CODELABOON_ENGINE_ASSETS'):
        sources.insert(0, Path(os.environ['CODELABOON_ENGINE_ASSETS']) / (info['name'] + '.tar.gz'))
    destination = cache_dir() / 'engine-assets' / info['asset']
    for source in [*sources, destination]:
        if source.is_file():
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != info['sha256']:
                raise RuntimeError('Engine source checksum mismatch: ' + info['name'])
            return source
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.download-', dir=destination.parent)
    try:
        digest = hashlib.sha256()
        with os.fdopen(descriptor, 'wb') as stream, requests.get(info['url'], stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(1024 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        if digest.hexdigest() != info['sha256']:
            raise RuntimeError('Engine source checksum mismatch: ' + info['name'])
        Path(name).replace(destination)
    finally:
        Path(name).unlink(missing_ok=True)
    return destination
