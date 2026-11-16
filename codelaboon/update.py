"""Update codelaboon in place.

When running from a source checkout this pulls the latest changes (if it is a
git repository) and reinstalls the package for the current user so a new
terminal/session picks up the updated ``codelaboon`` command. When no checkout
is available, it installs a checksum-verified newer official release wheel.

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


def update(editable: bool = True, pull: bool = True, runtime: bool = False, engine="opencode", check_runtime=True) -> bool:
    """Update from the current source checkout and reinstall.

    Returns True on success.
    """
    from codelaboon.install import _banner, _step, install_package, user_scripts_dir

    root = Path(__file__).resolve().parent.parent
    has_checkout = (root / "pyproject.toml").is_file()
    interactive = callable(getattr(sys.stdout, "isatty", None)) and sys.stdout.isatty()

    if interactive:
        _banner('update and recovery')

    if not has_checkout:
        from codelaboon.release_update import install_latest
        ok, _ = _step('Install verified release', install_latest)
        if not ok:
            return False
        if not finish_runtime_update(root, runtime, engine, check_runtime):
            return False
        print('Restart Codelaboon to use the update.')
        return True

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
    elif pull and _is_git_checkout(root):
        print('Update stopped: Git is unavailable. Install Git or use --no-pull to reinstall local source.')
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
        detail="editable" if editable else "user",
    )
    if not ok:
        if pip_output:
            tail = "\n".join(pip_output.splitlines()[-12:])
            print("\n  pip output:")
            print("  " + "\n  ".join(tail.splitlines()))
        return False

    if not finish_runtime_update(root, runtime, engine, check_runtime):
        return False

    scripts = user_scripts_dir()
    print()
    print(f"  codelaboon updated from: {root}")
    print(f"  Scripts directory: {scripts}")
    print("  Restart `codelaboon` (open a new terminal if PATH changed) to use the update.")
    print()
    return True


def finish_runtime_update(root, prepare, engine, check_runtime=True):
    if not check_runtime and not prepare:
        print('Runtime verification skipped (--no-runtime-check).')
        return True
    print('\n  Check and repair installed runtimes (unused engines remain lazy)', flush=True)
    from codelaboon.install import installation_python
    interpreter, _ = installation_python()
    command = [interpreter, '-m', 'codelaboon.runtime_management', 'maintain']
    if prepare:
        command.extend(['--prepare', engine])
    # A fresh interpreter imports the updated repair code after pull/install.
    code = subprocess.call(command, cwd=str(root))
    if code:
        print('Core installation finished, but runtime verification failed. Use codelaboon runtime status for recovery steps.')
        return False
    print('  Runtime verification complete.')
    return True


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    editable = "--no-editable" not in argv
    pull = "--no-pull" not in argv
    engine = argv[argv.index("--engine") + 1] if "--engine" in argv else "opencode"
    return 0 if update(editable=editable, pull=pull,
                       runtime="--prepare-runtime" in argv, engine=engine,
                       check_runtime='--no-runtime-check' not in argv) else 1


if __name__ == "__main__":
    raise SystemExit(main())
