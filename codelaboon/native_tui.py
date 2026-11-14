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

import requests

from codelaboon.paths import config_dir

VENDOR = Path(__file__).resolve().parent / "_vendor"
ENGINES = {"opencode": "opencode", "omp": "oh-my-pi"}


def bun_executable():
    configured = os.environ.get("CODELABOON_BUN")
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())
    found = shutil.which("bun")
    if found:
        return found
    local = Path(__file__).resolve().parent.parent / ".runtime/node_modules/bun/bin"
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
    raise RuntimeError("The source TUI needs Bun >=1.3.10. Install Bun, then run codelaboon tui --setup.")


def ensure_bun():
    try:
        return bun_executable()
    except RuntimeError:
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("Install Bun >=1.3.10 or Node.js with npm, then retry the installer.")
        subprocess.run([npm, "install", "--prefix", str(config_dir() / "runtime/bun"),
                        "--no-audit", "--no-fund", "bun@1.4.4"], check=True)
        return bun_executable()


def source_root(engine):
    name = ENGINES[engine]
    direct = VENDOR / name
    if (direct / "UPSTREAM.json").is_file():
        return direct
    archive = VENDOR / f"{name}.tar.gz"
    if not archive.is_file():
        raise RuntimeError(f"Missing packaged {name} sources; reinstall codelaboon.")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
    destination = config_dir() / "runtime" / f"{name}-{digest}"
    if not (destination / "UPSTREAM.json").is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
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


def setup(engine):
    root = source_root(engine)
    bun = ensure_bun()
    version = subprocess.check_output([bun, "--version"], text=True).strip().split(".")
    if tuple(int(part) for part in version[:3]) < (1, 3, 10):
        raise RuntimeError("The source TUI requires Bun >=1.3.10")
    command = [bun, "install", "--ignore-scripts", "--backend", "copyfile", "--linker", "hoisted"]
    # Importing only runtime workspaces changes the root manifest. Bun must
    # reconcile the upstream lockfile with that reduced workspace on setup.
    subprocess.run(command, cwd=root, check=True)
    if engine == "omp":
        install_omp_native(root)
        subprocess.run([bun, "scripts/generate-docs-index.ts"],
                       cwd=root / "packages/coding-agent", check=True)
    (root / ".codelaboon-ready").write_text("ready\n", encoding="utf-8")


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
    return {"model": "codelaboon/free", "small_model": "codelaboon/free",
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
    from codelaboon.cli import CodelaboonCLI
    from codelaboon.native_gateway import serve

    root = source_root(engine)
    bun = bun_executable()
    if not (root / ".codelaboon-ready").is_file():
        raise RuntimeError(f"Run codelaboon tui --engine {engine} --setup once to install the source TUI dependencies.")
    project = Path.cwd().resolve()
    cli = CodelaboonCLI()
    cli.load_providers()
    providers = {"local": cli.providers["local"]} if local_only else cli.providers
    with serve(providers) as (gateway, url), tempfile.TemporaryDirectory(prefix="codelaboon-models-") as temporary:
        if sys.stdout.isatty() and sys.stdin.isatty() and arguments[:1] not in (["run"], ("run",)):
            from codelaboon.install import _step
            result = []
            def discover():
                result.extend(gateway.models())
                return True, engine
            ok, message = _step("Load coding workspace", discover)
            if not ok:
                raise RuntimeError(message)
            rows = result
        else:
            rows = gateway.models()
        if local_only and not rows:
            raise RuntimeError("No local model is listed. Start Ollama/llama.cpp and configure the local provider.")
        default = rows[0]["id"] if local_only else "free"
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
            if local_only:
                config["enabled_providers"] = ["codelaboon"]
                config["compaction"]["reserved"] = 1024
                for flag in ("MODELS_FETCH", "LSP_DOWNLOAD", "DEFAULT_PLUGINS"):
                    env[f"OPENCODE_DISABLE_{flag}"] = "true"
            if profile == "security":
                config["instructions"] = [str(Path(__file__).parent / "prompts/security.md")]
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
            env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
            state = Path(env.get("CODELABOON_NATIVE_DIR") or config_dir() / "native")
            native_themes.install(engine, state / "config/opencode")
            for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
                env[f"XDG_{kind}_HOME"] = str(state / kind.lower())
            package = root / "packages/opencode"
            command = [bun, "run", "--conditions=browser", "--preload",
                       str(root / "node_modules/@opentui/solid/scripts/preload.ts"), str(package / "src/index.ts")]
            command.extend(arguments if arguments[:1] == ["run"] or arguments[:1] == ("run",)
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
