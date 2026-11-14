"""Optional upstream native CLIs, downloaded unchanged and checksum verified."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import requests

from codelaboon.paths import config_dir

CLAUDE_RELEASES = "https://downloads.claude.ai/claude-code-releases"
KILO_VERSION = "7.8.27"


def target(engine):
    systems = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}
    architectures = {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64", "arm64": "arm64"}
    try:
        system, arch = systems[platform.system()], architectures[platform.machine()]
    except KeyError as error:
        raise RuntimeError("This platform does not have a supported native CLI build") from error
    musl = system == "linux" and platform.libc_ver()[0] == "musl"
    if engine == "claude" and system == "windows":
        system = "win32"
    if engine == "bun":
        arch = "aarch64" if arch == "arm64" else arch
        return f"{system}-{arch}" + ("-musl" if musl else "") + ("-baseline" if arch == "x64" else "")
    suffix = "-baseline" if engine == "kilo" and arch == "x64" else ""
    return f"{system}-{arch}{suffix}" + ("-musl" if musl else "")


def metadata(url):
    with requests.get(url, timeout=(10, 30)) as response:
        response.raise_for_status()
        return response.json()


def setup(engine):
    if engine not in ("kilo", "claude", "bun"):
        raise ValueError("Unknown optional engine")
    directory = config_dir() / "runtime" / "native-clis" / engine
    directory.mkdir(parents=True, exist_ok=True)
    system = target(engine)
    if engine == "claude":
        with requests.get(CLAUDE_RELEASES + "/stable", timeout=(10, 30)) as response:
            response.raise_for_status()
            version = response.text.strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise RuntimeError("Claude Code returned an invalid release version")
        release = metadata(f"{CLAUDE_RELEASES}/{version}/manifest.json")["platforms"][system]
        url = f"{CLAUDE_RELEASES}/{version}/{system}/claude" + (".exe" if os.name == "nt" else "")
        digest = release["checksum"]
        algorithm = "sha256"
    else:
        version = "1.4.4" if engine == "bun" else KILO_VERSION
        package = f"@oven/bun-{system}" if engine == "bun" else f"@kilocode/cli-{system}"
        release = metadata(f"https://registry.npmjs.org/{package}/{version}")["dist"]
        url = release["tarball"]
        algorithm, digest = release["integrity"].split("-", 1)
        if algorithm != "sha512":
            raise RuntimeError(f"{engine} package does not provide the expected SHA-512 integrity")
    destination = directory / f"{version}-{system}"
    binary_name = engine + (".exe" if os.name == "nt" else "")
    print(f"Downloading verified {engine} {version} ({system})...", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix=".install-", dir=directory) as temporary:
        staging = Path(temporary)
        download = staging / "download"
        hasher = hashlib.new(algorithm)
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with download.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    hasher.update(chunk)
                    stream.write(chunk)
        actual = hasher.hexdigest() if engine == "claude" else base64.b64encode(hasher.digest()).decode()
        if actual != digest:
            raise RuntimeError(f"{engine} download checksum mismatch")
        content = staging / "content"
        content.mkdir()
        if engine == "claude":
            shutil.move(download, content / binary_name)
        else:
            with tarfile.open(download) as archive:
                archive.extractall(content, filter="data")
        candidates = [file for file in content.rglob(binary_name) if file.is_file()]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one {engine} executable in the verified package")
        relative = candidates[0].relative_to(content)
        candidates[0].chmod(0o755)
        subprocess.run([str(candidates[0]), "--version"], check=True, capture_output=True, timeout=30)
        if not destination.exists():
            content.rename(destination)
        record = {"engine": engine, "version": version, "platform": system, "url": url,
                  "integrity": algorithm + ":" + digest, "executable": str(destination / relative)}
        marker = staging / "current.json"
        marker.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        marker.replace(directory / "current.json")
    return destination / relative


def executable(engine):
    existing = shutil.which(engine)
    if existing:
        return existing
    marker = config_dir() / "runtime/native-clis" / engine / "current.json"
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        path = Path(data["executable"])
        if path.is_relative_to(marker.parent) and path.is_file():
            return str(path)
    except (OSError, ValueError, KeyError):
        pass
    print(f"Installing optional {engine} native CLI...", file=sys.stderr, flush=True)
    return str(setup(engine))


def launch(engine, arguments=(), profile="coding", local_only=False):
    binary = executable(engine)
    if arguments[:1] in (["--version"], ("--version",), ["--help"], ("--help",)):
        return subprocess.call([binary, *arguments])
    if engine == "claude" and arguments[:1] in (["auth"], ("auth",)):
        return subprocess.call([binary, *arguments])
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.native_gateway import serve
    from codelaboon.native_tui import opencode_config
    cli = CodelaboonCLI()
    cli.load_providers()
    providers = {"local": cli.providers["local"]} if local_only else cli.providers
    if engine == "claude" and not local_only:
        from codelaboon.native_gateway import FREE_COMPATIBLE
        providers = {name: provider for name, provider in providers.items()
                     if name in FREE_COMPATIBLE or name == "local"}
    with serve(providers) as (gateway, url):
        rows = gateway.models(startup=True)
        if not rows:
            raise RuntimeError("No model is listed for this session")
        if engine == "claude":
            from codelaboon.claude_engine import launch as launch_claude
            return launch_claude(binary, arguments, profile, local_only, rows, url, gateway.token)
        config = opencode_config(rows, url, gateway.token)
        default = rows[0]["id"] if local_only else "free"
        config["model"] = config["small_model"] = "codelaboon/" + default
        config["enabled_providers"] = list(config["provider"])
        if profile == "security":
            config["instructions"] = [str(Path(__file__).parent / "prompts/security.md")]
        env = dict(os.environ, KILO_CONFIG_CONTENT=json.dumps(config), KILO_DISABLE_AUTOUPDATE="true",
                   KILO_DISABLE_MODELS_FETCH="true", KILO_DISABLE_DEFAULT_PLUGINS="true")
        for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
            env[f"XDG_{kind}_HOME"] = str(config_dir() / "kilo" / kind.lower())
        command = [binary, *arguments]
        if arguments[:1] in (["run"], ("run",)) and not any(
                argument == "--dir" or argument.startswith("--dir=") for argument in arguments):
            command[2:2] = ["--dir", str(Path.cwd().resolve())]
        return subprocess.call(command, env=env)
