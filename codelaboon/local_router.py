"""Local routing only: choose an allowed cloud job, never author task content."""
import json
import urllib.parse
import urllib.request


def choose(config, candidates):
    url = config['url']
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Orchestrator must use a literal loopback HTTP endpoint')
    schema = {'type': 'object', 'properties': {
        'job': {'type': 'integer', 'enum': list(range(len(candidates)))}},
        'required': ['job'], 'additionalProperties': False}
    body = {'model': config['model'], 'temperature': 0, 'max_tokens': 64,
            'stream': False,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'route', 'strict': True, 'schema': schema}},
            'messages': [
                {'role': 'system', 'content':
                 'You are a routing controller only. Choose one listed job index. '
                 'Choose a harness whose capabilities fit the stage. Prefer reliable '
                 'workers with fewer failures, then the earliest listed job for fair rotation. '
                 'Do not plan, implement, review code, or invent work. Return JSON only. /no_think'},
                {'role': 'user', 'content': json.dumps(candidates)}],
            'chat_template_kwargs': {'enable_thinking': False}}
    request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    # Ignore system proxies and refuse redirects away from the local server.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=config.get('timeout_seconds', 60)) as response:
        result = json.load(response)
    selection = json.loads(result['choices'][0]['message']['content'])
    if not isinstance(selection, dict):
        raise ValueError('Local router must return a job object')
    index = selection.get('job')
    if type(index) is not int or not 0 <= index < len(candidates):
        raise ValueError('Local router chose an unlisted job')
    return index
