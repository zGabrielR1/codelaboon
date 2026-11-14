"""Configure the unmodified Claude Code CLI for Codelaboon's loopback gateway."""
import json
import os
from pathlib import Path
import subprocess

from codelaboon.paths import config_dir


def launch(binary, arguments, profile, local_only, rows, url, token):
    directory = config_dir() / 'claude-code'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # These are local UI preferences, not Anthropic account/entitlement records.
    preferences = directory / '.claude.json'
    try:
        state = json.loads(preferences.read_text())
    except FileNotFoundError:
        state = {}
    if not state.get('hasCompletedOnboarding'):
        state.update(hasCompletedOnboarding=True)
        state.setdefault('theme', 'dark')
        descriptor = os.open(preferences, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(state, stream)
    default = rows[0]['id'] if local_only else 'free'
    env = dict(os.environ)
    for key in ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_CUSTOM_HEADERS',
                'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
                'ANTHROPIC_FOUNDRY_API_KEY'):
        env.pop(key, None)
    env.update(CLAUDE_CONFIG_DIR=str(directory), ANTHROPIC_BASE_URL=url.removesuffix('/v1'),
               ANTHROPIC_AUTH_TOKEN=token, ANTHROPIC_MODEL=default,
               ANTHROPIC_DEFAULT_OPUS_MODEL=default, ANTHROPIC_DEFAULT_SONNET_MODEL=default,
               ANTHROPIC_DEFAULT_HAIKU_MODEL=default, CLAUDE_CODE_SUBAGENT_MODEL=default,
               CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', DISABLE_AUTOUPDATER='1',
               CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL='1',
               CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY='1', CLAUDE_CODE_DISABLE_1M_CONTEXT='1',
               ENABLE_TOOL_SEARCH='false', MAX_THINKING_TOKENS='0',
               CLAUDE_CODE_MAX_CONTEXT_TOKENS='32768')
    settings = {'enforceAvailableModels': True, 'availableModels': [row['id'] for row in rows],
                'modelPicker': {'replaceBuiltInOptions': True, 'options': [
                    {'model': row['id'], 'label': row['name'], 'description': row['id']} for row in rows]}}
    command = [binary, '--settings', json.dumps(settings), *arguments]
    if profile == 'security':
        command.extend(['--append-system-prompt', (Path(__file__).parent / 'prompts/security.md').read_text()])
    import sys
    print('Claude Code · Codelaboon ' + default + ' · no Claude subscription required', file=sys.stderr, flush=True)
    return subprocess.call(command, env=env)
