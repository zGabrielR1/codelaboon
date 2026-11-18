"""Queue and report resumable regression repairs in detached Git worktrees."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import subprocess
import tempfile
import uuid


def git(project, *args, **kwargs):
    return subprocess.run(["git", "-C", str(project), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, **kwargs).stdout


def isolated_command(argv):
    return ["xvfb-run", "-a", "dbus-run-session", sys.executable, str(Path(__file__).resolve()), "--isolated-child", *argv]


def handoff(project, attempt, record, spec, checkpoint=None):
    from codelaboon.watch import save
    with tempfile.TemporaryDirectory() as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        git(project, "read-tree", "HEAD", env=env)
        git(project, "add", "-A", env=env)
        patch = git(project, "diff", "--cached", "--binary", spec["base"], "--", env=env)
        (attempt / "repair.patch").write_bytes(patch)
    images = {}
    if spec.get("gui"):
        before = attempt / "gui-before" / "frame.png"
        if checkpoint and checkpoint.is_file():
            before = Path(json.loads(checkpoint.read_text(encoding="utf-8"))["screenshot"])
        for label, frame in (("before", before), ("after", attempt / "gui-after" / "frame.png")):
            if frame.is_file():
                images[label] = f"{label}.png"
                shutil.copyfile(frame, attempt / images[label])
    save(attempt / "handoff.json", {
        "base": spec["base"], "worktree": str(project), "status": record["status"],
        "verification": record.get("verification"), "checks": record.get("checks", []),
        "failure": record.get("failure_kind"), "screenshots": images, "patch": "repair.patch", "worker_log": "output.log",
    })


def main(argv=None):
    parser = argparse.ArgumentParser(prog="codelaboon regression")
    parser.add_argument("objective", nargs="?")
    parser.add_argument("--report", metavar="ID", help="Print the latest handoff for a queued regression")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path)
    parser.add_argument("--reproduce", help="Command expected to fail before repair")
    parser.add_argument("--check", action="append", default=[])
    parser.add_argument("--gui-spec", type=Path, help="JSON build, launch, and accessibility flow")
    parser.add_argument("--model", default="free")
    parser.add_argument("--fallback-model", action="append", default=[])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--desktop", choices=("none", "foreground", "isolated"), default="none")
    args = parser.parse_args(argv)
    from codelaboon import work
    from codelaboon.paths import config_dir
    from codelaboon.work_queue import validate_swarm
    try:
        config = args.config or config_dir() / "work.json"
        if args.report:
            _, _, runtime = work.configuration(config)
            state = json.loads((runtime / "state.json").read_text(encoding="utf-8"))
            location = state.get("last_attempts", {}).get(args.report)
            if location is None:
                raise ValueError("No completed attempt is available for this regression")
            attempt = Path(location).resolve()
            if not attempt.is_relative_to(runtime.resolve()):
                raise ValueError("Invalid regression attempt location")
            report = json.loads((attempt / "handoff.json").read_text(encoding="utf-8"))
            print(json.dumps({"attempt": str(attempt), **report}, indent=2))
            return
        if not args.objective or bool(args.reproduce) == bool(args.gui_spec) or (not args.gui_spec and not args.check):
            parser.error("Provide an objective and either --gui-spec or --reproduce with --check")
        gui = None
        if args.gui_spec:
            from codelaboon.gui_regression import validate
            gui = validate(json.loads(args.gui_spec.read_text(encoding="utf-8")))
            if args.desktop == "foreground":
                raise ValueError("GUI flows run on an isolated display.")
            args.desktop = "isolated"
        reproduce = shlex.split(args.reproduce) if args.reproduce else []
        checks = [shlex.split(value) for value in args.check]
        if (not reproduce and not gui) or not all(checks) or args.attempts < 1:
            raise ValueError("Provide nonempty commands and a positive attempt limit")
        if not gui and args.desktop != "none" and any("/" not in model for model in [args.model, *args.fallback_model]):
            raise ValueError("Desktop repairs require explicit vision-capable provider/model routes")
        if args.desktop == "isolated" and (not sys.platform.startswith("linux") or not all(shutil.which(name) for name in ("xvfb-run", "dbus-run-session"))):
            raise ValueError("Isolated desktop jobs require Linux, xvfb-run, and dbus-run-session")
        options = validate_swarm(dict(model=args.model, controller="worker", cycles=1,
                                      interval=60, workers=args.workers, timeout=args.timeout,
                                      foreground_desktop=args.desktop != "none" and all(
                                          "/" in model for model in [args.model, *args.fallback_model])))
        project = args.project.resolve()
        base = git(project, "rev-parse", "HEAD").decode().strip()
        if not config.exists():
            work.initialize(config)
        _, _, runtime = work.configuration(config)
        directory = runtime / "regressions" / uuid.uuid4().hex
        directory.mkdir(parents=True, mode=0o700)
        tree = directory / "repair"
        created = []
        try:
            supporting = [directory / role for role in ("diagnosis", "review")][:args.workers - 1]
            for checkout in (tree, *supporting):
                git(project, "worktree", "add", "--detach", str(checkout), base)
                created.append(checkout)
            spec = {"base": base, "reproduce": reproduce, "attempts": args.attempts,
                    "fallback_models": args.fallback_model, "isolated": args.desktop == "isolated",
                    "supporting": [str(checkout) for checkout in supporting]}
            if gui:
                spec["gui"] = gui
            acceptance = [reproduce, *(check for check in checks if check != reproduce)] if reproduce else checks
            if gui:
                acceptance = [["Build → Launch → Verify"], *checks]
            task_id = work.add(tree, args.objective, acceptance, config, swarm=options, regression=spec)
        except Exception:
            for checkout in reversed(created):
                git(project, "worktree", "remove", str(checkout))
            raise
        work.start(config)
        print(f"Regression {task_id} in {tree}. Review attempts under {runtime}.")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")


def start_accessibility():
    launcher = Path("/usr/libexec/at-spi-bus-launcher")
    registry = Path("/usr/libexec/at-spi2-registryd")
    if not (launcher.is_file() and registry.is_file()):
        return
    try:
        from gi.repository import Gio, GLib
    except ImportError:
        return
    subprocess.Popen([str(launcher), "--launch-immediately"], stdin=subprocess.DEVNULL)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    for _ in range(20):
        try:
            address, = bus.call_sync("org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus", "GetAddress",
                                     None, None, Gio.DBusCallFlags.NO_AUTO_START, 1000, None).unpack()
            break
        except GLib.Error:
            GLib.usleep(25_000)
    else:
        return
    os.environ["AT_SPI_BUS_ADDRESS"] = address
    subprocess.Popen([str(registry)], stdin=subprocess.DEVNULL)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--isolated-child"]:
        os.environ.update(CODELABOON_ISOLATED_DISPLAY=os.environ["DISPLAY"],
                          XDG_SESSION_TYPE="x11", GDK_BACKEND="x11", QT_QPA_PLATFORM="xcb")
        for key in ("WAYLAND_DISPLAY", "AT_SPI_BUS_ADDRESS", "NO_AT_BRIDGE"):
            os.environ.pop(key, None)
        start_accessibility()
        os.execvp(sys.argv[2], sys.argv[2:])
    main()
