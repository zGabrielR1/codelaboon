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

    async def test_saved_session_resume_and_stale_catalogue(self):
        from codelaboon.sessions import list_sessions
        app=CodelaboonTuiApp()
        with tempfile.TemporaryDirectory() as root:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.cli.config_dir=__import__('pathlib').Path(root)
                app._current_provider='chatgpt'
                app._current_model='saved-model'
                app.history=[{'role':'user','content':'Remember this'},{'role':'assistant','content':'Saved answer'}]
                app._save_conversation()
                saved=list_sessions(root)
                self.assertEqual(len(saved),1)
                app.action_new_conversation()
                app._saved_sessions={saved[0]['id']:saved[0]}
                with patch.object(app,'_load_models'):
                    app._resume_session(saved[0]['id'])
                self.assertEqual(app.history[-1]['content'],'Saved answer')
                app._discovery=12
                app._models_result(11,'chatgpt',['stale-model'],'')
                self.assertEqual(app._current_model,'saved-model')
    async def test_busy_submission_preserves_draft(self):
        from textual.widgets import Input
        app=CodelaboonTuiApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            field=app.query_one('#prompt',Input)
            app._busy=True
            field.value='Keep this draft'
            app.on_input_submitted(Input.Submitted(field,field.value))
            self.assertEqual(field.value,'Keep this draft')
