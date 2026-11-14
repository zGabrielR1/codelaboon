"""Download a pinned CPU runtime and small routing model into .watch only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import platform
from pathlib import Path
import urllib.request
import zipfile
import tarfile

ROOT = Path(__file__).resolve().parent.parent / '.watch' / 'local'
ASSETS = [
    ('llama.zip', 'https://github.com/ggml-org/llama.cpp/releases/download/b12360/llama-b12360-bin-win-cpu-x64.zip',
     'eae1726047e0eaa707b1302929d196c999b96c2f243b21aea6e93bcebacc4e17'),
    ('router.gguf', 'https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf',
     '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'),
]
LINUX = ('llama-linux.tar.gz',
         'https://github.com/ggml-org/llama.cpp/releases/download/b12360/llama-b12360-bin-ubuntu-x64.tar.gz',
         'b60dc211e4ba206bb04bbc9eb06294364c43d0aab8fc308c44a361477466ba4c')


def download(asset):
    name, url, digest = asset
    target = ROOT / name
    if target.exists():
        with target.open('rb') as existing:
            if hashlib.file_digest(existing, 'sha256').hexdigest() == digest:
                return
    temporary = target.with_suffix('.part')
    print('Downloading ' + name, flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    with temporary.open('rb') as content:
        if hashlib.file_digest(content, 'sha256').hexdigest() != digest:
            raise ValueError('Checksum mismatch: ' + name)
    temporary.replace(target)
    print('Verified ' + name, flush=True)


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    for project in ('demo-clamp', 'demo-slug'):
        (ROOT.parent / project).mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assets = ASSETS if os.name == 'nt' else ASSETS[1:]
        if platform.system() == 'Linux' and platform.machine() == 'x86_64':
            assets = [LINUX, *ASSETS[1:]]
        list(pool.map(download, assets))
    if os.name != 'nt':
        if platform.system() == 'Linux' and platform.machine() == 'x86_64':
            destination = ROOT / 'llama-linux'
            destination.mkdir(exist_ok=True)
            with tarfile.open(ROOT / 'llama-linux.tar.gz') as archive:
                archive.extractall(destination, filter='data')
            print('Verified Linux CPU runtime and model. Run codelaboon work init, then work enable.')
            raise SystemExit(0)
        print('Verified routing model. Install a native llama-server on PATH, then run codelaboon work start.')
        raise SystemExit(0)
    destination = ROOT / 'llama'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT / 'llama.zip') as archive:
        for member in archive.infolist():
            if not (destination / member.filename).resolve().is_relative_to(destination.resolve()):
                raise ValueError('Unsafe archive path')
        archive.extractall(destination)
    print('Local orchestrator installed in ' + str(ROOT))
