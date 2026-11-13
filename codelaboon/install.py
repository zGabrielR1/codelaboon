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

import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import List, Optional


MARKER = "# codelaboon"


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


def install_package(editable: bool = False, extra: Optional[str] = "tui") -> int:
    """Run ``pip install --user`` against the current source checkout."""
    root = package_root()
    if not (root / "pyproject.toml").is_file():
        print("No source checkout found; skipping pip install (already installed?).")
        return 0
    target = str(root)
    if extra:
        target += f"[{extra}]"
    command = [sys.executable, "-m", "pip", "install", "--user"]
    if editable:
        command.append("-e")
    command.append(target)
    print("Installing:", " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


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


def add_to_path(directory: Path) -> bool:
    """Make ``directory`` reachable from new shells. True when it changed."""
    directory = directory.expanduser()
    if os.name == "nt":
        return add_to_windows_path(directory)
    updated = add_to_posix_path(directory)
    if updated:
        print("Updated:", ", ".join(str(path) for path in updated))
    return bool(updated)


def on_path(directory: Path) -> bool:
    wanted = os.path.normcase(str(directory))
    return any(os.path.normcase(entry) == wanted for entry in os.environ.get("PATH", "").split(os.pathsep))


def install(editable: bool = False, update_path: bool = True) -> bool:
    status = install_package(editable=editable)
    if status != 0:
        print("pip install failed; PATH was not changed.")
        return False

    directory = user_scripts_dir()
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
