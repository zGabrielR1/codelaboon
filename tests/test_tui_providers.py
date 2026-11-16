"""TUI setup and welcome layout checks without provider network calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from textual.widgets import Input, Static
from codelaboon.tui import CodelaboonTuiApp, ProviderKey


class TuiProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_wusrouter_setup_and_switch_key(self):
        app = CodelaboonTuiApp()
        with patch.object(app, "_load_models") as load:
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                self.assertIn("wusrouter", app.cli.providers)
                with patch.object(app.cli.providers["wusrouter"], "validate_api_key", return_value=False):
                    app._select_provider("wusrouter")
                await pilot.pause()
                self.assertIsInstance(app.screen, ProviderKey)
                app._busy = True
                app._current_model = "old-account-model"
                generation = app._generation
                app.screen.query_one("#provider-key", Input).value = "new-account-key"
                with patch("config.providers.save_provider_config", return_value=True) as save:
                    await pilot.click("#key-save")
                    await pilot.pause()
                self.assertEqual(save.call_args.args[0], "wusrouter")
                self.assertEqual(save.call_args.args[1]["api_key"], "new-account-key")
                load.assert_called_with("wusrouter")
                self.assertFalse(app._busy)
                self.assertIsNone(app._current_model)
                self.assertGreater(app._generation, generation)
                await pilot.press("ctrl+k")
                await pilot.pause()
                self.assertIsInstance(app.screen, ProviderKey)
                await pilot.click("#key-later")
                app._select_provider("qoder", prompt_login=False)
                await pilot.press("ctrl+k")
                await pilot.pause()
                self.assertEqual(app.screen.provider, "qoder")

    async def test_welcome_layout_at_desktop_and_small_terminal(self):
        for width in (120, 80, 40):
            app = CodelaboonTuiApp()
            with patch.object(app, "_load_models"):
                async with app.run_test(size=(width, 40)) as pilot:
                    await pilot.pause()
                    home = app.query_one("#home", Static)
                    self.assertTrue(home.display)
                    self.assertLessEqual(max(map(len, app._welcome(width - 8).splitlines())), width - 8)
                    if width == 120:
                        self.assertIn("/ __/", str(home.content))
                        with tempfile.TemporaryDirectory() as directory:
                            screenshot = app.save_screenshot("codelaboon-welcome.svg", path=directory)
                            self.assertTrue(Path(screenshot).is_file())
