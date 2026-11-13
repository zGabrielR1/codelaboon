"""Install codelaboon so the ``codelaboon`` command works from any directory.

``python -m codelaboon install`` performs the two steps the README used to
leave to the user:

1. install the package for the current user (``pip install --user``);
2. add the user script directory (``~/.local/bin``, ``~/Library/Python/X.Y/bin``
   or ``%APPDATA%\\Python\\PythonX.Y\\Scripts``) to ``PATH``.

The PATH edit is idempotent: existing directories are left alone and the same
line is never appended twice. On Windows the user ``Path`` registry value is
updated and a settings-change broadcast is sent; new terminals pick it up.
"""

import itertools
import os
import shutil
import subprocess
import sys
import sysconfig
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional


MARKER = "# codelaboon"

# ANSI styling, disabled automatically when the terminal cannot show it.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = getattr(sys.stdout, "isatty", None)
    if not callable(stream) or not stream():
        return False
    if os.name == "nt":
        return os.environ.get("WT_SESSION") or os.environ.get("TERM") or os.environ.get("ANSICON")
    return True


def _paint(text: str, *styles: str) -> str:
    if not _color_enabled() or not styles:
        return text
    return "".join(styles) + text + _RESET


def _banner() -> None:
    width = max(44, min(shutil.get_terminal_size((72, 20)).columns, 72))
    mark = _paint("▲ codelaboon", _BOLD, _CYAN)
    print()
    print(f"  {mark}  {_paint('installer', _DIM)}")
    print("  " + _paint("─" * (width - 4), _DIM))


def _step(label: str, action: Callable[[], tuple[bool, str]], detail: str = "") -> tuple[bool, str]:
    """Run ``action`` with an animated spinner, returning its (ok, detail)."""
    is_tty = callable(getattr(sys.stdout, "isatty", None)) and sys.stdout.isatty()
    interactive = is_tty and not os.environ.get("CODELABOON_NO_ANIMATION")
    plain_frames = "-\\|/"
    frames = itertools.cycle(_SPINNER if _color_enabled() else plain_frames)
    done = threading.Event()
    result: list[tuple[bool, str]] = [(False, "")]

    def run() -> None:
        try:
            result[0] = action()
        except Exception as error:  # Show install failures, never crash the UI.
            result[0] = (False, str(error))
        finally:
            done.set()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()

    if interactive:
        while not done.is_set():
            frame = next(frames)
            sys.stdout.write("\r" + f"  {_paint(frame, _CYAN)} {label}")
            if detail:
                sys.stdout.write(f" {_paint(detail, _DIM)}")
            sys.stdout.write("   ")
            sys.stdout.flush()
            done.wait(0.08)
        sys.stdout.write("\r")
    else:
        print(f"  … {label}" + (f" ({detail})" if detail else ""))
        done.wait()

    ok, message = result[0]
    icon = _paint("✓", _BOLD, _GREEN) if ok else _paint("✗", _BOLD, _RED)
    line = f"  {icon} {label}"
    if message:
        color = _DIM if ok else _YELLOW
        line += f" {_paint(message, color)}"
    print(line + " " * 8)
    return ok, message



def package_root() -> Path:
    """The source checkout, when codelaboon is running from one."""
    return Path(__file__).resolve().parent.parent


def user_scripts_dir() -> Path:
    """The directory pip --user puts the console script in."""
    scheme = "nt_user" if os.name == "nt" else "posix_user"
    try:
        path = sysconfig.get_path("scripts", scheme=scheme)
    except KeyError:
        path = ""
    if not path:
        base = Path(sysconfig.get_path("data", scheme=scheme))
        path = str(base / ("Scripts" if os.name == "nt" else "bin"))
    return Path(path)


def install_package(
    editable: bool = False,
    extra: Optional[str] = "tui",
    quiet: bool = False,
) -> tuple[int, str]:
    """Run ``pip install --user`` against the current source checkout."""
    root = package_root()
    if not (root / "pyproject.toml").is_file():
        return 0, "source checkout not found"
    target = str(root)
    if extra:
        target += f"[{extra}]"
    command = [sys.executable, "-m", "pip", "install", "--user", "--progress-bar", "off"]
    if editable:
        command.append("-e")
    command.append(target)
    if quiet:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, output.strip()
    completed = subprocess.run(command, check=False)
    return completed.returncode, ""


def _posix_profiles() -> List[Path]:
    from codelaboon.paths import home

    home_dir = home()
    candidates = [home_dir / ".profile", home_dir / ".bashrc", home_dir / ".zshrc"]
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home_dir / ".config")))
    candidates.append(config / "fish" / "config.fish")
    return [path for path in candidates if path.is_file()]


def add_to_posix_path(directory: Path) -> List[Path]:
    """Append an idempotent export line to the shell profiles that exist."""
    updated: List[Path] = []
    line = f'export PATH="{directory}:$PATH"  {MARKER}'
    for profile in _posix_profiles():
        try:
            text = profile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if str(directory) in text and MARKER in text:
            continue
        prefix = "" if text.endswith("\n") or not text else "\n"
        with open(profile, "a", encoding="utf-8") as stream:
            stream.write(f"{prefix}{line}\n")
        updated.append(profile)
    return updated


def _broadcast_windows_environment_change() -> None:
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
        )
    except (AttributeError, OSError):
        pass


def add_to_windows_path(directory: Path) -> bool:
    """Add ``directory`` to the current user's Path registry value."""
    try:
        import winreg
    except ImportError:
        return False

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        0,
        winreg.KEY_READ | winreg.KEY_SET_VALUE,
    )
    try:
        try:
            current, _kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        parts = [part for part in str(current).split(";") if part.strip()]
        if any(Path(part) == directory for part in parts):
            return False
        parts.append(str(directory))
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))
    finally:
        winreg.CloseKey(key)
    _broadcast_windows_environment_change()
    return True


def add_to_path(directory: Path, quiet: bool = False) -> bool:
    """Make ``directory`` reachable from new shells. True when it changed."""
    directory = directory.expanduser()
    if os.name == "nt":
        return add_to_windows_path(directory)
    updated = add_to_posix_path(directory)
    if updated and not quiet:
        print("Updated:", ", ".join(str(path) for path in updated))
    return bool(updated)


def on_path(directory: Path) -> bool:
    wanted = os.path.normcase(str(directory))
    return any(os.path.normcase(entry) == wanted for entry in os.environ.get("PATH", "").split(os.pathsep))


def install(editable: bool = False, update_path: bool = True) -> bool:
    interactive = callable(getattr(sys.stdout, "isatty", None)) and sys.stdout.isatty()
    interactive = interactive and not os.environ.get("CODELABOON_PLAIN_INSTALL")
    directory = user_scripts_dir()
    pip_output = ""

    if interactive:
        _banner()

        def do_install() -> tuple[bool, str]:
            nonlocal pip_output
            code, output = install_package(editable=editable, quiet=True)
            pip_output = output
            if code != 0:
                return False, "pip install failed"
            if "source checkout not found" in output:
                return True, "already installed"
            return True, "ready"

        ok, _ = _step(
            "Install codelaboon",
            do_install,
            detail="(editable)" if editable else "(user)",
        )
        if not ok:
            if pip_output:
                tail = "\n".join(pip_output.splitlines()[-12:])
                print("\n" + _paint("pip output:", _DIM))
                print(_paint(tail, _DIM))
            print(_paint("\n  PATH was not changed.", _YELLOW))
            return False

        changed = False
        if update_path:
            def do_path() -> tuple[bool, str]:
                nonlocal changed
                changed = add_to_path(directory, quiet=True)
                if on_path(directory) and not changed:
                    return True, "already on PATH"
                if changed:
                    return True, "updated"
                return True, "add manually"

            _step("Configure PATH", do_path, detail=str(directory))
        else:
            _step("Configure PATH", lambda: (True, "skipped (--no-path)"))

        print()
        print("  " + _paint("Next steps", _BOLD, _MAGENTA))
        if changed or (not on_path(directory) and not update_path):
            print("  " + _paint("Open a new terminal, then:", _DIM))
        print(f"  {_paint('$', _DIM)} cd my-project")
        print(f"  {_paint('$', _DIM)} codelaboon")
        if update_path and not on_path(directory) and not changed and os.name == "nt":
            print("  " + _paint(f"Add to PATH if needed: {directory}", _YELLOW))
        print()
        return True

    # Non-interactive: keep plain, script-friendly output.
    code, output = install_package(editable=editable, quiet=False)
    if code != 0:
        print("pip install failed; PATH was not changed.")
        return False

    changed = False
    if update_path:
        changed = add_to_path(directory)
    print()
    print(f"codelaboon installed. Scripts directory: {directory}")
    if on_path(directory):
        print("The scripts directory is already on PATH.")
    elif changed:
        print("PATH updated. Open a new terminal (or log out/in on Windows) to use `codelaboon`.")
    elif not update_path:
        print(f"PATH was not changed. Add this yourself: {directory}")
    else:
        print(f"Could not update PATH automatically. Add this yourself: {directory}")
    print()
    print("Then start the workspace from any project directory:")
    print("  cd my-project")
    print("  codelaboon")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    editable = "--editable" in argv or "-e" in argv
    update_path = "--no-path" not in argv
    return 0 if install(editable=editable, update_path=update_path) else 1


if __name__ == "__main__":
    raise SystemExit(main())
