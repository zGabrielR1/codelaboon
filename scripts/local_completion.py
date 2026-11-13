"""One local Ollama completion; writes text, does not execute model output."""
import json
import sys
import urllib.request
from pathlib import Path

body = json.dumps({'model': sys.argv[1], 'stream': False,
                   'messages': [{'role': 'user', 'content':
                                 Path(sys.argv[2]).read_text(encoding='utf-8')}]}).encode()
request = urllib.request.Request('http://127.0.0.1:11434/v1/chat/completions',
                                 data=body, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=600) as response:
    result = json.load(response)
content = result['choices'][0]['message']['content']
if not content:
    raise RuntimeError('Empty model response')
print(content)
