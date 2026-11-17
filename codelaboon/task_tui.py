"""Engine-independent terminal task conversations (optional Textual extra)."""
import json
import uuid
from pathlib import Path
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Input, Label, ListItem, ListView, RichLog, Static,Select,TextArea
from textual.screen import ModalScreen
from textual.containers import VerticalScroll
from codelaboon import task_api


class TaskCreateScreen(ModalScreen):
    """Queue through the same policy and verification boundary as the browser."""
    CSS='''TaskCreateScreen {align: center middle;} #create-box {width: 90%;height: 95%;border: solid #73daca;padding: 1 2;background: #171719;} #create-fields {height: 1fr;} #create-box TextArea {height: 5;} #create-box Label {height: auto;margin-top: 1;} #create-buttons {height: 3;} #create-error {height: auto;max-height: 4;color: #ff9aaa;}'''
    BINDINGS=[('escape','cancel','Cancel'),('ctrl+enter','submit','Queue task')]

    def __init__(self):
        super().__init__()
        from codelaboon.engine_tasks import catalog
        self.engines=catalog()
        self.submitting=False

    def compose(self):
        installed=[(row['id'],row['id']) for row in self.engines if row['installed']]
        with Vertical(id='create-box'):
            yield Label('Create a task / queues and starts the background worker',markup=False)
            with VerticalScroll(id='create-fields'):
                yield Label('Objective');yield TextArea(id='create-objective')
                yield Label('Project directory');yield Input(str(Path.cwd()),id='create-project')
                yield Label('Scope / files and actions allowed');yield Input(placeholder='Describe the boundaries for this task',id='create-scope')
                yield Label('Installed engine')
                yield Select(installed,allow_blank=not installed,id='create-engine',**({'value':installed[0][1]} if installed else {}))
                if not installed:
                    yield Label('No task engine installed. Run one of:\n'+'\n'.join(row['prepare_command'] for row in self.engines),markup=False)
                yield Label('Worker model');yield Input('free',id='create-model')
                yield Label('Verification commands / JSON argument arrays, no shell expansion')
                yield TextArea(placeholder='[["python", "-m", "unittest", "discover", "-s", "tests"]]',id='create-checks')
                yield Label('Verified cycles (0 = continuous until paused)');yield Input('1',id='create-cycles',type='integer')
                yield Label('Coding profile; default tool permissions; no elevation. Models and prompts can be edited in Settings.',markup=False)
            yield Label('',id='create-error',markup=False)
            with Horizontal(id='create-buttons'):
                yield Button('Queue task',id='create-submit',variant='primary',disabled=not installed)
                yield Button('Cancel',id='create-cancel')

    def on_mount(self):self.query_one('#create-objective',TextArea).focus()

    async def action_submit(self):
        button=self.query_one('#create-submit',Button)
        if button.disabled:return
        try:
            body={key:self.query_one('#create-'+key,Input).value for key in ('project','scope','model')}
            body.update(objective=self.query_one('#create-objective',TextArea).text,
                engine=self.query_one('#create-engine',Select).value,
                checks=json.loads(self.query_one('#create-checks',TextArea).text),
                cycles=int(self.query_one('#create-cycles',Input).value),profile='coding')
            button.disabled=True
            self.submitting=True
            self.query_one('#create-cancel',Button).disabled=True
            self.query_one('#create-error',Label).update('Queueing task and starting worker...')
            result=await self.app.run_queue_task(body)
        except (OSError,ValueError,RuntimeError) as error:
            button.disabled=False
            self.submitting=False
            self.query_one('#create-cancel',Button).disabled=False
            self.query_one('#create-error',Label).update(Text(str(error)))
            return
        self.dismiss(result)

    def action_cancel(self):
        if not self.submitting:self.dismiss()

    async def on_button_pressed(self,event):
        event.stop()
        if event.button.id=='create-cancel':self.action_cancel()
        elif event.button.id=='create-submit':await self.action_submit()


class TaskSettingsScreen(ModalScreen):
    CSS='''TaskSettingsScreen {align: center middle;} #settings-box {width: 85%;height: 90%;border: solid #73daca;padding: 1 2;background: #171719;} #settings-fields {height: 1fr;} #settings-buttons {height: 3;} #settings-box TextArea {height: 7;} #settings-box Label {height: auto;margin-top: 1;} #settings-buttons Button {margin-right: 1;}'''
    BINDINGS=[('escape','dismiss','Close')]

    def __init__(self,identity):super().__init__();self.identity=identity;self.row=task_api.settings(identity)

    def compose(self):
        values=self.row['values']
        with Vertical(id='settings-box'):
            yield Label('Task models and system instructions',markup=False)
            with VerticalScroll(id='settings-fields'):
                yield Label('Applies at the next attempt. Active work keeps its captured settings.',markup=False)
                yield Label('Worker / default swarm-agent model');yield Input(values['worker_model'],id='setting-worker')
                yield Label('Planning orchestrator');yield Select([('Embedded worker coordinator','worker'),('Cloud planning model','cloud'),('Local planning model','local')],value=values['orchestrator_mode'],allow_blank=False,id='setting-mode')
                yield Label('Planning model (local/MODEL or PROVIDER/MODEL)');yield Input(values['orchestrator_model'],id='setting-planner')
                yield Label('Additive worker system instructions');yield TextArea(values['worker_system_prompt'],id='setting-system')
                yield Label('Additive planning system instructions');yield TextArea(values['orchestrator_system_prompt'],id='setting-planner-system')
            yield Label(self.row['reason'],id='settings-error',markup=False)
            with Horizontal(id='settings-buttons'):
                yield Button('Save for next attempt',id='settings-save',disabled=not self.row['editable'])
                yield Button('Close',id='settings-close')

    def on_button_pressed(self,event):
        if event.button.id=='settings-close':self.dismiss();return
        if event.button.id!='settings-save':return
        values={'worker_model':self.query_one('#setting-worker',Input).value,'orchestrator_mode':self.query_one('#setting-mode',Select).value,
            'orchestrator_model':self.query_one('#setting-planner',Input).value,'worker_system_prompt':self.query_one('#setting-system',TextArea).text,
            'orchestrator_system_prompt':self.query_one('#setting-planner-system',TextArea).text}
        try:task_api.settings(self.identity,{'values':values,'expected_revision':self.row['revision']});self.dismiss()
        except (OSError,ValueError) as error:self.query_one('#settings-error',Label).update(Text(str(error)))


class TaskChangesScreen(ModalScreen):
    CSS='''TaskChangesScreen {align: center middle;} #changes-box {width: 95%;height: 90%;border: solid #73daca;padding: 1;background: #171719;} #changes-log {height: 1fr;}'''
    BINDINGS=[('escape','dismiss','Close')]
    def __init__(self,identity):super().__init__();self.identity=identity
    def compose(self):
        with Vertical(id='changes-box'):
            yield Label('Project changes / read-only Git evidence')
            yield RichLog(id='changes-log',wrap=True,markup=False)
            yield Button('Close',id='changes-close')
    def on_mount(self):
        row=task_api.changes(self.identity)
        self.query_one('#changes-log',RichLog).write(Text(row['notice']+'\n\n'+('Git metadata unavailable\n' if not row['available'] else '')+row['status']+'\n'+row['stat']+'\n'+row['diff']+'\n\nAttempt observation: '+json.dumps(row['attempt_observation'])))
    def on_button_pressed(self,event):self.dismiss()


class TaskApp(App):
    TITLE='codelaboon / Task conversations'
    BINDINGS=[('ctrl+q','quit','Back to engine'),('ctrl+r','refresh','Refresh'),('ctrl+n','new_task','New task')]
    CSS='''
    Screen {background: #171719; color: #f2f2f3;}
    #heading {height: 5; padding: 1 2; color: #73daca;}
    #heading Button {margin-right: 2;} #heading Static {width: 1fr;}
    #body {height: 1fr;} #tasks {width: 30%; min-width: 20; border-right: solid #45454b;}
    #chat {width: 1fr; padding: 0 1;} #task-title {height: auto; max-height: 4; padding: 1 0;}
    #feed {height: 1fr; border-top: solid #45454b;}
    #hint {height: auto; max-height: 3; color: #a3a3ac;}
    #actions {height: 3;} #actions Button {min-width: 8; margin-right: 1;}
    #compose {height: 3;} #message {width: 1fr;} #send {min-width: 10;}
    #note {height: 3;} #error {height: auto; max-height: 3; color: #ff9aaa;}
    ListItem {height: auto; padding: 1;} Label {width: 100%;}
    '''

    def __init__(self, identity=None):
        super().__init__()
        self.identity=identity
        self.records={}
        self.drafts={}
        self.list_ids=()
        self.signature=''
        self.message_id=None
        self.message_body=None

    def compose(self) -> ComposeResult:
        with Horizontal(id='heading'):
            yield Button('New task',id='new-task',variant='primary')
            yield Static('codelaboon / Task conversations - live worker output')
        with Horizontal(id='body'):
            yield ListView(id='tasks')
            with Vertical(id='chat'):
                yield Static('Choose a task. The orchestrator continues independently.',id='task-title',markup=False)
                yield RichLog(id='feed',wrap=True,markup=False,auto_scroll=True)
                yield Static('',id='hint',markup=False)
                with Horizontal(id='actions'):
                    yield Button('Pause',id='pause')
                    yield Button('Retry failed',id='retry')
                    yield Button('Resume',id='resume')
                    yield Button('Refresh',id='refresh')
                    yield Button('Settings',id='settings')
                    yield Button('Changes',id='changes')
                yield Checkbox('Save note only',id='note')
                with Horizontal(id='compose'):
                    yield Input(placeholder='Guide the next attempt within scope...',max_length=4096,id='message')
                    yield Button('Send',id='send',variant='primary')
                yield Static('',id='error',markup=False)
        yield Footer()

    async def on_mount(self):
        await self.action_refresh()
        self.set_interval(2,self.action_refresh)

    async def action_refresh(self):
        if isinstance(self.screen,ModalScreen):return
        try:
            state=task_api.snapshot()
            self.records={task['id']:task for task in state['tasks']}
            ids=tuple(self.records)
            listing=self.query_one('#tasks',ListView)
            if ids!=self.list_ids:
                await listing.clear()
                for identity,task in self.records.items():
                    item=ListItem(Label(Text(task['title']+'\n'+task['engine']+' / '+task['state'])))
                    item.task_identity=identity
                    await listing.append(item)
                self.list_ids=ids
            else:
                for item,task in zip(listing.children,self.records.values()):
                    item.query_one(Label).update(Text(task['title']+'\n'+task['engine']+' / '+task['state']))
            if self.identity in self.records:
                self.show_conversation(state)
            elif self.identity:
                self.query_one('#task-title',Static).update('Task not found in this worker configuration: '+self.identity)
            elif not self.records:
                self.query_one('#task-title',Static).update('No tasks queued. Choose New task or press Ctrl+N to create one here.')
            self.query_one('#send',Button).disabled=self.identity not in self.records
        except (OSError,ValueError,KeyError,TypeError) as error:self.query_one('#error',Static).update('Refresh failed: '+str(error))

    def show_conversation(self,state):
        task=self.records[self.identity]
        self.query_one('#task-title',Static).update(task['title']+'\n'+task['engine']+' / '+task['state']+' / '+str(task.get('cycles_completed',0))+' verified cycles')
        compatible=not state['worker']['running'] or 'operator-interventions' in state['worker'].get('service',{}).get('features',[])
        notes_only=not compatible or task['elevation']!='none' or task['state'] in ('stopped','completed')
        note=self.query_one('#note',Checkbox)
        if notes_only:note.value=True
        note.disabled=notes_only
        self.query_one('#hint',Static).update('Notes only: older worker, finished task or immutable elevated case.' if notes_only else 'Guidance joins the next attempt. Active work and independent checks finish first.')
        for action in ('pause','resume'):
            self.query_one('#'+action,Button).disabled=task['state'] in ('stopped','completed') or ((task['state']=='paused')==(action=='pause'))
        self.query_one('#retry',Button).disabled=not ('failed' in task['state'] or 'retry' in task['state']) or task.get('elevation','none')!='none'
        conversation=task_api.conversation(self.identity)
        output=task_api.logs(self.identity)
        signature=json.dumps([self.identity,conversation,output],sort_keys=True)
        if signature==self.signature:return
        feed=self.query_one('#feed',RichLog)
        follow=feed.is_vertical_scroll_end or not self.signature
        scroll=feed.scroll_y
        feed.clear()
        feed.write(Text('You / objective',style='bold cyan'));feed.write(Text(task['objective']))
        rows=[{**row,'role':'Orchestrator / execution update'} for row in conversation['events']]
        rows += [{**row,'role':'You'} for row in conversation['messages']]
        for row in sorted(rows,key=lambda row:row['created']):
            feed.write(Text('\n'+row['role'],style='bold cyan'));feed.write(Text(row['text']))
            if row.get('delivery'):feed.write(Text(row['delivery'],style='dim'))
        if output['text']:
            feed.write(Text('\nWorker / latest captured output',style='bold cyan'));feed.write(Text(output['text']))
        self.signature=signature
        if follow:feed.scroll_end(animate=False)
        else:feed.scroll_to(y=scroll,animate=False)

    async def on_list_view_selected(self,event:ListView.Selected):
        if self.identity:self.drafts[self.identity]=self.query_one('#message',Input).value
        self.identity=event.item.task_identity
        self.signature=''
        self.query_one('#message',Input).value=self.drafts.get(self.identity,'')
        self.query_one('#error',Static).update('')
        await self.action_refresh()
        self.query_one('#message',Input).focus()

    async def on_input_submitted(self,event:Input.Submitted):
        if event.input.id=='message':await self.send_message()

    async def on_button_pressed(self,event:Button.Pressed):
        action=event.button.id
        if action=='new-task':self.action_new_task()
        elif action=='send':await self.send_message()
        elif action in ('settings','changes') and self.identity in self.records:
            try:self.push_screen(TaskSettingsScreen(self.identity) if action=='settings' else TaskChangesScreen(self.identity))
            except (OSError,ValueError) as error:self.query_one('#error',Static).update(str(error))
        elif action=='refresh':await self.action_refresh()
        elif action in ('pause','resume','retry') and self.identity in self.records:
            try:task_api.control(self.identity,action);await self.action_refresh()
            except (OSError,ValueError) as error:self.query_one('#error',Static).update(str(error))

    def action_new_task(self):
        if isinstance(self.screen,ModalScreen):return
        self.push_screen(TaskCreateScreen(),self.task_created)

    async def run_queue_task(self,body):
        import asyncio
        return await asyncio.to_thread(task_api.enqueue,body)

    async def task_created(self,result):
        if not result:return
        if self.identity:self.drafts[self.identity]=self.query_one('#message',Input).value
        self.identity=result['task'];self.signature=''
        self.query_one('#message',Input).value=''
        await self.action_refresh()
        self.query_one('#error',Static).update(Text(result['message']))

    async def send_message(self):
        if self.identity not in self.records:return
        message=self.query_one('#message',Input)
        body={'task':self.identity,'text':message.value,'mode':'note' if self.query_one('#note',Checkbox).value else 'guidance'}
        if body!=self.message_body:self.message_id=uuid.uuid4().hex;self.message_body=body
        try:
            task_api.message({**body,'message_id':self.message_id})
            message.value='';self.drafts.pop(self.identity,None);self.message_body=None
            self.query_one('#error',Static).update('')
            await self.action_refresh()
        except (OSError,ValueError,RuntimeError) as error:self.query_one('#error',Static).update(str(error))
