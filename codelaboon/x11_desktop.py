"""X11 foreground input and capture, including private Xvfb displays."""
import os
import string
import time


class X11Desktop:
    aliases = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L", "win": "Super_L",
               "enter": "Return", "tab": "Tab", "esc": "Escape", "escape": "Escape",
               "space": "space", "backspace": "BackSpace", "delete": "Delete",
               "up": "Up", "down": "Down", "left": "Left", "right": "Right"}
    KEYBOARD_KEYS = (*aliases, *string.ascii_letters, *string.digits,
                     *(f"f{i}" for i in range(1, 13)))

    def __init__(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        self.x, self.xk, self.xtest = X, XK, xtest
        self.display = display.Display()

    def close(self):
        self.display.close()

    def size(self):
        geometry = self.display.screen().root.get_geometry()
        return geometry.width, geometry.height

    def screenshot(self):
        from PIL import ImageGrab
        return ImageGrab.grab(xdisplay=os.environ["DISPLAY"])

    def click(self, x, y):
        self.xtest.fake_input(self.display, self.x.MotionNotify, x=x, y=y)
        self.button(1)

    def button(self, number):
        self.xtest.fake_input(self.display, self.x.ButtonPress, number)
        self.xtest.fake_input(self.display, self.x.ButtonRelease, number)
        self.display.sync()

    def scroll(self, ticks):
        for _ in range(abs(ticks)):
            self.button(4 if ticks > 0 else 5)

    def hotkey(self, *keys):
        events = []
        for key in keys:
            if len(key) == 1:
                symbol = ord(key)
            else:
                symbol = self.xk.string_to_keysym(self.aliases.get(key, key.upper()))
            candidates = [(code, level) for code, level in self.display.keysym_to_keycodes(symbol)
                          if level in (0, 1)]
            if not candidates:
                raise ValueError(f"Key {key!r} is unavailable in this keyboard layout.")
            code, level = min(candidates, key=lambda pair: pair[1])
            if level:
                shift = self.display.keysym_to_keycode(self.xk.string_to_keysym("Shift_L"))
                if shift not in events:
                    events.append(shift)
            events.append(code)
        for code in events:
            self.xtest.fake_input(self.display, self.x.KeyPress, code)
        for code in reversed(events):
            self.xtest.fake_input(self.display, self.x.KeyRelease, code)
        self.display.sync()

    def write(self, text, interval):
        for char in text:
            self.hotkey(char)
            time.sleep(interval)
