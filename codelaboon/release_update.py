"""Install the newest Codelaboon release wheel after verifying its checksum."""
import hashlib
import json
from pathlib import Path
import re
import tempfile

import requests

REPOSITORY = 'zGabrielR1/codelaboon'
DOWNLOAD = 'https://github.com/'+REPOSITORY+'/releases/download/'


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-?rc\.?([0-9]+))?', value)
    if not match:
        raise ValueError('Unsupported release version')
    major, minor, patch, rc = match.groups()
    return (int(major), int(minor), int(patch), int(rc is None), int(rc or 0))


def download(url, limit):
    with requests.get(url, stream=True, timeout=(10, 60)) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > limit:
                raise ValueError('Release download exceeds its size limit')
            chunks.append(chunk)
    return b''.join(chunks)


def install_latest():
    from codelaboon import __version__
    from codelaboon.install import install_package
    releases = json.loads(download('https://api.github.com/repos/'+REPOSITORY+'/releases?per_page=20', 2*1024*1024))
    if not isinstance(releases, list):
        raise ValueError('Invalid GitHub release listing')
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        try:
            key = version(release['tag_name'])
        except (ValueError, KeyError, TypeError):
            continue
        if key > version(__version__):
            candidates.append((key, release))
    if not candidates:
        return True, 'Already at or above the newest published release'
    _, release = max(candidates, key=lambda row: row[0])
    tag = release['tag_name']
    assets = release.get('assets', [])
    wheel_version = tag.removeprefix('v').replace('-rc.', 'rc').replace('-rc', 'rc')
    name = f'codelaboon-{wheel_version}-py3-none-any.whl'
    expected = {name, 'SHA256SUMS'}
    for asset in assets:
        if asset.get('name') in expected:
            if asset.get('browser_download_url') != DOWNLOAD+tag+'/'+asset['name']:
                raise ValueError('Release asset URL is outside the expected repository')
            expected.remove(asset['name'])
    if expected:
        raise ValueError('The selected release is missing its wheel or checksum manifest')
    manifest = download(DOWNLOAD+tag+'/SHA256SUMS', 65536).decode('utf-8')
    hashes = []
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == name:
            hashes.append(parts[0])
    if len(hashes) != 1 or not re.fullmatch('[0-9a-fA-F]{64}', hashes[0]):
        raise ValueError('Release wheel has no unique SHA256 checksum')
    raw = download(DOWNLOAD+tag+'/'+name, 1024*1024)
    if hashlib.sha256(raw).hexdigest() != hashes[0].lower():
        raise ValueError('Release wheel checksum mismatch; installation stopped')
    with tempfile.TemporaryDirectory(prefix='codelaboon-update-') as directory:
        path = Path(directory)/name
        path.write_bytes(raw)
        code, output = install_package(artifact=path, quiet=True)
    if code:
        return False, '\n'.join(output.splitlines()[-12:])
    return True, 'Installed '+tag+' (SHA256 verified)'
