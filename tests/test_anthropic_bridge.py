"""Wire compatibility and account isolation for Claude Code's free backend."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from codelaboon.anthropic_bridge import MessagesResponse, to_chat
from codelaboon.native_gateway import serve


class BridgeTests(unittest.TestCase):
    def response(self, chunks):
        response = MagicMock(status_code=200)
        response.iter_lines.return_value = iter('data: ' + json.dumps(chunk) for chunk in chunks)
        return response

    def test_preserves_tool_ids_schemas_results_and_user_text(self):
        body = {'model': 'free', 'system': [{'type': 'text', 'text': 'system', 'cache_control': {'type': 'ephemeral'}}],
                'messages': [
                    {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'read1', 'name': 'Read', 'input': {'file_path': 'a'}}]},
                    {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'read1', 'content': 'denied', 'is_error': True},
                                               {'type': 'text', 'text': 'Try another file'}]}],
                'tools': [{'name': 'Read', 'input_schema': {'type': 'object'}}],
                'tool_choice': {'type': 'tool', 'name': 'Read'}, 'max_tokens': 32000}
        result = to_chat(body)
        self.assertEqual(result['messages'][1]['tool_calls'][0]['id'], 'read1')
        self.assertEqual(result['messages'][2], {'role': 'tool', 'tool_call_id': 'read1', 'content': '[Tool error] denied'})
        self.assertEqual(result['messages'][3]['content'][0]['text'], 'Try another file')
        self.assertEqual(result['tool_choice']['function']['name'], 'Read')
        self.assertEqual(result['max_tokens'], 4096)
        self.assertNotIn('cache_control', json.dumps(result))

    def test_parallel_fragmented_tool_calls_and_usage_become_valid_messages_events(self):
        chunks = [
            {'choices': [{'delta': {'content': 'Reading'}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'r1', 'function': {'name': 'Read', 'arguments': '{"file_'}},
                                                 {'index': 1, 'id': 'r2', 'function': {'name': 'Read', 'arguments': '{"file_path":"b"}'}}]}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {'arguments': 'path":"a"}'}}]}, 'finish_reason': 'tool_calls'}]},
            {'choices': [], 'usage': {'prompt_tokens': 123, 'completion_tokens': 45}}]
        output = b''.join(MessagesResponse(self.response(chunks), 'free', True).iter_content()).decode()
        events = [json.loads(line[6:]) for line in output.splitlines() if line.startswith('data: ')]
        starts = [item['content_block'] for item in events if item['type'] == 'content_block_start']
        self.assertEqual([item.get('id') for item in starts], [None, 'r1', 'r2'])
        arguments = [json.loads(item['delta']['partial_json']) for item in events if item['type'] == 'content_block_delta' and item['delta']['type'] == 'input_json_delta']
        self.assertEqual(arguments, [{'file_path': 'a'}, {'file_path': 'b'}])
        finish = next(item for item in events if item['type'] == 'message_delta')
        self.assertEqual(finish['delta']['stop_reason'], 'tool_use')
        self.assertEqual(finish['usage'], {'input_tokens': 123, 'output_tokens': 45})
        self.assertEqual(events[-1]['type'], 'message_stop')

    def test_truncated_stream_reports_error_instead_of_success(self):
        response = self.response([{'choices': [{'delta': {'content': 'partial'}}]}])
        output = b''.join(MessagesResponse(response, 'free', True).iter_content()).decode()
        self.assertIn('event: error', output)
        self.assertNotIn('event: message_stop', output)

    def test_invalid_tool_arguments_do_not_execute(self):
        response = self.response([{'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'bad', 'function': {'name': 'Read', 'arguments': 'not JSON'}}]}, 'finish_reason': 'tool_calls'}]}])
        output = b''.join(MessagesResponse(response, 'free', True).iter_content()).decode()
        self.assertIn('event: error', output)
        self.assertNotIn('"type": "tool_use"', output)

    def test_unsupported_content_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported Messages content'):
            to_chat({'model': 'free', 'messages': [{'role': 'user', 'content': [{'type': 'document'}]}]})

    def test_json_response_and_provider_error_have_anthropic_shapes(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {'id': 'answer', 'choices': [{'message': {'content': 'hello'}, 'finish_reason': 'length'}],
                                      'usage': {'prompt_tokens': 10, 'completion_tokens': 20}}
        result = json.loads(b''.join(MessagesResponse(response, 'free', False).iter_content()))
        self.assertEqual(result['stop_reason'], 'max_tokens')
        self.assertEqual(result['usage']['output_tokens'], 20)
        response.status_code = 429
        response.json.return_value = {'error': {'message': 'Quota exhausted'}}
        result = json.loads(b''.join(MessagesResponse(response, 'free', True).iter_content()))
        self.assertEqual(result['error']['type'], 'rate_limit_error')

    def test_http_messages_routes_free_model_without_anthropic_credentials(self):
        provider = MagicMock(api_key='', base_url='https://free.example/v1', models=['free-model'])
        provider.validate_api_key.return_value = True
        provider.credential.return_value = ''
        response = MagicMock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'free reply'}, 'finish_reason': 'stop'}]}
        with serve({'local': provider}) as (gateway, url), patch.object(gateway.local, 'post', return_value=response) as upstream:
            client = requests.Session()
            client.trust_env = False
            answer = client.post(url + '/messages', headers={'x-api-key': gateway.token},
                                 json={'model': 'local/free-model[1m]', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 40})
            self.assertEqual(answer.status_code, 200)
            self.assertEqual(answer.json()['content'][0]['text'], 'free reply')
            self.assertEqual(upstream.call_args.kwargs['json']['model'], 'free-model')
            self.assertNotIn('authorization', upstream.call_args.kwargs['headers'])
            denied = client.post(url + '/messages/count_tokens', json={'messages': []})
            self.assertEqual(denied.status_code, 401)
            counted = client.post(url + '/messages/count_tokens', headers={'x-api-key': gateway.token}, json={'messages': []})
            self.assertGreater(counted.json()['input_tokens'], 0)

    def test_launcher_uses_private_gateway_token_and_isolated_profile(self):
        from codelaboon.claude_engine import launch
        rows = [{'id': 'free', 'name': 'free (Auto)', 'api': 'chat'}]
        with tempfile.TemporaryDirectory() as directory, patch('codelaboon.claude_engine.config_dir', return_value=Path(directory)), patch.dict(
                os.environ, {'ANTHROPIC_API_KEY': 'personal-key', 'CLAUDE_CODE_OAUTH_TOKEN': 'personal-token'}), patch(
                'codelaboon.claude_engine.subprocess.Popen') as run:
            captured = {}
            def capture(command, **kwargs):
                captured.update(json.loads(Path(command[command.index('--settings') + 1]).read_text()))
                return run.return_value
            run.side_effect = capture
            run.return_value.wait.return_value=0
            launch('/native/claude', [], 'coding', False, rows, 'http://127.0.0.1:123/v1', 'session-token')
            env = run.call_args.kwargs['env']
            self.assertEqual(env['ANTHROPIC_BASE_URL'], 'http://127.0.0.1:123')
            self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'], 'session-token')
            self.assertNotIn('ANTHROPIC_API_KEY', env)
            self.assertNotIn('CLAUDE_CODE_OAUTH_TOKEN', env)
            preferences = Path(directory) / 'claude-code/.claude.json'
            self.assertTrue(json.loads(preferences.read_text())['hasCompletedOnboarding'])
            self.assertNotIn('session-token', preferences.read_text())
            command = run.call_args.args[0]
            settings = captured
            self.assertFalse(Path(command[command.index('--settings') + 1]).exists())
            self.assertNotIn('session-token', str(command))
            self.assertEqual(settings['env']['ANTHROPIC_API_KEY'], '')
            self.assertTrue(settings['modelPicker']['replaceBuiltInOptions'])
            self.assertEqual(settings['availableModels'], ['free'])
            self.assertNotIn('--dangerously-skip-permissions', command)
