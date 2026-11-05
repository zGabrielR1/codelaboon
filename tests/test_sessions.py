import json
from pathlib import Path
import tempfile
import unittest
from codelaboon.sessions import save_session,list_sessions

class SessionTests(unittest.TestCase):
    def test_roundtrip_and_corrupt_file_isolation(self):
        with tempfile.TemporaryDirectory() as root:
            item={'id':'a'*32,'title':'Saved idea','provider':'test','model':'model','messages':[{'role':'user','content':'hello'},{'role':'assistant','content':'reply'}]}
            save_session(root,item)
            (Path(root)/'sessions'/'broken.json').write_text('{bad')
            rows=list_sessions(root)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['messages'],item['messages'])
            item['title']='Renamed'
            save_session(root,item)
            self.assertEqual(list_sessions(root)[0]['title'],'Renamed')
            self.assertEqual(list((Path(root)/'sessions').glob('*.tmp')),[])
    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):save_session(root,{'id':'../escape'})
    def test_invalid_messages_are_not_resumed(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'sessions';folder.mkdir()
            (folder/('a'*32+'.json')).write_text(json.dumps({'id':'a'*32,'title':'x','provider':'test','model':'x','updated_at':'now','messages':[{'role':'bad','content':'x'}]}))
            self.assertEqual(list_sessions(root),[])
