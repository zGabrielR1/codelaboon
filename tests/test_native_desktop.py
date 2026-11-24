import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from codelaboon import desktop_mcp
from codelaboon.desktop import Browser
from codelaboon.native_desktop import DesktopSession
from codelaboon.work_queue import swarm_harness, validate_swarm


class DesktopBrowserTests(unittest.TestCase):
    def test_failed_snapshot_reports_successful_click_without_retrying_it(self):
        browser = Browser(headless=True)
        self.addCleanup(browser.close)
        browser.browser = Mock()
        browser.browser.is_connected.return_value = True
        browser.page = Mock(url="http://127.0.0.1/next")
        browser.page.is_closed.return_value = False
        browser.page.locator.return_value.aria_snapshot.side_effect = RuntimeError("snapshot timed out")

        result = browser.call("click", selector="a")

        self.assertIn("action completed", result["message"])
        self.assertEqual(result["url"], "http://127.0.0.1/next")
        browser.page.locator.return_value.click.assert_called_once_with()
        with self.assertRaisesRegex(ValueError, "Could not read the page snapshot"):
            browser.call("snapshot")

    def test_navigate_recovers_from_disconnected_chromium(self):
        browser = Browser(headless=True)
        self.addCleanup(browser.close)
        old_runtime = browser.runtime = Mock()
        browser.browser = Mock()
        browser.browser.is_connected.return_value = False
        browser.page = Mock()
        browser.page.is_closed.return_value = False
        playwright = Mock()
        runtime = playwright.sync_playwright.return_value.start.return_value
        page = runtime.chromium.launch.return_value.new_page.return_value
        page.url = "http://127.0.0.1/"
        page.locator.return_value.aria_snapshot.return_value = "Recovered page"
        with patch.dict("sys.modules", {"playwright.sync_api": playwright}):
            self.assertEqual(browser.call("navigate", url=page.url)["snapshot"], "Recovered page")
        old_runtime.stop.assert_called_once_with()
        page.goto.assert_called_once_with(page.url, wait_until="domcontentloaded")


class NativeDesktopTests(unittest.TestCase):
    def test_failed_capture_revokes_the_old_frame_and_releases_the_desktop(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "codelaboon.native_desktop.data_dir", return_value=Path(directory)
        ), patch("codelaboon.native_desktop.sys.platform", "test"):
            driver = Mock()
            driver.size.return_value = (640, 480)
            screenshot = Mock(size=(640, 480))
            driver.screenshot.side_effect = [screenshot, OSError("capture failed"), screenshot]
            first, second = DesktopSession(), DesktopSession()
            with patch.dict("sys.modules", {"pyautogui": driver}):
                try:
                    frame, _, _, _ = first.observe()
                    with self.assertRaisesRegex(OSError, "capture failed"):
                        first.observe()
                    self.assertIsNone(first.lease)
                    with self.assertRaisesRegex(ValueError, "Observe"):
                        first.act(frame, "click", x=10, y=10)
                    self.assertIsNone(first.lease)
                    second.observe()
                    driver.click.assert_not_called()
                finally:
                    first.close()
                    second.close()

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
