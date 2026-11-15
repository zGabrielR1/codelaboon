"""Exercise the actual official editor extension in an isolated VS Code test host."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import socket
from native_fixture import ROOT,REPLY,fixture
sys.path.insert(0,str(ROOT))


def respond(body,project):
    if 'IDE_BACKEND_PROBE' in json.dumps(body.get('messages',[])):
        (project/'backend-observed').write_text('observed')
    return {'role':'assistant','content':REPLY},'stop'

with fixture('codex',responder=respond) as (project,env,observed):
    extension=project/'extension'
    shutil.copytree(ROOT/'codelaboon/integrations/vscode',extension)
    wrapper=project/'wrapper'
    wrapper.write_text('#!'+sys.executable+'\nimport sys\nsys.path.insert(0,'+repr(str(ROOT))+')\nfrom codelaboon.codex_engine import wrapper\nwrapper()\n')
    wrapper.chmod(0o700)
    profile=project/'config/claude-code'
    from codelaboon.claude_engine import prepare_profile
    prepare_profile(profile)
    (extension/'backend.json').write_text(json.dumps({'codexWrapper':str(wrapper),'connectCodexOnInstall':True}))
    user=project/'vscode-user'
    (user/'User').mkdir(parents=True)
    (user/'User/settings.json').write_text(json.dumps({'chatgpt.cliExecutable':str(wrapper),'claudeCode.disableLoginPrompt':True,
        'claudeCode.claudeProcessWrapper':str(wrapper),'claudeCode.environmentVariables':[{'name':'CLAUDE_CONFIG_DIR','value':str(profile)}],
        'telemetry.telemetryLevel':'off','workbench.startupEditor':'none','security.workspace.trust.enabled':False}))
    env['CODELABOON_VSCODE_PROBE_DEBUG']='1'
    env['CODELABOON_VSCODE_TEST_PROJECT']=str(project)
    official=next((Path.home()/'.vscode/extensions').glob('openai.chatgpt-*/package.json')).parent
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    dependency=next((Path.home()/'.vscode/extensions').glob('anthropic.claude-code-*/package.json')).parent
    command=['code','--extensionDevelopmentPath='+str(dependency),'--extensionDevelopmentPath='+str(extension),'--extensionDevelopmentPath='+str(official),'--extensionTestsPath='+str(ROOT/'scripts/vscode_codex_host_test.js'),
        '--user-data-dir='+str(user),'--extensions-dir='+str(project/'isolated-extensions'),
        '--remote-debugging-port='+str(port),'--wait','--disable-gpu','--skip-welcome','--skip-release-notes','--disable-workspace-trust',str(project)]
    output_path=ROOT/'.runtime/vscode-codex-smoke.log'
    with output_path.open('w') as output:
        process=subprocess.Popen(command,env=env,stdout=output,stderr=output)
        sent=False;deadline=time.monotonic()+90
        while process.poll() is None and time.monotonic()<deadline:
            if (project/'ui-ready').exists():
                mode='reply' if sent else 'codex-send'
                probe=subprocess.run(['node',str(ROOT/'scripts/vscode_ui_probe.js'),str(port),mode],env=env,
                                     capture_output=True,text=True,timeout=8)
                with (ROOT/'.runtime/vscode-probe.log').open('w') as probe_log:
                    probe_log.write(mode+' '+str(probe.returncode)+' '+probe.stdout+' '+probe.stderr+'\n')
                if probe.returncode==0:
                    if mode=='codex-send':sent=True
                    else:(project/'reply-visible').write_text('visible')
            time.sleep(0.3)
        if process.poll() is None:
            process.terminate();process.wait(timeout=10)
            raise AssertionError('VS Code test host timed out')
    result=process
    artifacts=ROOT/'.runtime/ui-qa'
    artifacts.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'.runtime/vscode-codex-smoke.log',artifacts/'vscode-codex-smoke.log')
    with (ROOT/'.runtime/vscode-host-logs.log').open('w') as host_logs:
        for p in (user/'logs').glob('**/*.log'):
            if 'openai' in str(p) or p.name in ('exthost.log','renderer.log'):
                host_logs.write(str(p)+'\n'+p.read_text(errors='replace')[-16000:]+'\n')
    assert result.returncode==0,output_path.read_text()[-2500:]
    assert (project/'host-test-passed').exists(),'VS Code host did not finish validation'
    assert any('IDE_BACKEND_PROBE' in json.dumps(body.get('messages',[])) for body in observed)
    print('PASS: real VS Code official Codex extension sent its editor prompt through Codelaboon')
