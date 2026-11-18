"""Bounded Linux native accessibility observations for desktop MCP."""
from collections import deque


class Accessibility:
    def __init__(self):
        self.references = []

    def observe(self, process_id=None):
        self.references.clear()
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi, Gio, GLib
        except (ImportError, ValueError) as error:
            raise RuntimeError("Native accessibility requires Linux AT-SPI and PyGObject.") from error
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync("org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus", "GetAddress",
                          None, None, Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error as error:
            raise RuntimeError("The accessibility bus is unavailable in this session.") from error
        desktop = Atspi.get_desktop(0)
        if desktop is None:
            raise RuntimeError("No AT-SPI desktop is available.")
        queue = deque((desktop.get_child_at_index(i), None)
                      for i in range(min(desktop.get_child_count(), 32)))
        result = []
        while queue and len(result) < 150:
            node, parent = queue.popleft()
            if node is None:
                continue
            try:
                if parent is None and process_id is not None and node.get_process_id() != process_id:
                    continue
                role = node.get_role()
                if role == Atspi.Role.PASSWORD_TEXT:
                    continue
                index = len(result)
                actions = [node.get_action_name(i) for i in range(min(node.get_n_actions(), 8))]
                result.append({"id": index, "parent": parent, "role": node.get_role_name(),
                               "name": (node.get_name() or "")[:160], "actions": actions})
                self.references.append((node, len(actions)))
                if len(queue) < 150:
                    queue.extend((node.get_child_at_index(i), index)
                                 for i in range(min(node.get_child_count(), 32)))
            except GLib.Error:
                continue
        return result

    def invoke(self, node_id, action_index):
        if not 0 <= node_id < len(self.references):
            raise ValueError("Observe the accessibility tree again.")
        node, count = self.references[node_id]
        if not 0 <= action_index < count:
            raise ValueError("Choose an action from the observed element.")
        self.references.clear()
        return {"applied": bool(node.do_action(action_index))}
