import json
import unittest
from unittest.mock import Mock
from codelaboon.responses_bridge import to_chat, ResponsesResponse

class ResponsesBridgeTests(unittest.TestCase):
    def test_function_and_custom_results_keep_call_ids(self):
        body={'model':'free','input':[{'type':'function_call','call_id':'a','name':'exec_command','arguments':'{"cmd":"pwd"}'},
             {'type':'function_call_output','call_id':'a','output':'/project'},
             {'type':'custom_tool_call','call_id':'b','name':'apply_patch','input':'patch'},
             {'type':'custom_tool_call_output','call_id':'b','output':'done'}]}
        messages=to_chat(body)['messages']
        self.assertEqual(messages[1]['tool_call_id'],'a')
        self.assertEqual(json.loads(messages[2]['tool_calls'][0]['function']['arguments']),{'input':'patch'})
        self.assertEqual(messages[3]['tool_call_id'],'b')

    def test_response_stream_has_completion_and_native_custom_tool(self):
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'tool_calls':[{'id':'a','function':{'name':'apply_patch','arguments':'{"input":"patch"}'}}]}}]}
        wrapped=ResponsesResponse(response,{'model':'free','stream':True,'tools':[{'type':'custom','name':'apply_patch'}]})
        events=[json.loads(block.decode().split('data: ',1)[1]) for block in wrapped.iter_content()]
        self.assertEqual(events[-1]['type'],'response.completed')
        self.assertEqual(events[-1]['response']['output'][0]['input'],'patch')
        self.assertEqual(events[-1]['response']['output'][0]['call_id'],'a')

    def test_upstream_error_is_not_a_success_event(self):
        response=Mock(status_code=429)
        response.json.return_value={'error':{'message':'limited'}}
        wrapped=ResponsesResponse(response,{'model':'free','stream':True})
        self.assertEqual(wrapped.status_code,429)
        self.assertIn('error',json.loads(next(wrapped.iter_content())))
