"""Owned, authenticated local-model sessions for evaluation/privileged cases."""
from contextlib import contextmanager
import os
import hashlib
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import requests
from codelaboon.paths import config_dir


def paths(config=None):
    config=config or {};root=config_dir()/'runtime/local'
    name='llama-server.exe' if os.name=='nt' else 'llama-server'
    linux=root/'llama-linux/llama-b12360/llama-server'
    executable=config.get('local_executable') or shutil.which(name) or (linux if os.name!='nt' and linux.is_file() else root/'llama'/name)
    return Path(executable),Path(config.get('local_model') or root/'router.gguf')


@contextmanager
def session(config=None):
    config=config or {};executable,model=paths(config)
    if not executable.is_file() or not model.is_file():raise ValueError('Install/configure the optional local router runtime and model first')
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='codelaboon-controller-') as directory:
        root=Path(directory);token=secrets.token_urlsafe(32);key=root/'key';key.write_text(token);key.chmod(0o600)
        alias=config.get('orchestrator',{}).get('model','local-router')
        with (root/'server.log').open('wb') as log:
            command=[str(executable),'-m',str(model),'--host','127.0.0.1','--port',str(port),'--alias',alias,'--api-key-file',str(key),'-c',str(config.get('local_context',4096)),'-t','2','--reasoning','off']
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
            client=requests.Session();client.trust_env=False;started=time.monotonic()
            try:
                deadline=started+60
                while time.monotonic()<deadline:
                    if process.poll() is not None:raise ValueError('Local model exited before readiness')
                    try:
                        response=client.get(f'http://127.0.0.1:{port}/v1/models',headers={'Authorization':'Bearer '+token},timeout=1)
                        if response.ok:break
                    except requests.RequestException:pass
                    time.sleep(.2)
                else:raise ValueError('Local model startup timed out')
                with model.open('rb') as model_file:model_sha256=hashlib.file_digest(model_file,'sha256').hexdigest()
                yield {'model_sha256':model_sha256,'url':f'http://127.0.0.1:{port}/v1/chat/completions','model':alias,'token':token,'timeout_seconds':15,'cold_start_seconds':round(time.monotonic()-started,3)}
            finally:
                client.close()
                from codelaboon.watch import terminate
                terminate(process)
