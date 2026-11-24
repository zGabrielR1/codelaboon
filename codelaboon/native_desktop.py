"""Foreground screen observation and input for the local MCP session."""

from contextlib import contextmanager, suppress
import hashlib
import io
import os
import sys
import uuid

from codelaboon.paths import data_dir


class DesktopSession:
    def __init__(self):
        self.lease = None
        self.frame = None
        self.portal = None
        self.x11 = None

    @contextmanager
    def driver(self):
        linux = sys.platform.startswith("linux")
        wayland = linux and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland")
        if linux and not wayland and not os.environ.get("DISPLAY"):
            raise RuntimeError("Start the worker inside a graphical desktop session.")
        if self.lease is None:
            root = data_dir()
            root.mkdir(parents=True, exist_ok=True)
            display = os.environ.get("CODELABOON_ISOLATED_DISPLAY")
            key = hashlib.sha256(display.encode()).hexdigest() if display else "host"
            lease = (root / f"desktop-{key}.lock").open("a+b")
            try:
                if os.name == "nt":
                    import msvcrt
                    lease.seek(0)
                    msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                lease.close()
                raise RuntimeError("Another Codelaboon session owns the foreground desktop.") from error
            self.lease = lease
        try:
            if wayland:
                if self.portal is None:
                    from codelaboon.wayland_desktop import WaylandDesktop
                    self.portal = WaylandDesktop()
                driver = self.portal
            elif linux:
                if self.x11 is None:
                    from codelaboon.x11_desktop import X11Desktop
                    self.x11 = X11Desktop()
                driver = self.x11
            else:
                import pyautogui as driver
        except ImportError as error:
            self.close()
            raise RuntimeError("Install codelaboon[native-desktop] for foreground desktop control.") from error
        except Exception:
            self.close()
            raise
        yield driver

    def close(self):
        self.frame = None
        try:
            if self.portal is not None:
                self.portal.close()
                self.portal = None
            if self.x11 is not None:
                self.x11.close()
                self.x11 = None
        finally:
            if self.lease is not None:
                self.lease.close()
                self.lease = None

    def observe(self):
        self.frame = None
        try:
            with self.driver() as driver:
                screenshot = driver.screenshot()
                width, height = driver.size()
                if screenshot.size != (width, height):
                    screenshot = screenshot.resize((width, height))
                with io.BytesIO() as output:
                    screenshot.save(output, format="PNG")
                    image = output.getvalue()
        except Exception:
            with suppress(Exception):
                self.close()
            raise
        frame_id = uuid.uuid4().hex
        self.frame = (frame_id, width, height)
        return frame_id, width, height, image

    def act(self, frame_id, action, x=None, y=None, keys=None, text=None, ticks=None):
        if self.frame is None or frame_id != self.frame[0]:
            raise ValueError("Observe the desktop before each input action.")
        with self.driver() as driver:
            _, width, height = self.frame
            if tuple(driver.size()) != (width, height):
                self.frame = None
                raise ValueError("Display dimensions changed. Observe the desktop again.")
            self.frame = None
            if action == "click":
                if x is None or y is None or not (0 <= x < width and 0 <= y < height):
                    raise ValueError("Click coordinates must be inside the observed screen.")
                driver.click(x, y)
            elif action == "key":
                if not keys or len(keys) > 4 or (self.portal is None and any(key not in driver.KEYBOARD_KEYS for key in keys)):
                    raise ValueError("Provide one to four supported keys.")
                driver.hotkey(*keys)
            elif action == "type":
                if not text or len(text) > 1000 or any(not 32 <= ord(char) <= 126 for char in text):
                    raise ValueError("Provide 1–1000 printable ASCII characters.")
                driver.write(text, interval=0.01)
            elif action == "scroll":
                if ticks is None or not 0 < abs(ticks) <= 20:
                    raise ValueError("Provide a signed scroll amount from 1 to 20 ticks.")
                driver.scroll(ticks)
            else:
                raise ValueError("Unknown desktop action.")
            return {"action": action, "applied": True}
