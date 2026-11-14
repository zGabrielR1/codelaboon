"""Verify the real native terminal UI using tmux and a local fixture model."""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

from native_fixture import ROOT, REPLY, fixture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--engine", choices=["opencode", "omp"], required=True)
parser.add_argument("--width", type=int, default=160)
parser.add_argument("--height", type=int, default=44)
parser.add_argument("--setup", action="store_true")
parser.add_argument("--types", action="store_true", help="Run the engine's own type checks in the prepared source")
args = parser.parse_args()
if not shutil.which("tmux"):
    parser.error("tmux is required for terminal integration checks")

artifacts = ROOT / ".runtime/ui-qa"
artifacts.mkdir(parents=True, exist_ok=True)
name = f"{args.engine}-{args.width}"
socket = "codelaboon-qa-" + uuid.uuid4().hex


def tmux(*argv):
    return subprocess.run(["tmux", "-L", socket, *argv], capture_output=True, text=True, check=True).stdout


def screen(label):
    text = tmux("capture-pane", "-t", "native", "-p")
    (artifacts / f"{name}-{label}.txt").write_text(text, encoding="utf-8")
    return text


def wait(label, predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = screen(label)
        if predicate(text):
            return text
        time.sleep(0.2)
    raise AssertionError(f"{name}: {label} did not reach expected state; see {artifacts / (name + '-' + label + '.txt')}")


def key(*keys):
    tmux("send-keys", "-t", "native", *keys)
    time.sleep(0.15)


def text(value):
    tmux("send-keys", "-t", "native", "-l", value)
    time.sleep(0.25)


with fixture(args.engine, args.setup) as (project, env, observed):
    if args.types:
        helper = ("import json,sys; from codelaboon.native_tui import source_root,bun_executable; "
                  "print(json.dumps([str(source_root(sys.argv[1])),bun_executable()]))")
        root, bun = json.loads(subprocess.check_output([sys.executable, "-c", helper, args.engine], cwd=ROOT, env=env, text=True))
        check = "check:ts" if args.engine == "omp" else "typecheck"
        directory = Path(root) if args.engine == "omp" else Path(root) / "packages/opencode"
        subprocess.run([bun, "run", check], cwd=directory, env=env, check=True, timeout=180)
    command = ["env", f"CODELABOON_CONFIG_DIR={env['CODELABOON_CONFIG_DIR']}",
               "CODELABOON_NO_ANIMATION=1", "COLORTERM=truecolor",
               sys.executable, str(ROOT / "codelaboon/cli.py"), "tui", "--engine", args.engine,
               "--local-only"]
    if args.width == 80:
        command.extend(["--theme", "codelaboon-kilo"])
    try:
        tmux("-f", "/dev/null", "new-session", "-d", "-s", "native", "-x", str(args.width),
             "-y", str(args.height), "-c", str(project), shlex.join(command))
        tmux("set-option", "-t", "native", "remain-on-exit", "on")
        wait("home", lambda value: "fixture" in value and ("c o d e l a b o o n" in value if args.engine == "opencode" else "omp" in value.lower()))
        # Type and submit separately so terminal paste coalescing cannot swallow Enter.
        prompt = "native-ui-history-check"
        text(prompt)
        key("Enter")
        wait("reply", lambda value: REPLY in value)
        if args.engine == "omp":
            profile = Path(env["CODELABOON_CONFIG_DIR"]) / "omp"
            assert (profile / "logs").is_dir(), "OMP logs escaped the Codelaboon profile"
            assert list(profile.rglob("*.jsonl")), "OMP session was not persisted in the Codelaboon profile"
        key("Up")
        wait("history", lambda value: value.count(prompt) >= 2)
        if args.engine == "opencode" and args.width >= 140:
            wait("sidebar", lambda value: "Delegated work" in value and "Background agent" in value)
        key("C-e")
        key("C-u")
        if args.engine == "opencode":
            key("C-p")
            wait("commands", lambda value: "Commands" in value and "Search" in value)
            text("theme")
            key("Enter")
            wait("themes", lambda value: "Themes" in value and "codelaboon-kilo" in value)
        else:
            text("/settings")
            key("Enter")
            wait("settings", lambda value: "Appearance" in value and "Dark Theme" in value)
            key("Enter")
            wait("themes", lambda value: "codelaboon-kilo" in value)
        assert any(body.get("messages") for body in observed), "The fixture never received a native model request"
        key("Escape")
        result = {"engine": args.engine, "width": args.width, "height": args.height,
                  "home": True, "response": True, "prompt_recall": True, "theme_picker": True,
                  "native_model_requests": len(observed)}
        (artifacts / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("PASS " + json.dumps(result))
    finally:
        subprocess.run(["tmux", "-L", socket, "kill-server"], capture_output=True)
