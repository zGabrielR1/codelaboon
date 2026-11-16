"""Read-only live task status and log rotation across swarm cycles."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codelaboon import work_monitor as monitor


class LiveMonitoring(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.state={'runtime':str(self.root),'running':True,'paused':False,'cooldowns':{'swarm-one':45},
            'pending':[{'id':'one','project':'project','swarm':{'controller':'worker'},'cycles_completed':0,
                        'paused':False,'stopped':False,'permissions':'full','profile':'security','elevation':'none'}]}
    def attempt(self,name,started,status='failed',text='model rate limited\n'):
        root=self.root/name;root.mkdir()
        (root/'result.json').write_text(json.dumps({'task':'one','status':status,'exit_code':1,'started':started,'stage':'build'}))
        (root/'output.log').write_text(text)
        return root
    def test_failed_cycles_show_retry_and_latest_attempt_instead_of_scheduled(self):
        self.attempt('old',1);latest=self.attempt('new',2)
        with patch('codelaboon.work.status',return_value=self.state):
            state=monitor.snapshot(task_id='one')
        row=state['pending'][0]
        self.assertEqual(row['state'],'retry wait');self.assertEqual(row['cooldown_seconds'],45)
        self.assertEqual(row['last_attempt']['logs'],str(latest))
        self.assertEqual(row['cycles_completed'],0)
    def test_log_follow_switches_to_new_attempt_and_does_not_change_task_state(self):
        self.attempt('first',1,text='first-cycle\n')
        calls=[]
        def advance(seconds):
            calls.append(seconds)
            if len(calls)==1:self.attempt('second',2,text='second-cycle\n')
            else:raise KeyboardInterrupt
        with patch('codelaboon.work.status',return_value=self.state),patch('codelaboon.work.configuration',return_value=(None,{},self.root)),patch.object(monitor.time,'sleep',side_effect=advance),patch('sys.stdout',new_callable=io.StringIO) as output:
            monitor.logs(task_id='one',follow=True)
        self.assertIn('first-cycle',output.getvalue());self.assertIn('second-cycle',output.getvalue())
        self.assertFalse((self.root/'PAUSE').exists());self.assertFalse((self.root/'STOP').exists())
    def test_watch_emits_json_and_ctrl_c_only_closes_the_view(self):
        with patch('codelaboon.work.status',return_value=self.state),patch.object(monitor.time,'sleep',side_effect=KeyboardInterrupt),patch('sys.stdout',new_callable=io.StringIO) as output:
            monitor.watch(task_id='one',as_json=True)
        value=json.loads(output.getvalue())
        self.assertEqual(value['pending'][0]['id'],'one')
        self.assertFalse((self.root/'STOP').exists())
    def test_completed_task_is_distinguished_from_missing(self):
        self.state['pending']=[]
        (self.root/'state.json').write_text('{"done":["one"]}')
        with patch('codelaboon.work.status',return_value=self.state):
            self.assertEqual(monitor.snapshot(task_id='one')['selected_task']['state'],'completed')
            self.assertIn('not found',monitor.snapshot(task_id='unknown')['selected_task']['state'])
