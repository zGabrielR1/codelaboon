"""Native Wayland screen and input through the user's desktop portal."""

import io
import os
import tempfile
import uuid

from codelaboon.paths import data_dir

BUS = "org.freedesktop.portal.Desktop"
DESKTOP = "/org/freedesktop/portal/desktop"
REMOTE = "org.freedesktop.portal.RemoteDesktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"


class WaylandDesktop:
    def __init__(self):
        try:
            import gi
            gi.require_version("Gst", "1.0")
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk, Gio, GLib, Gst
            from PIL import Image
        except (ImportError, ValueError) as error:
            raise RuntimeError("Wayland needs PyGObject, GDK 4, GStreamer and Pillow.") from error
        self.gdk, self.gio, self.glib, self.gst, self.image = Gdk, Gio, GLib, Gst, Image
        Gst.init(None)
        if not Gst.ElementFactory.find("pipewiresrc"):
            raise RuntimeError("Install the GStreamer PipeWire plugin for Wayland capture.")
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.session = self.pipeline = self.fd = self.dimensions = None
        try:
            self.start()
        except Exception:
            self.close()
            raise

    def call(self, interface, method, signature, *values, path=DESKTOP):
        return self.bus.call_sync(
            BUS, path, interface, method, self.glib.Variant(signature, values), None,
            self.gio.DBusCallFlags.NONE, 5000, None,
        ).unpack()

    def request(self, interface, method, signature, *values, **options):
        glib, gio = self.glib, self.gio
        token = "codelaboon_" + uuid.uuid4().hex
        sender = self.bus.get_unique_name()[1:].replace(".", "_")
        path = f"{DESKTOP}/request/{sender}/{token}"
        context = glib.MainContext.new()
        loop = glib.MainLoop.new(context, False)
        result = []

        def response(_bus, _sender, _path, _interface, _signal, parameters):
            result.extend(parameters.unpack())
            loop.quit()

        def timeout(*_args):
            loop.quit()
            return False

        context.push_thread_default()
        subscription = self.bus.signal_subscribe(
            BUS, "org.freedesktop.portal.Request", "Response", path, None,
            gio.DBusSignalFlags.NONE, response,
        )
        timer = glib.timeout_source_new_seconds(45)
        timer.set_callback(timeout)
        timer.attach(context)
        try:
            options["handle_token"] = glib.Variant("s", token)
            returned, = self.call(interface, method, signature, *values, options)
            if returned != path:
                raise RuntimeError("The desktop portal returned an unexpected request path.")
            loop.run()
            if not result:
                self.call("org.freedesktop.portal.Request", "Close", "()", path=path)
                raise RuntimeError("Desktop portal approval timed out.")
            if result[0] != 0:
                raise RuntimeError("Desktop portal access was canceled or denied.")
            return result[1]
        finally:
            timer.destroy()
            self.bus.signal_unsubscribe(subscription)
            context.pop_thread_default()

    def start(self):
        variant = self.glib.Variant
        created = self.request(REMOTE, "CreateSession", "(a{sv})",
                               session_handle_token=variant("s", "codelaboon_" + uuid.uuid4().hex))
        self.session = created["session_handle"]
        options = {"types": variant("u", 3)}
        token_file = None
        if os.environ.get("CODELABOON_WAYLAND_REMEMBER") == "1":
            token_file = data_dir() / "wayland-restore-token"
            options["persist_mode"] = variant("u", 2)
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                token = ""
            if token:
                options["restore_token"] = variant("s", token)
        self.request(REMOTE, "SelectDevices", "(oa{sv})", self.session, **options)
        self.request(SCREENCAST, "SelectSources", "(oa{sv})", self.session,
                     types=variant("u", 1), multiple=variant("b", False))
        started = self.request(REMOTE, "Start", "(osa{sv})", self.session, "")
        streams = started.get("streams", [])
        if started.get("devices", 0) & 3 != 3 or len(streams) != 1:
            raise RuntimeError("Share one monitor and grant both keyboard and pointer access.")
        if token_file is not None:
            token = started.get("restore_token")
            if token:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=token_file.parent,
                                                 delete=False) as temporary:
                    temporary.write(token)
                try:
                    os.replace(temporary.name, token_file)
                finally:
                    if os.path.exists(temporary.name):
                        os.unlink(temporary.name)
            else:
                token_file.unlink(missing_ok=True)
        self.node, properties = streams[0]
        self.logical_size = properties.get("logical_size") or properties.get("size")
        if not self.logical_size or min(self.logical_size) < 1:
            raise RuntimeError("The desktop portal did not report the monitor's coordinate space.")
        handle, descriptors = self.bus.call_with_unix_fd_list_sync(
            BUS, DESKTOP, SCREENCAST, "OpenPipeWireRemote", variant("(oa{sv})", (self.session, {})),
            None, self.gio.DBusCallFlags.NONE, 5000, None, None,
        )
        self.fd = descriptors.get(handle.unpack()[0])
        self.pipeline = self.gst.parse_launch(
            f"pipewiresrc fd={self.fd} path={self.node} ! videoconvert ! pngenc ! "
            "appsink name=screen max-buffers=1 drop=true sync=false"
        )
        if self.pipeline.set_state(self.gst.State.PLAYING) == self.gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Could not start the portal screen stream.")

    def screenshot(self):
        screen = self.pipeline.get_by_name("screen")
        sample = screen.emit("try-pull-sample", 5 * self.gst.SECOND)
        if sample is None:
            raise RuntimeError("No screen frame arrived from the portal.")
        buffer = sample.get_buffer()
        with self.image.open(io.BytesIO(buffer.extract_dup(0, buffer.get_size()))) as image:
            self.dimensions = image.size
            return image.copy()

    def size(self):
        return self.dimensions

    def notify(self, method, signature, *values):
        self.call(REMOTE, method, signature, self.session, {}, *values)

    def click(self, x, y):
        width, height = self.dimensions
        logical_width, logical_height = self.logical_size
        self.notify("NotifyPointerMotionAbsolute", "(oa{sv}udd)", self.node,
                    x * logical_width / width, y * logical_height / height)
        self.notify("NotifyPointerButton", "(oa{sv}iu)", 272, 1)
        self.notify("NotifyPointerButton", "(oa{sv}iu)", 272, 0)

    def keyval(self, key):
        names = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L", "win": "Super_L",
                 "enter": "Return", "tab": "Tab", "esc": "Escape", "escape": "Escape",
                 "space": "space", "backspace": "BackSpace", "delete": "Delete",
                 "up": "Up", "down": "Down", "left": "Left", "right": "Right"}
        value = (self.gdk.unicode_to_keyval(ord(key)) if len(key) == 1 else
                 self.gdk.keyval_from_name(names.get(key, key.upper() if key.startswith("f") else key)))
        if value in (0, 0xffffff):
            raise ValueError("Unsupported desktop key.")
        return value

    def hotkey(self, *keys):
        values = [self.keyval(key) for key in keys]
        pressed = []
        try:
            for value in values:
                self.notify("NotifyKeyboardKeysym", "(oa{sv}iu)", value, 1)
                pressed.append(value)
        finally:
            for value in reversed(pressed):
                self.notify("NotifyKeyboardKeysym", "(oa{sv}iu)", value, 0)

    def write(self, text, interval):
        for character in text:
            self.hotkey(character)

    def scroll(self, ticks):
        self.notify("NotifyPointerAxisDiscrete", "(oa{sv}ui)", 0, -ticks)

    def close(self):
        if self.pipeline is not None:
            self.pipeline.set_state(self.gst.State.NULL)
        if self.fd is not None:
            os.close(self.fd)
        if self.session is not None:
            try:
                self.call("org.freedesktop.portal.Session", "Close", "()", path=self.session)
            except self.glib.Error:
                pass
