import tempfile
from pathlib import Path
import unittest
from codelaboon.task_conversation import post,history,context,included
class Conversation(unittest.TestCase):
 def test_guidance_receipts_idempotency_and_notes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);task={'id':'fixture','scope':'local only'}
   post(root,'fixture','one','Focus on regression evidence')
   post(root,'fixture','one','Focus on regression evidence')
   post(root,'fixture','two','Private review note','note')
   self.assertEqual(len(history(root,'fixture')),2)
   text,ids=context(root,task)
   self.assertIn('subordinate',text);self.assertNotIn('Private review',text)
   self.assertEqual(ids,['one']);self.assertEqual(history(root,'fixture')[0]['delivery'],'Queued for next attempt')
   included(root,'fixture',ids,'attempt-fixture')
   self.assertIn('Included in attempt',history(root,'fixture')[0]['delivery'])
   with self.assertRaises(ValueError):post(root,'fixture','one','Different')
 def test_privilege_boundary_and_validation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);post(root,'fixture','one','guidance')
   for task in ({'id':'fixture','elevation':'root'},{'id':'fixture','_privileged_case':True}):self.assertEqual(context(root,task),('',[]))
   for identity,text in (('../escape','hello'),('valid',''),('valid','x'*4097)):
    with self.assertRaises(ValueError):post(root,'fixture',identity,text)
if __name__=='__main__':unittest.main()
