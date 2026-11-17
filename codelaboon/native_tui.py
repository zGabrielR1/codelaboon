"""Launch the vendored OpenCode or OMP source fork in the caller's project."""

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

import requests

from codelaboon.paths import config_dir, development_dir

VENDOR = Path(__file__).resolve().parent / "_vendor"
ENGINES = {"opencode": "opencode", "omp": "oh-my-pi"}


def bun_executable():
    configured = os.environ.get("CODELABOON_BUN")
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())
    found = shutil.which("bun")
    if found:
        return found
    local = development_dir() / "runtime/node_modules/bun/bin"
    executable = local / ("bun.exe" if os.name == "nt" else "bun")
    if executable.is_file():
        return str(executable)
    # The npm Bun wrapper can retain this filename on Linux as well.
    alternate = local / "bun.exe"
    if os.name != "nt" and alternate.is_file() and os.access(alternate, os.X_OK):
        return str(alternate)
    installed = config_dir() / "runtime/bun/node_modules/bun/bin" / ("bun.exe" if os.name == "nt" else "bun")
    if installed.is_file():
        return str(installed)
    alternate = installed.with_name("bun.exe")
    if os.name != "nt" and alternate.is_file() and os.access(alternate, os.X_OK):
        return str(alternate)
    marker = config_dir() / "runtime/native-clis/bun/current.json"
    try:
        candidate = Path(json.loads(marker.read_text())["executable"])
        if candidate.is_relative_to(marker.parent) and candidate.is_file():
            return str(candidate)
    except (OSError, ValueError, KeyError):
        pass
    raise RuntimeError("Bun has not been installed")


def ensure_bun():
    try:
        return bun_executable()
    except RuntimeError:
        from codelaboon.external_engines import setup as install_native
        return str(install_native("bun"))


def source_root(engine):
    name = ENGINES[engine]
    direct = development_dir() / "vendor" / name
    if os.environ.get("CODELABOON_DEV_RUNTIME") == "1" and (direct / "UPSTREAM.json").is_file():
        return direct
    from codelaboon.engine_assets import record, archive_for
    info = record(engine)
    destination = direct if os.environ.get("CODELABOON_DEV_RUNTIME") == "1" else (
        config_dir() / "runtime" / f"{name}-{info['sha256'][:16]}")
    if not (destination / "UPSTREAM.json").is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive = archive_for(engine)
        with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=destination.parent) as temporary:
            staging = Path(temporary) / "source"
            staging.mkdir()
            with tarfile.open(archive) as bundle:
                bundle.extractall(staging, filter="data")
            if not (staging / "UPSTREAM.json").is_file():
                raise RuntimeError(f"Invalid packaged {name} sources")
            try:
                staging.rename(destination)
            except OSError:
                if not (destination / "UPSTREAM.json").is_file():
                    raise
    return destination


def dependency_snapshot(root):
    """Check hoisted package manifests without descending into dependency trees."""
    modules = root / 'node_modules'
    snapshot = {}
    for directory in modules.iterdir():
        if directory.name.startswith('.') or not directory.is_dir():
            continue
        packages = directory.iterdir() if directory.name.startswith('@') else [directory]
        for package in packages:
            manifest = package / 'package.json'
            if not manifest.is_file():
                continue
            with manifest.open('rb') as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024 or b'\0' in raw or not isinstance(json.loads(raw), dict):
                raise ValueError('Invalid runtime dependency manifest: '+str(manifest))
            snapshot[manifest.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
    if not snapshot:
        raise ValueError('Runtime dependencies are missing')
    return snapshot


def check_startup(engine, root, bun):
    """Exercise the actual startup imports before accepting an installation."""
    if engine == 'opencode':
        command = [bun, 'run', '--conditions=browser', '--preload',
                   str(root / 'node_modules/@opentui/solid/scripts/preload.ts'),
                   str(root / 'packages/opencode/src/index.ts'), '--help']
    else:
        command = [bun, str(root / 'packages/coding-agent/src/cli.ts'), '--help']
    env = {**os.environ, 'OPENCODE_DISABLE_MODELS_FETCH':'true',
           'OPENCODE_DISABLE_DEFAULT_PLUGINS':'true', 'OPENCODE_DISABLE_AUTOUPDATE':'true'}
    with tempfile.TemporaryFile() as diagnostic:
        try:
            result = subprocess.run(command, cwd=root, env=env, stdout=subprocess.DEVNULL,
                                    stderr=diagnostic, timeout=60)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('Runtime startup verification timed out; setup was not marked ready') from error
        if result.returncode:
            diagnostic.seek(0, os.SEEK_END)
            diagnostic.seek(max(0, diagnostic.tell()-2048))
            detail = diagnostic.read().decode('utf-8', errors='replace').replace('\0', '<NUL>')
            raise RuntimeError('Runtime startup verification failed; setup was not marked ready. '+detail)


def setup(engine, force=False):
    if engine in ("claude", "kilo", "crush", "jcode", "codex"):
        from codelaboon.external_engines import setup as install_external
        return install_external(engine)
    root = source_root(engine)
    bun = ensure_bun()
    version = subprocess.check_output([bun, "--version"], text=True).strip().split(".")
    if tuple(int(part) for part in version[:3]) < (1, 3, 10):
        raise RuntimeError("The source TUI requires Bun >=1.3.10")
    marker = root / '.codelaboon-ready'
    repair = bool(force)
    if (root / 'node_modules').exists():
        try:
            current = dependency_snapshot(root)
            if marker.is_file():
                previous = json.loads(marker.read_text(encoding='utf-8'))
                repair = repair or bool(previous.get('dependency_manifests') and previous['dependency_manifests'] != current)
        except (OSError, ValueError, AttributeError):
            repair = True
    marker.unlink(missing_ok=True)
    if repair and (root / 'node_modules').exists():
        modules = root / 'node_modules'
        if modules.is_symlink() or modules.resolve().parent != root.resolve():
            raise RuntimeError('Refusing to relocate dependencies outside the selected runtime')
        backup = root / ('.codelaboon-corrupt-dependencies-'+uuid.uuid4().hex)
        modules.rename(backup)
        print('Preserved damaged runtime dependencies at '+str(backup), file=sys.stderr)
    command = [bun, "install", "--ignore-scripts", "--linker", "hoisted"]
    if os.name == 'nt':
        command.extend(['--backend', 'copyfile'])
    if os.environ.get("CODELABOON_DEV_RUNTIME") != "1":
        command.append("--production")
    # Importing only runtime workspaces changes the root manifest. Bun must
    # reconcile the upstream lockfile with that reduced workspace on setup.
    if repair:
        # A hardlinked cache can share the corruption. Never reuse it for repair.
        with tempfile.TemporaryDirectory(prefix='.codelaboon-clean-cache-', dir=root.parent) as cache:
            subprocess.run([*command, '--cache-dir', cache], cwd=root, check=True)
    else:
        subprocess.run(command, cwd=root, check=True)
    if engine == "omp":
        install_omp_native(root)
        subprocess.run([bun, "scripts/generate-docs-index.ts"],
                       cwd=root / "packages/coding-agent", check=True)
    if engine == "opencode":
        # Seed model metadata at installation, never by blocking the first render.
        models = root / ".codelaboon-models.json"
        try:
            response = requests.get("https://models.dev/api.json", timeout=(5, 10))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            data = {}
        models.write_text(json.dumps(data), encoding="utf-8")
    print('Verifying '+engine+' dependency manifests and startup imports...', file=sys.stderr)
    snapshot = dependency_snapshot(root)
    check_startup(engine, root, bun)
    temporary_marker = root / ('.codelaboon-ready-'+uuid.uuid4().hex+'.tmp')
    temporary_marker.write_text(json.dumps({'format':3, 'engine':engine,
        'development':os.environ.get('CODELABOON_DEV_RUNTIME') == '1',
        'dependency_manifests':snapshot})+'\n', encoding='utf-8')
    temporary_marker.replace(marker)


def ready(root):
    try:
        marker = json.loads((root / '.codelaboon-ready').read_text(encoding='utf-8'))
        return marker.get('format') == 3 and marker.get('dependency_manifests') == dependency_snapshot(root)
    except (OSError, ValueError, AttributeError):
        return False


def install_omp_native(root):
    """Use the matching published native addon, verifying npm's SHA-512 digest."""
    version = json.loads((root / "packages/natives/package.json").read_text(encoding="utf-8"))["version"]
    metadata = requests.get(f"https://registry.npmjs.org/@oh-my-pi/pi-natives/{version}", timeout=30)
    metadata.raise_for_status()
    dist = metadata.json()["dist"]
    response = requests.get(dist["tarball"], timeout=120)
    response.raise_for_status()
    algorithm, expected = dist["integrity"].split("-", 1)
    if algorithm != "sha512" or base64.b64encode(hashlib.sha512(response.content).digest()).decode() != expected:
        raise RuntimeError("OMP native package integrity check failed")
    systems = {"Windows": "win32", "Linux": "linux", "Darwin": "darwin"}
    architectures = {"AMD64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}
    tag = f"{systems[platform.system()]}-{architectures[platform.machine()]}"
    with tarfile.open(fileobj=io.BytesIO(response.content)) as archive:
        files = [member for member in archive if member.isfile()
                 and Path(member.name).name.startswith(f"pi_natives.{tag}") and member.name.endswith(".node")]
        if not files:
            raise RuntimeError(f"OMP does not publish a native addon for {tag}")
        native = root / "packages/natives/native"
        native.mkdir(parents=True, exist_ok=True)
        for member in files:
            (native / Path(member.name).name).write_bytes(archive.extractfile(member).read())


def opencode_config(rows, url, token):
    providers = {}
    for api, identifier, package in (("chat", "codelaboon", "@ai-sdk/openai-compatible"),
                                     ("responses", "codelaboon-chatgpt", "@ai-sdk/openai"),
                                     ("anthropic", "codelaboon-claude", "@ai-sdk/anthropic"),
                                     ("google", "codelaboon-gemini", "@ai-sdk/google")):
        models = {row["id"]: {"name": row["name"], "tool_call": True,
                              "limit": {"context": 8192 if row["id"].startswith("local/") else 32768, "output": 4096}}
                  for row in rows if row["api"] == api}
        if models:
            providers[identifier] = {"npm": package, "name": {"chat": "codelaboon", "responses": "ChatGPT",
                                     "anthropic": "Claude", "google": "Gemini"}[api],
                                     "options": {"baseURL": url, "apiKey": token}, "models": models}
    from codelaboon.execution_policy import full_access
    policy={"permission":{"*":"allow","external_directory":"allow"}} if full_access() else {}
    return {**policy,"model": "codelaboon/free", "small_model": "codelaboon/free",
            "autoupdate": False, "share": "disabled", "provider": providers,
            "compaction": {"auto": True, "prune": True, "reserved": 8192}}


def omp_config(rows, url):
    return {"providers": {"codelaboon": {
        "baseUrl": url, "apiKey": "CODELABOON_GATEWAY_TOKEN", "authHeader": True,
        "models": [{"id": row["id"], "name": row["name"],
                    "api": {"responses": "openai-responses", "anthropic": "anthropic-messages",
                            "google": "google-generative-ai"}.get(row["api"], "openai-completions"),
                    "reasoning": False, "input": ["text"],
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    "contextWindow": 8192 if row["id"].startswith("local/") else 32768, "maxTokens": 4096} for row in rows]
    }}}


def launch(engine="opencode", arguments=(), profile="coding", local_only=False, theme=None):
    from codelaboon.execution_policy import profile as task_profile
    profile=task_profile(profile)
    if engine in ("claude", "kilo", "crush", "jcode", "codex"):
        from codelaboon.external_engines import launch as launch_external
        return launch_external(engine, arguments, profile, local_only)
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.native_gateway import serve

    root = source_root(engine)
    if not ready(root):
        print(f"Preparing or repairing {engine} runtime...", file=sys.stderr)
        setup(engine)
    bun = bun_executable()
    project = Path.cwd().resolve()
    cli = CodelaboonCLI()
    cli.load_providers()
    providers = {"local": cli.providers["local"]} if local_only else cli.providers
    from codelaboon.connections import loader
    with serve(providers,reload_providers=loader(cli,set(providers)),task_class='security' if profile=='security' else None) as (gateway, url), tempfile.TemporaryDirectory(prefix="codelaboon-models-") as temporary:
        if sys.stdout.isatty() and sys.stdin.isatty() and arguments[:1] not in (["run"], ("run",)):
            from codelaboon.install import _step
            result = []
            def discover():
                result.extend(gateway.models(startup=True))
                return True, engine
            ok, message = _step("Load coding workspace", discover)
            if not ok:
                raise RuntimeError(message)
            rows = result
        else:
            rows = gateway.models(startup=True)
        if local_only and not rows:
            raise RuntimeError("No local model is listed. Start Ollama/llama.cpp and configure the local provider.")
        default = os.environ.get("CODELABOON_TASK_CHAT_MODEL") or (rows[0]["id"] if local_only else "free")
        env = os.environ.copy()
        env["CODELABOON_GATEWAY_TOKEN"] = gateway.token
        env["CODELABOON_GATEWAY_URL"] = url
        from codelaboon import native_themes
        env["CODELABOON_DEFAULT_THEME"] = native_themes.DEFAULT
        if theme:
            env["CODELABOON_THEME"] = theme
        if engine == "opencode":
            config = opencode_config(rows, url, gateway.token)
            config["model"] = config["small_model"] = "codelaboon/" + default
            if os.environ.get("CODELABOON_TASK_CHAT_MODEL"):
                config["small_model"]="codelaboon/free"
                config["compaction"]["auto"]=False
            if local_only:
                config["enabled_providers"] = ["codelaboon"]
                config["compaction"]["reserved"] = 1024
                for flag in ("MODELS_FETCH", "LSP_DOWNLOAD", "DEFAULT_PLUGINS"):
                    env[f"OPENCODE_DISABLE_{flag}"] = "true"
            if profile == "security":
                config["instructions"] = [str(Path(__file__).parent / "prompts/security.md")]
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
            env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
            env["OPENCODE_DISABLE_MODELS_FETCH"] = "true"
            env["OPENCODE_DISABLE_DEFAULT_PLUGINS"] = "true"
            env["CODELABOON_RUNTIME"] = "1"
            snapshot = root / ".codelaboon-models.json"
            if snapshot.is_file():
                env["OPENCODE_MODELS_PATH"] = str(snapshot)
            state = Path(env.get("CODELABOON_NATIVE_DIR") or config_dir() / "native")
            native_themes.install(engine, state / "config/opencode")
            for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
                env[f"XDG_{kind}_HOME"] = str(state / kind.lower())
            package = root / "packages/opencode"
            command = [bun, "run", "--conditions=browser", "--preload",
                       str(root / "node_modules/@opentui/solid/scripts/preload.ts"), str(package / "src/index.ts")]
            command.extend(arguments if arguments and arguments[0] in ("run", "export", "import", "session")
                           else [str(project), *arguments])
            cwd = project
        else:
            if local_only:
                env["CODELABOON_SMALL_CONTEXT"] = "1"
            models = Path(temporary) / "models.json"
            models.write_text(json.dumps(omp_config(rows, url)), encoding="utf-8")
            env["CODELABOON_MODELS_FILE"] = str(models)
            state = Path(env["CODELABOON_NATIVE_DIR"]) / "omp" if env.get("CODELABOON_NATIVE_DIR") else config_dir() / "omp"
            native_themes.install(engine, state)
            env["PI_CONFIG_DIR"] = str(state)
            env["PI_CODING_AGENT_DIR"] = str(state)
            command = [bun, str(root / "packages/coding-agent/src/cli.ts"),
                       "--model", "codelaboon/" + default, *arguments]
            if profile == "security":
                command.extend(["--append-system-prompt", str(Path(__file__).parent / "prompts/security.md")])
            cwd = project
        try:
            return subprocess.call(command, cwd=cwd, env=env)
        except KeyboardInterrupt:
            return 130
