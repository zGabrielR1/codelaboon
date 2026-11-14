"""Anthropic Messages wire adapter for Codelaboon's OpenAI-compatible providers."""
import json
import secrets


def content(blocks):
    if isinstance(blocks, str):
        return blocks
    result = []
    for block in blocks or []:
        kind = block.get('type')
        if kind == 'text':
            result.append({'type': 'text', 'text': block.get('text', '')})
        elif kind == 'image':
            source = block['source']
            url = source.get('url') if source['type'] == 'url' else (
                'data:' + source['media_type'] + ';base64,' + source['data'])
            result.append({'type': 'image_url', 'image_url': {'url': url}})
        elif kind not in ('thinking', 'redacted_thinking'):
            raise ValueError('Unsupported Messages content block: ' + str(kind))
    return result


def to_chat(body):
    messages = []
    if body.get('system'):
        messages.append({'role': 'system', 'content': content(body['system'])})
    for message in body.get('messages', []):
        blocks = message.get('content', '')
        if isinstance(blocks, str):
            messages.append({'role': message['role'], 'content': blocks})
            continue
        normal, calls, results = [], [], []
        for block in blocks:
            if block['type'] == 'tool_use':
                calls.append({'id': block['id'], 'type': 'function', 'function': {
                    'name': block['name'], 'arguments': json.dumps(block.get('input', {}))}})
            elif block['type'] == 'tool_result':
                value = content(block.get('content', ''))
                if block.get('is_error'):
                    prefix = '[Tool error] '
                    value = prefix + value if isinstance(value, str) else [{'type': 'text', 'text': prefix}, *value]
                results.append({'role': 'tool', 'tool_call_id': block['tool_use_id'], 'content': value})
            else:
                normal.append(block)
        # Tool results must follow their assistant tool calls before new user text.
        messages.extend(results)
        if normal or calls:
            row = {'role': message['role'], 'content': content(normal) or None}
            if calls:
                row['tool_calls'] = calls
            messages.append(row)
    result = {'model': body['model'], 'messages': messages,
              'stream': bool(body.get('stream')), 'max_tokens': min(body.get('max_tokens', 4096), 4096)}
    if result['stream']:
        result['stream_options'] = {'include_usage': True}
    for field in ('temperature', 'top_p'):
        if field in body:
            result[field] = body[field]
    if body.get('stop_sequences'):
        result['stop'] = body['stop_sequences']
    if body.get('tools'):
        result['tools'] = []
        for tool in body['tools']:
            if 'input_schema' not in tool:
                raise ValueError('This gateway requires client-executed tools with input_schema')
            result['tools'].append({'type': 'function', 'function': {
                'name': tool['name'], 'description': tool.get('description', ''),
                'parameters': tool['input_schema']}})
        choice = body.get('tool_choice', {})
        if choice.get('type') == 'tool':
            result['tool_choice'] = {'type': 'function', 'function': {'name': choice['name']}}
        elif choice.get('type') in ('auto', 'any', 'none'):
            result['tool_choice'] = {'any': 'required'}.get(choice['type'], choice['type'])
        if choice.get('disable_parallel_tool_use'):
            result['parallel_tool_calls'] = False
    return result


def reason(value):
    return {'tool_calls': 'tool_use', 'function_call': 'tool_use', 'length': 'max_tokens',
            'stop': 'end_turn', 'content_filter': 'refusal'}.get(value, 'end_turn')


def usage(value):
    return {'input_tokens': value.get('prompt_tokens', 0), 'output_tokens': value.get('completion_tokens', 0)}


def event(kind, **value):
    return ('event: ' + kind + '\ndata: ' + json.dumps({'type': kind, **value}) + '\n\n').encode()


class MessagesResponse:
    """Response facade consumed by the existing loopback HTTP transport."""
    codelaboon_google_oauth = False

    def __init__(self, response, model, streaming):
        self.response, self.model, self.streaming = response, model, streaming
        self.status_code = response.status_code
        self.headers = {'Content-Type': 'text/event-stream' if streaming and response.status_code < 400
                        else 'application/json'}

    def close(self):
        self.response.close()

    def document(self):
        data = self.response.json()
        if self.status_code >= 400:
            error = data.get('error', {})
            return {'type': 'error', 'error': {'type': 'rate_limit_error' if self.status_code == 429 else 'api_error',
                    'message': error.get('message', str(error)) if isinstance(error, dict) else str(error)}}
        choice = data['choices'][0]
        message = choice['message']
        blocks = [{'type': 'text', 'text': message['content']}] if message.get('content') else []
        for call in message.get('tool_calls', []):
            blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'],
                           'input': json.loads(call['function']['arguments'])})
        return {'id': data.get('id', 'msg_' + secrets.token_hex(12)), 'type': 'message', 'role': 'assistant',
                'model': self.model, 'content': blocks, 'stop_reason': reason(choice.get('finish_reason')),
                'stop_sequence': None, 'usage': usage(data.get('usage', {}))}

    def iter_content(self, chunk_size=None):
        if not self.streaming or self.status_code >= 400:
            yield json.dumps(self.document()).encode()
            return
        identifier = 'msg_' + secrets.token_hex(12)
        yield event('message_start', message={'id': identifier, 'type': 'message', 'role': 'assistant',
                    'model': self.model, 'content': [], 'stop_reason': None, 'stop_sequence': None,
                    'usage': {'input_tokens': 0, 'output_tokens': 0}})
        tools, tokens, finish, done = {}, {}, None, False
        text_open = False
        self.response.encoding = 'utf-8'
        try:
            for line in self.response.iter_lines(decode_unicode=True):
                if not line.startswith('data:'):
                    continue
                raw = line[5:].strip()
                if raw == '[DONE]':
                    done = True
                    break
                data = json.loads(raw)
                if data.get('error'):
                    raise ValueError('Upstream stream error: ' + str(data['error']))
                tokens = data.get('usage') or tokens
                for choice in data.get('choices', []):
                    if choice.get('index', 0) != 0:
                        continue
                    delta = choice.get('delta', {})
                    if delta.get('content'):
                        if not text_open:
                            yield event('content_block_start', index=0, content_block={'type': 'text', 'text': ''})
                            text_open = True
                        yield event('content_block_delta', index=0,
                                    delta={'type': 'text_delta', 'text': delta['content']})
                    for call in delta.get('tool_calls', []):
                        tool = tools.setdefault(call.get('index', 0), {'id': '', 'name': '', 'arguments': ''})
                        tool['id'] += call.get('id') or ''
                        tool['name'] += call.get('function', {}).get('name') or ''
                        tool['arguments'] += call.get('function', {}).get('arguments') or ''
                        if len(tool['arguments']) > 8 * 1024 * 1024:
                            raise ValueError('Upstream tool arguments exceed gateway limit')
                    finish = choice.get('finish_reason') or finish
            if finish not in (None, 'stop', 'length', 'tool_calls', 'function_call', 'content_filter'):
                raise ValueError('Unsupported upstream finish reason: ' + str(finish))
            if not finish and not done:
                raise ValueError('Upstream stream ended without a completion marker')
            if text_open:
                yield event('content_block_stop', index=0)
            index = int(text_open)
            for tool in tools.values():
                arguments = json.loads(tool['arguments'] or '{}')
                if not tool['id'] or not tool['name'] or not isinstance(arguments, dict):
                    raise ValueError('Upstream returned an invalid tool call')
                yield event('content_block_start', index=index, content_block={
                    'type': 'tool_use', 'id': tool['id'], 'name': tool['name'], 'input': {}})
                yield event('content_block_delta', index=index, delta={
                    'type': 'input_json_delta', 'partial_json': json.dumps(arguments)})
                yield event('content_block_stop', index=index)
                index += 1
            yield event('message_delta', delta={'stop_reason': reason(finish), 'stop_sequence': None}, usage=usage(tokens))
            yield event('message_stop')
        except (ValueError, KeyError, TypeError) as error:
            yield event('error', error={'type': 'api_error', 'message': str(error)})
