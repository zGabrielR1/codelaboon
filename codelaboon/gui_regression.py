"""Build and independently verify a native GUI flow on a private Linux display."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from codelaboon.desktop_accessibility import Accessibility
from codelaboon.x11_desktop import X11Desktop
from codelaboon.watch import save


def validate(spec):
    if not isinstance(spec, dict) or set(spec) != {"build", "launch", "steps"}:
        raise ValueError("GUI specification requires build, launch, and steps.")
    for field in ("build", "launch"):
        argv = spec[field]
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg for arg in argv):
            raise ValueError(f"{field} must be a nonempty argument array.")
    steps = spec["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 50:
        raise ValueError("Provide 1–50 GUI steps.")
    for step in steps:
        if (not isinstance(step, dict) or set(step) != {"action", "name"}
                or step["action"] not in ("click", "expect", "expect_absent")
                or not isinstance(step["name"], str) or not 1 <= len(step["name"]) <= 160):
            raise ValueError("Each step requires click, expect, or expect_absent and an accessible name.")
    if steps[-1]["action"] == "click":
        raise ValueError("Finish the flow with an assertion.")
    return spec


def command(spec, destination):
    from codelaboon.regression import isolated_command
    destination.mkdir(mode=0o700)
    save(destination / "spec.json", spec)
    source = str(Path(__file__).resolve().parent.parent)
    bootstrap = f"import sys; sys.path.insert(0, {source!r}); from codelaboon.gui_regression import main; main()"
    return isolated_command([sys.executable, "-c", bootstrap, str(destination)])


def activation(node):
    return next((index for index, label in enumerate(node["actions"])
                 if label in ("click", "press", "activate")), None)


def run(spec, destination):
    if not os.environ.get("CODELABOON_ISOLATED_DISPLAY"):
        raise RuntimeError("GUI verification requires a private display.")
    state = {"phase": "building", "step": 0, "steps": len(spec["steps"]), "target": spec["launch"][0]}
    save(destination / "live.json", state)
    desktop = app = None

    def update(phase, message="", capture=False):
        if capture:
            temporary = destination / "frame.tmp"
            desktop.screenshot().save(temporary, format="PNG")
            temporary.replace(destination / "frame.png")
            state["frame"] = uuid.uuid4().hex
        state.update(phase=phase, message=message)
        save(destination / "live.json", state)

    try:
        subprocess.run(spec["build"], check=True, stdin=subprocess.DEVNULL)
        update("launching")
        desktop = X11Desktop()
        app = subprocess.Popen(spec["launch"], stdin=subprocess.DEVNULL)
        tree = Accessibility()

        def operator():
            if not (destination / "hold").exists():
                return
            update("paused", "Operator owns the private display", capture=True)
            while (destination / "hold").exists():
                request = destination / "input.json"
                if request.is_file():
                    try:
                        action = json.loads(request.read_text(encoding="utf-8"))
                        if action["frame"] == state["frame"]:
                            width, height = desktop.size()
                            x, y = action["x"], action["y"]
                            if 0 <= x < width and 0 <= y < height:
                                desktop.click(x, y)
                                update("paused", "Operator click applied", capture=True)
                    finally:
                        request.unlink(missing_ok=True)
                time.sleep(.1)
            raise InterruptedError("Operator returned control. Relaunching for independent verification.")

        def observe():
            operator()
            if app.poll() is not None:
                raise RuntimeError(f"App exited during verification ({app.returncode}).")
            return tree.observe(process_id=app.pid)

        def wait_for(match):
            deadline = time.monotonic() + 8
            while True:
                observed = observe()
                result = match(observed)
                if result or time.monotonic() >= deadline:
                    return result
                time.sleep(.15)

        if not wait_for(bool):
            raise RuntimeError("No accessible window appeared for the launched process. Launch the app executable directly.")
        for index, step in enumerate(spec["steps"], 1):
            state["step"] = index
            action, name = step["action"], step["name"]
            update("verifying", f"{action}: {name}", capture=True)

            def matches(nodes):
                found = [node for node in nodes if node["name"] == name]
                if action == "expect_absent":
                    return bool(nodes) and not found
                if action == "click":
                    return [node for node in found if activation(node) is not None]
                return found

            found = wait_for(matches)
            if not found:
                if action == "click":
                    raise RuntimeError(f"Could not find control {name!r}.")
                update("assertion_failed", f"{action} failed for {name!r}", capture=True)
                return 10
            if action == "click":
                if len(found) != 1:
                    raise RuntimeError(f"Control {name!r} is ambiguous.")
                position = activation(found[0])
                if position is None or not tree.invoke(found[0]["id"], position)["applied"]:
                    raise RuntimeError(f"Control {name!r} could not be activated.")
        update("passed", capture=True)
        return 0
    except InterruptedError as error:
        update("restarting", str(error))
        return 79
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        update("error", str(error))
        print(error, file=sys.stderr)
        return 78
    finally:
        if app is not None and app.poll() is None:
            app.terminate()
            try:
                app.wait(timeout=3)
            except subprocess.TimeoutExpired:
                app.kill()
                app.wait()
        if desktop is not None:
            desktop.close()


def main():
    destination = Path(sys.argv[1])
    spec = validate(json.loads((destination / "spec.json").read_text(encoding="utf-8")))
    while True:
        code = run(spec, destination)
        if code != 79:
            raise SystemExit(code)
