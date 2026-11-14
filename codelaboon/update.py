"""Update codelaboon in place.

When running from a source checkout this pulls the latest changes (if it is a
git repository) and reinstalls the package for the current user so a new
terminal/session picks up the updated ``codelaboon`` command. When no checkout
is available, it explains how to update the installed package.

This addresses the common "I changed or pulled code but it didn't take effect"
case: the running interpreter may still import an older installed copy until it
is reinstalled.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _is_git_checkout(root: Path) -> bool:
    git = root / ".git"
    return git.exists()


def _run(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    return completed.returncode, output


def update(editable: bool = True, pull: bool = True, runtime: bool = True, engine="opencode") -> bool:
    """Update from the current source checkout and reinstall.

    Returns True on success.
    """
    from codelaboon.install import _banner, _step, install_package, user_scripts_dir

    root = Path(__file__).resolve().parent.parent
    has_checkout = (root / "pyproject.toml").is_file()
    interactive = callable(getattr(sys.stdout, "isatty", None)) and sys.stdout.isatty()

    if interactive:
        _banner()

    if not has_checkout:
        message = (
            "No source checkout found. Reinstall with: "
            f"{sys.executable} -m pip install --user --upgrade codelaboon"
        )
        if interactive:
            _step("Locate source checkout", lambda: (False, "not found"))
            print("\n  " + message)
        else:
            print(message)
        return False

    git_output = ""
    if pull and _is_git_checkout(root) and shutil.which("git"):
        def do_pull() -> tuple[bool, str]:
            nonlocal git_output
            code, output = _run(["git", "pull", "--ff-only"], root)
            git_output = output
            if code != 0:
                short = output.splitlines()[-1] if output else "skipped"
                return False, short[:80]
            first = output.splitlines()[0] if output else "up to date"
            return True, first[:80]

        ok, _ = _step("Pull latest changes", do_pull)
        if not ok:
            print("Update stopped. Resolve the pull failure, or use --no-pull to reinstall local changes.")
            return False
    elif pull:
        _step("Pull latest changes", lambda: (True, "not a git checkout"))

    pip_output = ""

    def do_install() -> tuple[bool, str]:
        nonlocal pip_output
        code, output = install_package(editable=editable, quiet=True)
        pip_output = output
        if code != 0:
            return False, "pip install failed"
        return True, "installed"

    ok, _ = _step(
        "Reinstall package",
        do_install,
        detail="(editable)" if editable else "(user)",
    )
    if not ok:
        if pip_output:
            tail = "\n".join(pip_output.splitlines()[-12:])
            print("\n  pip output:")
            print("  " + "\n  ".join(tail.splitlines()))
        return False

    if runtime:
        from codelaboon.install import setup_runtime
        if not setup_runtime(engine):
            return False

    scripts = user_scripts_dir()
    print()
    print(f"  codelaboon updated from: {root}")
    print(f"  Scripts directory: {scripts}")
    print("  Restart `codelaboon` (open a new terminal if PATH changed) to use the update.")
    print()
    return True


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    editable = "--no-editable" not in argv
    pull = "--no-pull" not in argv
    engine = argv[argv.index("--engine") + 1] if "--engine" in argv else "opencode"
    return 0 if update(editable=editable, pull=pull,
                       runtime="--skip-runtime" not in argv, engine=engine) else 1


if __name__ == "__main__":
    raise SystemExit(main())
