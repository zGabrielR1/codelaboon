"""Native Codex CLI/app-server with an isolated Codelaboon provider profile."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from codelaboon.paths import config_dir


def launch(binary,arguments,profile,local_only,rows,url,token):
    home=config_dir()/'codex';home.mkdir(parents=True,exist_ok=True,mode=0o700)
    env=dict(os.environ,CODEX_HOME=str(home),CODELABOON_GATEWAY_TOKEN=token)
    for key in ('OPENAI_API_KEY','OPENAI_BASE_URL','CODEX_API_KEY'):env.pop(key,None)
    settings={'model':'free' if not local_only else rows[0]['id'],'model_provider':'codelaboon',
              'model_providers.codelaboon.name':'Codelaboon', 'model_providers.codelaboon.base_url':url,
              'model_providers.codelaboon.env_key':'CODELABOON_GATEWAY_TOKEN',
              'model_providers.codelaboon.wire_api':'responses','model_providers.codelaboon.requires_openai_auth':False,
              'model_providers.codelaboon.supports_websockets':False,
              'model_context_window':32768,'model_auto_compact_token_limit':24576,'analytics.enabled':False}
    if profile=='security': settings['developer_instructions']=(Path(__file__).parent/'prompts/security.md').read_text()
    models=[{'slug':row['id'],'display_name':row['name'],'description':'Codelaboon verified route',
             'base_instructions':'You are a coding agent. Use the available tools to complete the user request. Respect tool permissions and report results accurately.',
             'supported_reasoning_levels':[],'shell_type':'unified_exec','visibility':'list','supported_in_api':True,
             'priority':index,'support_verbosity':False,'default_verbosity':None,'apply_patch_tool_type':'freeform',
             'truncation_policy':{'mode':'tokens','limit':8192},'experimental_supported_tools':[],
             'context_window':32768,'supports_reasoning_summary_parameter':False,'input_modalities':['text'],
             'tool_mode':'direct'} for index,row in enumerate(rows) if row['api']=='chat']
    descriptor,catalog=tempfile.mkstemp(prefix='.models-',suffix='.json',dir=home)
    with os.fdopen(descriptor,'w') as stream:json.dump({'models':models},stream)
    settings['model_catalog_json']=catalog
    # Put enforced provider overrides after SDK arguments; preserve their transport,
    # editor context, permission and MCP flags. Never change the user's Codex home.
    from codelaboon.execution_policy import full_access
    command=[binary,*arguments]
    if full_access():command.append('--dangerously-bypass-approvals-and-sandbox')
    for key,value in settings.items(): command.extend(['-c',key+'='+json.dumps(value)])
    try:
        process=subprocess.Popen(command,env=env,start_new_session=os.name!='nt')
        try:return process.wait()
        except BaseException:
            from codelaboon.watch import terminate
            terminate(process);raise
    finally:Path(catalog).unlink(missing_ok=True)


def wrapper():
    import signal
    def stopped(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stopped)
    if os.name!='nt':signal.signal(signal.SIGHUP,stopped)
    from codelaboon.external_engines import launch as engine
    try:code=engine('codex',sys.argv[1:])
    except KeyboardInterrupt:code=130
    raise SystemExit(code)


if __name__=='__main__': wrapper()
