import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from codelaboon import desktop_mcp
from codelaboon.native_desktop import DesktopSession
from codelaboon.work_queue import swarm_harness, validate_swarm


class NativeDesktopTests(unittest.TestCase):
    def test_session_lease_and_single_use_observation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"DISPLAY": ":99", "WAYLAND_DISPLAY": "", "XDG_SESSION_TYPE": "x11"}
        ), patch("codelaboon.native_desktop.data_dir", return_value=Path(directory)):
            driver = Mock()
            driver.size.return_value = (640, 480)
            driver.screenshot.return_value.size = (640, 480)
            with patch("codelaboon.native_desktop.sys.platform", "test"), patch.dict("sys.modules", {"pyautogui": driver}):
                first, second = DesktopSession(), DesktopSession()
                try:
                    frame, _, _, _ = first.observe()
                    with self.assertRaisesRegex(RuntimeError, "owns the foreground"):
                        second.observe()
                    first.act(frame, "click", x=15, y=25)
                    driver.click.assert_called_once_with(15, 25)
                    with self.assertRaisesRegex(ValueError, "Observe"):
                        first.act(frame, "click", x=15, y=25)
                    first.close()
                    second.observe()
                finally:
                    first.close()
                    second.close()

    def test_native_swarm_routes_locally_and_headless_mcp_is_opt_in(self):
        options = validate_swarm({
            "controller": "worker", "workers": 4, "timeout": 60, "interval": 60,
            "cycles": 1, "engine": "jcode", "model": "free", "foreground_desktop": True,
        })
        self.assertEqual(swarm_harness({"id": "demo", "swarm": options})["location"], "local")
        with patch.dict(os.environ, {
            "CODELABOON_DESKTOP_MCP": "1", "CODELABOON_HEADLESS_TASK": "1",
            "CODELABOON_FOREGROUND_TASK": "0",
        }):
            self.assertFalse(desktop_mcp.enabled("coding"))
            os.environ["CODELABOON_FOREGROUND_TASK"] = "1"
            self.assertTrue(desktop_mcp.enabled("coding"))
            self.assertFalse(desktop_mcp.enabled("security"))
            self.assertIn("--foreground-task", desktop_mcp.stdio()["args"])
