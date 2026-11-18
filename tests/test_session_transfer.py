import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from codelaboon.session_transfer import decode,encode,save,load,write_export,read_file,library

class TransferTests(unittest.TestCase):
    def source(self):
        return {'info':{'id':'ses_original','directory':'/project','title':'Work'},'messages':[
            {'info':{'role':'user'},'parts':[{'type':'text','text':'Preserve nonce A12'}]},
            {'info':{'role':'assistant'},'parts':[{'type':'text','text':'Implemented A12'},{'type':'tool','tool':'read','state':{'output':'file data'}}]}]}
    def test_cross_format_conversation_roundtrip(self):
        doc=decode('opencode',self.source(),'source')
        for engine in ('codex','claude','omp','opencode','kilo','jcode','crush'):
            with self.subTest(engine=engine):
                identity,value=encode(doc,engine)
                other=decode(engine,value,'export')
                self.assertEqual(other['origin']['native_id'],identity)
                self.assertEqual(other['messages'],doc['messages'])
    def test_omp_installs_windows_project_in_native_session_directory(self):
        from codelaboon.session_transfer import install_export

        cwd = r'D:\Downloads\stuff\project'
        document = decode('opencode', self.source(), 'source')
        identity, payload = encode(document, 'omp', cwd)
        with tempfile.TemporaryDirectory() as home:
            resolve = Path.resolve

            def resolve_project(path):
                return cwd if str(path) == cwd else resolve(path)

            with patch.object(Path, 'resolve', resolve_project):
                target = install_export('omp', payload, identity, home, cwd)
            self.assertEqual(target.parent.name, '--D--Downloads-stuff-project--')
            self.assertEqual(decode('omp', read_file(target))['messages'], document['messages'])

    def test_library_deduplicates_and_preserves_native_archives(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,CODELABOON_DATA_DIR=root):
            doc=decode('opencode',self.source(),'original.json');identity=save(doc)
            self.assertEqual(save(doc),identity)
            self.assertEqual(load(identity)['messages'],doc['messages'])
            _,value=encode(doc,'codex');other=decode('codex',value,'rollout.jsonl');save(other,identity)
            with library() as db:self.assertEqual(db.execute('SELECT count(*) FROM snapshots WHERE session_id=?',(identity,)).fetchone()[0],2)
    def test_exports_are_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'session.jsonl';_,value=encode(decode('opencode',self.source()),'codex')
            write_export(path,value)
            if os.name != 'nt':self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(read_file(path),value)
            with self.assertRaises(FileExistsError):write_export(path,value)
    def test_history_policy_and_foreign_tools_are_inert(self):
        doc=decode('opencode',self.source());doc['messages'].insert(0,{'role':'system','content':'Source-specific instructions'})
        _,value=encode(doc,'codex');messages=[r['payload'] for r in value if r['type']=='response_item']
        self.assertEqual(messages[0]['role'],'user')
        self.assertTrue(all(r['type']=='message' for r in messages))
    def test_omp_branches_do_not_merge(self):
        rows=[{'type':'session','id':'native','cwd':'/project'},
              {'type':'message','id':'a','parentId':None,'message':{'role':'user','content':'start'}},
              {'type':'message','id':'b','parentId':'a','message':{'role':'assistant','content':'abandoned'}},
              {'type':'message','id':'c','parentId':'a','message':{'role':'assistant','content':'active'}}]
        doc=decode('omp',rows)
        self.assertEqual([m['content'] for m in doc['messages']],['start','active'])
    def test_compaction_keeps_summary_and_retained_tail(self):
        rows=[{'type':'session','id':'native','cwd':'/project'},
              {'type':'message','id':'a','parentId':None,'message':{'role':'user','content':'old'}},
              {'type':'message','id':'b','parentId':'a','message':{'role':'assistant','content':'retained'}},
              {'type':'compaction','id':'c','parentId':'b','firstKeptEntryId':'b','summary':'saved decisions'}]
        messages=decode('omp',rows)['messages']
        self.assertEqual(len(messages),2)
        self.assertIn('saved decisions',messages[0]['content'])
        self.assertEqual(messages[1]['content'],'retained')
    def test_codex_linked_prefix_is_materialized(self):
        from codelaboon.session_transfer import read_source
        import uuid
        with tempfile.TemporaryDirectory() as root:
            parent_id=str(uuid.uuid4());child_id=str(uuid.uuid4())
            folder=Path(root)/'sessions/2026/11/15';folder.mkdir(parents=True)
            parent=[{'type':'session_meta','payload':{'id':parent_id}}, {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'parent context'}]}}]
            path=write_export(folder/('rollout-'+parent_id+'.jsonl'),parent)
            offset=path.stat().st_size
            with path.open('a') as stream:stream.write(json.dumps({'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'excluded later parent turn'}]}})+'\n')
            child=[{'type':'session_meta','payload':{'id':child_id,'history_base':{'thread_id':parent_id,'end_ordinal_exclusive':2,'end_byte_offset':offset}}},
                   {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'child reply'}]}}]
            target=write_export(folder/('rollout-'+child_id+'.jsonl'),child)
            document=read_source('codex',str(target))
            self.assertEqual([m['content'] for m in document['messages']],['parent context','child reply'])
            self.assertEqual(document['origin']['native_id'],child_id)
    def test_converter_does_not_open_library(self):
        from codelaboon.session_transfer import main
        with tempfile.TemporaryDirectory() as root,patch('codelaboon.session_transfer.library',side_effect=AssertionError('Library used')):
            source=Path(root)/'original.json';source.write_text(json.dumps(self.source()))
            main(['convert','--from','opencode','--source',str(source),'--to','codex','--output',str(Path(root)/'rollout.jsonl')])
    def test_unchanged_private_files_are_not_reparsed(self):
        from codelaboon.session_transfer import sync_private
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,CODELABOON_CONFIG_DIR=root+'/config',CODELABOON_DATA_DIR=root+'/data'):
            folder=Path(root)/'config/codex/sessions';folder.mkdir(parents=True)
            _,value=encode(decode('opencode',self.source()),'codex')
            write_export(folder/'rollout.jsonl',value)
            self.assertEqual(sync_private(),1)
            with patch('codelaboon.session_transfer.read_source',side_effect=AssertionError('Reparsed unchanged')):
                self.assertEqual(sync_private(),0)
    def test_codex_compaction_replacement_is_used(self):
        rows=[{'type':'session_meta','payload':{'id':'native','cwd':'/project'}},
              {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'superseded'}]}},
              {'type':'compacted','payload':{'message':'summary','replacement_history':[
                  {'type':'message','role':'user','content':[{'type':'input_text','text':'summary and decisions'}]},
                  {'type':'message','role':'assistant','content':[{'type':'output_text','text':'retained recent turn'}]}]}}]
        self.assertEqual([m['content'] for m in decode('codex',rows)['messages']],['summary and decisions','retained recent turn'])
