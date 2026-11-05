import tempfile
import unittest
from unittest.mock import patch
from codelaboon.tui import CodelaboonTuiApp, ChatGPTLogin, Picker
from textual.widgets import Input

class TuiFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_select_chatgpt_offers_login_inside_tui(self):
        app=CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch.object(app.cli.providers['chatgpt'],'validate_api_key',return_value=False):
                app._select_provider('chatgpt')
                await pilot.pause()
                self.assertIsInstance(app.screen,ChatGPTLogin)
                await pilot.click('#later-login')
                await pilot.pause()
                self.assertNotIsInstance(app.screen,ChatGPTLogin)
    async def test_login_success_refreshes_models_without_changing_other_provider(self):
        app=CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app._current_provider='chatgpt'
            dialog=ChatGPTLogin()
            app.push_screen(dialog)
            await pilot.pause()
            with patch.object(app,'_load_models') as load:
                app._login_done(dialog,True)
                load.assert_called_once_with('chatgpt')
            await pilot.pause()
            self.assertFalse(app._login_pending)
    async def test_provider_picker_and_sidebar_shortcuts(self):
        app=CodelaboonTuiApp()
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            app.action_focus_providers()
            await pilot.pause()
            self.assertIsInstance(app.screen,Picker)
            app.screen.query_one(Input).value='nvidia'
            await pilot.pause()
            self.assertEqual(app.screen.filtered[0][0],'nvidia')
            await pilot.press('escape')
            await pilot.pause()
            sidebar=app.query_one('#sidebar')
            self.assertGreater(sidebar.region.x,app.query_one('#main').region.x)
            before=sidebar.display
            await pilot.press('ctrl+b')
            self.assertNotEqual(sidebar.display,before)
    async def test_new_conversation_restores_home(self):
        app=CodelaboonTuiApp()
        async with app.run_test(size=(80,24)) as pilot:
            await pilot.pause()
            app.query_one('#body').remove_class('home')
            app.query_one('#home').display=False
            app.action_new_conversation()
            self.assertTrue(app.query_one('#body').has_class('home'))
            self.assertTrue(app.query_one('#home').display)
