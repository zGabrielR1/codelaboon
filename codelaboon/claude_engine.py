"""Configure the unmodified Claude Code CLI for Codelaboon's loopback gateway."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from codelaboon.paths import config_dir


def prepare_profile(directory):
    directory=Path(directory)
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
        descriptor, temporary = tempfile.mkstemp(prefix='.preferences-',dir=directory)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(state, stream)
            os.replace(temporary,preferences)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return directory


def launch(binary, arguments, profile, local_only, rows, url, token):
    directory=prepare_profile(config_dir()/'claude-code')
    default = os.environ.get('CODELABOON_TASK_CHAT_MODEL') or (rows[0]['id'] if local_only else 'free')
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
    # CLI settings take precedence over project settings. Keep the gateway token
    # out of argv and never persist it in the user's or project's configuration.
    owned = {key: value for key, value in env.items() if key.startswith('ANTHROPIC_') or key.startswith('CLAUDE_CODE_') or key in ('ENABLE_TOOL_SEARCH', 'MAX_THINKING_TOKENS', 'DISABLE_AUTOUPDATER')}
    for key in ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_CUSTOM_HEADERS',
                'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
                'ANTHROPIC_FOUNDRY_API_KEY'):
        owned[key] = ''
    settings['env'] = owned
    descriptor, settings_path = tempfile.mkstemp(prefix='.gateway-', suffix='.json', dir=directory)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(settings, stream)
    from codelaboon.execution_policy import full_access
    command = [binary, '--settings', settings_path, *arguments]
    if full_access():command.append('--dangerously-skip-permissions')
    if profile == 'security':
        command.extend(['--append-system-prompt', (Path(__file__).parent / 'prompts/security.md').read_text()])
    import sys
    print('Claude Code · Codelaboon ' + default + ' · no Claude subscription required', file=sys.stderr, flush=True)
    try:
        process=subprocess.Popen(command,env=env,start_new_session=os.name!='nt')
        try:
            return process.wait()
        except BaseException:
            from codelaboon.watch import terminate
            terminate(process)
            raise
    finally:
        Path(settings_path).unlink(missing_ok=True)
