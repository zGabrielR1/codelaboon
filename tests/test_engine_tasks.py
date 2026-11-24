"""Native headless protocols: explicit completion, failure and engine routing."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from codelaboon import engine_tasks as tasks
from codelaboon.work_queue import validate_swarm,swarm_harness


class EngineTasks(unittest.TestCase):
    def run_engine(self,engine,payload,code=0):
        process=MagicMock(returncode=code)
        process.wait.return_value=code;process.poll.return_value=code
        process.communicate.return_value=(payload,None);process.stdout=io.StringIO(payload)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prompt=root/'prompt.md';prompt.write_text('Only inspect local fixture files')
            with patch.object(tasks.subprocess,'Popen',return_value=process) as spawn:
                result=tasks.run(engine,'free',prompt,root)
                command=spawn.call_args.args[0]
                self.assertIn(engine,command)
                self.assertEqual(spawn.call_args.kwargs['env']['CODELABOON_TASK_MODEL'],'free')
                return result
    def test_all_seven_completion_protocols(self):
        stream=lambda rows:''.join(json.dumps(row)+'\n' for row in rows)
        values={
            'jcode':json.dumps({'text':'Verified fixture'}),
            'opencode':stream([{'type':'text','part':{'text':'Verified fixture'}},{'type':'step_finish','part':{'reason':'stop'}}]),
            'kilo':stream([{'type':'text','part':{'text':'Verified fixture'}},{'type':'step_finish','part':{'reason':'stop'}}]),
            'omp':stream([{'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'Verified fixture'}],'stopReason':'stop'}}]),
            'claude':json.dumps({'type':'result','subtype':'success','is_error':False,'result':'Verified fixture'}),
            'codex':stream([{'type':'item.completed','item':{'type':'agent_message','text':'Verified fixture'}},{'type':'turn.completed'}]),
            'crush':'Verified fixture',
        }
        for engine,payload in values.items():
            with self.subTest(engine=engine):self.assertEqual(self.run_engine(engine,payload),'Verified fixture')
    def test_partial_and_failed_responses_do_not_become_success(self):
        values={'opencode':'{"type":"text","part":{"text":"partial"}}\n','kilo':'{"type":"error"}\n',
            'omp':'{"type":"message_end","message":{"role":"assistant","content":[],"stopReason":"error"}}\n',
            'claude':'{"subtype":"error","is_error":true,"result":"partial"}',
            'codex':'{"type":"turn.failed"}\n','jcode':'{"text":""}','crush':''}
        for engine,payload in values.items():
            with self.subTest(engine=engine),self.assertRaises(RuntimeError):self.run_engine(engine,payload)

    def test_malformed_protocol_fields_report_the_engine_and_field(self):
        cases = [
            ('claude', 'not JSON', 'final response'),
            ('jcode', '[]', 'final response'),
            ('opencode', '{"type":"text","part":null}\n', 'text event part'),
            ('kilo', '{"type":"step_finish","part":[]}\n', 'step_finish event part'),
            ('codex', '{"type":"item.completed","item":null}\n', 'completed item'),
            ('omp', '{"type":"message_end","message":{"role":"assistant","content":null}}\n', 'assistant content'),
            ('omp', '{"type":"message_end","message":{"role":"assistant","content":[null]}}\n', 'assistant content entry'),
        ]
        for engine, payload, field in cases:
            with self.subTest(engine=engine, field=field), self.assertRaisesRegex(RuntimeError, f'{engine}.*{field}'):
                self.run_engine(engine, payload)

    def test_portable_coordination_and_native_swarm_are_distinct(self):
        base=dict(controller='worker',workers=1,timeout=30,interval=60,cycles=0,model='free')
        for engine in tasks.ENGINES:
            options=validate_swarm({**base,'engine':engine,'model':'devin/account-default' if engine=='devin' else 'free'})
            harness=swarm_harness({'id':'fixture','swarm':options})
            self.assertEqual(harness['argv'][-2:],['--engine',engine])
        with self.assertRaises(ValueError):validate_swarm({**base,'engine':'claude','workers':4})
        with self.assertRaises(ValueError):validate_swarm({**base,'engine':'unknown'})
