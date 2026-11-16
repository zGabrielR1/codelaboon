"""Task entry points must not start an engine or model just to inspect work."""
import importlib.util
import io
import json
import os
import sys
import unittest
from unittest.mock import patch

from codelaboon import cli,task_console


class TaskEntrypoints(unittest.TestCase):
    def test_all_engine_aliases_open_the_same_task_without_inference(self):
        for engine in ('opencode','omp','jcode','codex','claude','kilo','crush'):
            with self.subTest(engine=engine),patch('sys.argv',['codelaboon',engine,'--tasks','instruction-fixture']),patch.object(task_console,'main') as tasks,patch('codelaboon.native_tui.launch') as native:
                cli.main()
                tasks.assert_called_once_with(['instruction-fixture']);native.assert_not_called()

    def test_tasks_list_does_not_load_providers(self):
        with patch('sys.argv',['codelaboon','tasks','--json']),patch('codelaboon.task_api.snapshot',return_value={'worker':{'running':False},'tasks':[]}),patch.object(cli.CodelaboonCLI,'load_providers') as load,patch('sys.stdout',new_callable=io.StringIO) as output:
            cli.main();self.assertEqual(json.loads(output.getvalue())['tasks'],[]);load.assert_not_called()

    def test_interactive_launcher_exposes_tasks_and_returns_to_engine(self):
        with patch('sys.stdout',new_callable=io.StringIO) as output,patch('sys.stdin.isatty',return_value=True),patch('sys.stdout.isatty',return_value=True),patch('builtins.input',side_effect=['t','']),patch('codelaboon.task_api.snapshot',return_value={'tasks':[]}),patch.object(task_console,'open_tasks') as tasks,patch.dict(os.environ,{'CODELABOON_HEADLESS_TASK':'0','CODELABOON_DIRECT':'0'}):
            self.assertTrue(task_console.launcher('opencode',[]));tasks.assert_called_once()
            self.assertIn('Task conversations',output.getvalue())

    def test_automation_and_native_flags_skip_launcher(self):
        with patch('builtins.input') as prompt:
            self.assertTrue(task_console.launcher('codex',['exec','fixture']))
            with patch.dict(os.environ,CODELABOON_HEADLESS_TASK='1'):self.assertTrue(task_console.launcher('omp',[]))
            prompt.assert_not_called()

    def test_browser_opens_the_requested_conversation_on_available_port(self):
        with patch('codelaboon.web.serve') as serve:
            task_console.browser('instruction-fixture')
            serve.assert_called_once_with(0,start_path='/tasks?task=instruction-fixture')


@unittest.skipUnless(importlib.util.find_spec('textual'),'Optional terminal UI extra not installed')
class TerminalTaskConversation(unittest.IsolatedAsyncioTestCase):
    async def test_open_follow_output_send_guidance_and_preserve_draft(self):
        from codelaboon.task_tui import TaskApp
        from textual.widgets import Input,RichLog,Static
        task={'id':'fixture','title':'Fixture objective','objective':'Work only on fixture files',
              'state':'active attempt','engine':'omp','elevation':'none','cycles_completed':0}
        state={'tasks':[task,{**task,'id':'second','title':'Second task'}],
               'worker':{'running':True,'service':{'features':['operator-interventions']}}}
        conversation={'events':[],'messages':[]}
        output={'text':'fixture live output','attempt':'a'}
        with patch('codelaboon.task_api.snapshot',return_value=state),patch('codelaboon.task_api.conversation',return_value=conversation),patch('codelaboon.task_api.logs',return_value=output),patch('codelaboon.task_api.message') as send:
            app=TaskApp('fixture')
            async with app.run_test(size=(110,35)) as pilot:
                await pilot.pause()
                self.assertIn('Fixture objective',str(app.query_one('#task-title',Static).render()))
                self.assertGreater(len(app.query_one('#feed',RichLog).lines),0)
                app.query_one('#message',Input).value='Prioritize the fixture regression'
                await pilot.click('#send');await pilot.pause()
                self.assertEqual(send.call_args.args[0]['task'],'fixture')
                self.assertEqual(send.call_args.args[0]['mode'],'guidance')
                self.assertEqual(app.query_one('#message',Input).value,'')
                output['text']='fixture output updated';await app.action_refresh()
                self.assertIn('fixture output updated',app.signature)

    async def test_older_workers_are_explicitly_note_only(self):
        from codelaboon.task_tui import TaskApp
        from textual.widgets import Checkbox
        task={'id':'fixture','title':'Fixture','objective':'Fixture','state':'queued','engine':'jcode','elevation':'none'}
        with patch('codelaboon.task_api.snapshot',return_value={'tasks':[task],'worker':{'running':True,'service':{'features':[]}}}),patch('codelaboon.task_api.conversation',return_value={'events':[],'messages':[]}),patch('codelaboon.task_api.logs',return_value={'text':''}):
            app=TaskApp('fixture')
            async with app.run_test(size=(90,30)) as pilot:
                await pilot.pause();self.assertTrue(app.query_one('#note',Checkbox).value);self.assertTrue(app.query_one('#note',Checkbox).disabled)
    async def test_terminal_settings_dialog_saves_model_and_prompt_at_checkpoint(self):
        from codelaboon.task_tui import TaskApp
        from codelaboon.task_settings import defaults
        from textual.widgets import Input,TextArea
        task={'id':'fixture','title':'Fixture','objective':'Fixture','state':'queued','engine':'jcode','elevation':'none'}
        row={'revision':'initial','values':defaults(task),'reason':'','editable':True}
        with patch('codelaboon.task_api.snapshot',return_value={'tasks':[task],'worker':{'running':False}}),patch('codelaboon.task_api.conversation',return_value={'events':[],'messages':[]}),patch('codelaboon.task_api.logs',return_value={'text':''}),patch('codelaboon.task_api.settings',return_value=row) as save:
            app=TaskApp('fixture')
            async with app.run_test(size=(110,45)) as pilot:
                await pilot.pause();await pilot.click('#settings');await pilot.pause()
                app.screen.query_one('#setting-worker',Input).value='nvidia/fixture'
                app.screen.query_one('#setting-system',TextArea).load_text('Prefer regression evidence')
                await app.action_refresh()  # A periodic refresh must not query the hidden main screen.
                app.screen.query_one('#settings-save').scroll_visible();await pilot.pause();await pilot.click('#settings-save');await pilot.pause()
                writes=[call.args[1] for call in save.call_args_list if len(call.args)>1]
                self.assertEqual(len(writes),1)
                self.assertEqual(writes[0]['values']['worker_model'],'nvidia/fixture')
                self.assertEqual(writes[0]['values']['worker_system_prompt'],'Prefer regression evidence')
