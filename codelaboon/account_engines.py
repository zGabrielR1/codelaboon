"""Official Windsurf/Devin CLI accounts, models and bounded task execution."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from codelaboon.execution_policy import full_access

INSTALL='https://docs.devin.ai/cli/'


def executable(install=False):
    path=os.environ.get('CODELABOON_DEVIN_BIN') or shutil.which('devin')
    if not path or not Path(path).is_file():
        from codelaboon.external_engines import managed_executable
        path=managed_executable('devin')
    if not path or not Path(path).is_file():
        if install:
            from codelaboon.external_engines import setup
            return str(setup('devin'))
        raise ValueError('Run codelaboon accounts devin setup to install the official checksum-verified native CLI; '+INSTALL)
    return str(Path(path).resolve())


def login(engine='devin'):
    subprocess.run([executable(install=True),'auth','login'],check=True)


def task_command(model,prompt):
    if not model.startswith('devin/'):raise ValueError('Devin uses native account models: devin/account-default or devin/MODEL; no free Auto substitution')
    model=model.split('/',1)[1]
    if not model:raise ValueError('Select a native Devin model')
    argv=[executable(install=True),'--print','--prompt-file',str(prompt)]
    if model!='account-default':argv.extend(['--model',model])
    if full_access():argv.extend(['--permission-mode','dangerous'])
    return argv


def run_task(model,prompt,runtime):
    output=runtime/'devin-output.log';runtime.mkdir(parents=True,exist_ok=True)
    from codelaboon.watch import execute
    offset=0
    def progress():
        nonlocal offset
        if not output.exists():return
        with output.open('rb') as stream:stream.seek(offset);chunk=stream.read(8192);offset+=len(chunk)
        if chunk:print(chunk.decode('utf-8',errors='replace'),end='',file=sys.stderr,flush=True)
    code=execute(task_command(model,prompt),Path.cwd(),output,86400,env=dict(os.environ),monitor=progress,review_interval=1)
    if code:raise RuntimeError('Native Devin task failed (exit='+str(code)+'); inspect '+str(output))
    # Bound memory; native output may include progress. Independent task checks
    # remain the acceptance oracle, never the mere presence of this text.
    with output.open('rb') as stream:stream.seek(0,2);stream.seek(max(0,stream.tell()-65536));text=stream.read(65536).decode('utf-8',errors='replace')
    if not text.strip():raise RuntimeError('Devin returned no final output')
    return text


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('account',choices=['windsurf','devin']);parser.add_argument('action',choices=['login','status','models','open','setup'],default='status',nargs='?');args,extra=parser.parse_known_args(arguments)
    if extra and args.action!='open':parser.error('Native flags are accepted only with open')
    try:
        if args.action=='setup':
            from codelaboon.external_engines import setup
            print(setup('devin'));return
        if args.action=='login':login();return
        if args.action=='status':command=['auth','status']
        elif args.action=='models':command=['models','list','--format','json']
        else:command=extra[1:] if extra[:1]==['--'] else extra
        raise SystemExit(subprocess.call([executable(install=args.action=='open'),*command]))
    except (OSError,ValueError,subprocess.CalledProcessError) as error:parser.exit(1,str(error)+'\n')
