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
import zipfile

import requests

from codelaboon.paths import config_dir

CLAUDE_RELEASES = "https://downloads.claude.ai/claude-code-releases"
KILO_VERSION = "7.8.27"
CRUSH_VERSION = "0.101.0"
JCODE_VERSION = "0.99.1"
CODEX_VERSION = "0.169.0"


def target(engine):
    systems = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}
    architectures = {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64", "arm64": "arm64", "ARM64": "arm64"}
    try:
        system, arch = systems[platform.system()], architectures[platform.machine()]
    except KeyError as error:
        raise RuntimeError("This platform does not have a supported native CLI build") from error
    if engine in ("crush", "jcode", "devin"):
        return f"{system}-{arch}"
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
    if engine not in ("kilo", "claude", "bun", "crush", "jcode", "codex", "devin"):
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
    elif engine == "devin":
        from urllib.parse import urlsplit
        manifest=metadata('https://static.devin.ai/cli/current/manifest.json')
        version=manifest.get('version','')
        if not isinstance(version,str) or not re.fullmatch(r'[0-9][A-Za-z0-9._-]{0,79}',version):raise RuntimeError('Invalid Devin release version')
        operating_system,architecture=system.split('-',1)
        architecture='x86_64' if architecture=='x64' else 'aarch64'
        native=architecture+'-'+{'linux':'unknown-linux','darwin':'apple-darwin','windows':'pc-windows'}[operating_system]
        release=manifest['platforms'][native];url=release['url'];digest=release.get('sha256','');algorithm='sha256'
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname!='static.devin.ai' or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.startswith('/cli/'+version+'/'):raise RuntimeError('Unexpected Devin release asset host/path')
        if not re.fullmatch(r'[a-fA-F0-9]{64}',digest):raise RuntimeError('Devin release lacks a valid checksum')
    elif engine == "codex":
        version = CODEX_VERSION
        arch = "aarch64" if platform.machine() in ("aarch64", "arm64") else "x86_64"
        package = "@openai/codex-" + ({"Linux":"linux","Darwin":"darwin","Windows":"win32"}[platform.system()]) + "-" + ("arm64" if arch=="aarch64" else "x64")
        release = metadata(f"https://registry.npmjs.org/@openai/codex/{version}-" + package.removeprefix("@openai/codex-"))["dist"]
        url = release["tarball"]
        algorithm, digest = release["integrity"].split("-",1)
        if algorithm != "sha512": raise RuntimeError("Codex package lacks SHA-512 integrity")
    elif engine == "jcode":
        version = JCODE_VERSION
        operating_system, architecture = system.split("-", 1)
        operating_system = "macos" if operating_system == "darwin" else operating_system
        architecture = "x86_64" if architecture == "x64" else "aarch64"
        filename = f"jcode-{operating_system}-{architecture}.tar.gz"
        base = f"https://github.com/1jehuang/jcode/releases/download/v{version}"
        with requests.get(base + "/SHA256SUMS", timeout=(10, 30)) as response:
            response.raise_for_status()
            digest = next((line.split()[0] for line in response.text.splitlines()
                           if len(line.split()) == 2 and line.split()[1] == filename), "")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise RuntimeError("Jcode release has no valid checksum for this platform")
        algorithm, url = "sha256", base + "/" + filename
    elif engine == "crush":
        version = CRUSH_VERSION
        system_name, architecture = system.split("-", 1)
        architecture = "x86_64" if architecture == "x64" else architecture
        suffix = "zip" if system_name == "windows" else "tar.gz"
        filename = f"crush_{version}_{system_name.title()}_{architecture}.{suffix}"
        base = f"https://github.com/charmbracelet/crush/releases/download/v{version}"
        with requests.get(base + "/checksums.txt", timeout=(10, 30)) as response:
            response.raise_for_status()
            digest = next((line.split()[0] for line in response.text.splitlines()
                           if len(line.split()) == 2 and line.split()[1] == filename), "")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise RuntimeError("Crush release has no valid checksum for this platform")
        algorithm, url = "sha256", base + "/" + filename
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
        actual = hasher.hexdigest() if algorithm == "sha256" else base64.b64encode(hasher.digest()).decode()
        if actual != digest:
            raise RuntimeError(f"{engine} download checksum mismatch")
        content = staging / "content"
        content.mkdir()
        if engine == "claude":
            shutil.move(download, content / binary_name)
        elif engine in ("crush","devin") and system.startswith("windows-"):
            with zipfile.ZipFile(download) as archive:
                for member in archive.infolist():
                    if not (content / member.filename).resolve().is_relative_to(content.resolve()):
                        raise RuntimeError("Unsafe path in Crush archive")
                archive.extractall(content)
        else:
            with tarfile.open(download) as archive:
                archive.extractall(content, filter="data")
        candidates = [file for file in content.rglob(binary_name) if file.is_file()]
        if engine == "jcode" and not candidates:
            native = list(content.rglob("jcode-*.exe" if os.name == "nt" else "jcode-*.bin"))
            if len(native) == 1:
                native[0].rename(content / binary_name)
                candidates = [content / binary_name]
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
    if engine == "jcode" and os.environ.get("CODELABOON_JCODE_BIN"):
        return str(Path(os.environ["CODELABOON_JCODE_BIN"]).resolve())
    existing = None if engine == "jcode" else shutil.which(engine)
    if existing and engine == "crush":
        try:
            with Path(existing).open("rb") as stream:
                scripted = stream.read(2) == b"#!"
            version = subprocess.check_output([existing, "--version"], text=True, timeout=10) if not scripted else ""
            if not re.search(r"\bv?" + re.escape(CRUSH_VERSION) + r"\b", version):
                existing = None
        except (OSError, subprocess.SubprocessError):
            existing = None
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
    from codelaboon.execution_policy import profile as task_profile
    profile=task_profile(profile)
    binary = executable(engine)
    if arguments[:1] in (["--version"], ("--version",), ["--help"], ("--help",)) or (
            engine == "crush" and any(flag in arguments for flag in ("--help", "-h"))):
        return subprocess.call([binary, *arguments])
    if engine == "claude" and arguments[:1] in (["auth"], ("auth",)):
        return subprocess.call([binary, *arguments])
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.native_gateway import serve
    from codelaboon.native_tui import opencode_config
    cli = CodelaboonCLI()
    cli.load_providers()
    providers = {"local": cli.providers["local"]} if local_only else cli.providers
    if engine in ("claude", "crush", "jcode", "codex") and not local_only:
        from codelaboon.native_gateway import COMPATIBLE
        providers = {name: provider for name, provider in providers.items()
                     if name in COMPATIBLE}
    with serve(providers,task_class='security' if profile=='security' else None) as (gateway, url):
        rows = gateway.models(startup=True)
        if not rows:
            raise RuntimeError("No model is listed for this session")
        if engine == "codex":
            from codelaboon.codex_engine import launch as launch_codex
            return launch_codex(binary, arguments, profile, local_only, rows, url, gateway.token)
        if engine == "jcode":
            from codelaboon.jcode_engine import launch as launch_jcode
            return launch_jcode(binary, arguments, profile, local_only, rows, url, gateway.token)
        if engine == "crush":
            from codelaboon.crush_engine import launch as launch_crush
            return launch_crush(binary, arguments, profile, local_only, rows, url, gateway.token)
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
