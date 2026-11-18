"""Local workspace actions shared by the web UI and stdio MCP."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
from typing import Literal
from urllib.parse import urlsplit


def run_command(argv: list[str]) -> dict:
    """Run an executable and arguments in the workspace, with a 30-second limit."""
    if not isinstance(argv, list) or not 1 <= len(argv) <= 64 or any(
        not isinstance(arg, str) or len(arg) > 4096 or "\0" in arg for arg in argv
    ) or not argv[0].strip():
        raise ValueError("Enter a JSON array containing an executable and its arguments.")
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(argv, cwd=Path.cwd(), stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=30)
        except subprocess.TimeoutExpired:
            raise ValueError("The command exceeded 30 seconds. Use a desktop terminal for longer commands.") from None
        size = output.tell()
        output.seek(max(0, size - 16384))
        return {"exit_code": result.returncode, "output": output.read(16384).decode(errors="replace"),
                "truncated": size > 16384}


def open_workspace_terminal() -> dict:
    """Open the system terminal in the workspace directory."""
    from codelaboon.task_launch import open_terminal

    open_terminal(Path.cwd())
    return {"message": "Opened a terminal in the workspace directory."}


def list_tasks() -> dict:
    """List work managed by the local Codelaboon task queue."""
    from codelaboon.task_api import snapshot

    state = snapshot()
    return {key: state[key] for key in ("configured", "worker", "tasks")}


def open_task(task: str, engine: str) -> dict:
    """Open an existing task in an installed native engine."""
    from codelaboon.task_launch import launch

    return launch(task, engine)


def control_task(task: str, action: Literal["pause", "resume"]) -> dict:
    """Pause or resume an existing task at its next checkpoint."""
    from codelaboon.task_api import control

    if action not in ("pause", "resume"):
        raise ValueError("Choose pause or resume.")
    return control(task, action)


class Browser:
    """An isolated, visible Chromium session owned by the calling workspace."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="desktop-browser")
        self.runtime = self.browser = self.page = None

    def call(self, action, **arguments):
        return self.executor.submit(self._call, action, arguments).result()

    def close(self):
        self.executor.submit(self._close).result()
        self.executor.shutdown()

    def _close(self):
        try:
            if self.runtime:
                self.runtime.stop()
        finally:
            self.runtime = self.browser = self.page = None

    def _call(self, action, arguments):
        if action == "close":
            self._close()
            return {"message": "Browser session closed."}
        if action == "navigate":
            url = arguments.get("url")
            if not isinstance(url, str) or len(url) > 4096:
                raise ValueError("Enter an HTTP or HTTPS URL.")
            target = urlsplit(url)
            if target.scheme not in ("http", "https") or not target.hostname or target.username is not None:
                raise ValueError("Enter an HTTP or HTTPS URL without credentials.")
        if self.page is None or self.page.is_closed():
            if action != "navigate":
                raise ValueError("Open a page first.")
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise ValueError("Install codelaboon[desktop] to enable browser control.") from None
            self._close()
            self.runtime = sync_playwright().start()
            try:
                self.browser = self.runtime.chromium.launch(headless=False)
                self.page = self.browser.new_page()
                self.page.set_default_timeout(8000)
            except Exception:
                self._close()
                raise ValueError("Could not start Chromium. Install it with python -m playwright install chromium and use a graphical desktop session.") from None
        try:
            if action == "navigate":
                self.page.goto(url, wait_until="domcontentloaded")
            elif action in ("click", "fill"):
                selector = arguments.get("selector")
                if not isinstance(selector, str) or not selector.strip() or len(selector) > 1000:
                    raise ValueError("Enter a CSS selector or Playwright locator.")
                locator = self.page.locator(selector)
                if action == "click":
                    locator.click()
                else:
                    value = arguments.get("text")
                    if not isinstance(value, str) or len(value) > 16000:
                        raise ValueError("Enter text of up to 16,000 characters.")
                    locator.fill(value)
            elif action != "snapshot":
                raise ValueError("Unknown browser action.")
            return {"url": self.page.url, "title": self.page.title(),
                    "snapshot": self.page.locator("body").aria_snapshot(timeout=8000)[:16000]}
        except ValueError:
            raise
        except Exception:
            raise ValueError("The browser action could not finish. Check the page and locator, then retry.") from None
