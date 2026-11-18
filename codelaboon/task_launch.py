"""Explicit web-to-native task launch, with an argument vector and no shell."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from codelaboon import task_api
from codelaboon.session_transfer import ENGINES


def launch(identity,engine):
    config,_,task=task_api.selected(identity)
    if engine not in ENGINES:raise ValueError('Choose a supported native chat engine')
    from codelaboon.engine_tasks import catalog
    available=next((row for row in catalog() if row['id']==engine),None)
    if not available or not available['installed']:raise ValueError('Install this engine first, or choose an installed engine')
    project=(config.parent/Path(task['project']).expanduser()).resolve()
    if not project.is_dir():raise ValueError('The task project folder is no longer available')
    command=[sys.executable,'-m','codelaboon',engine,'--tasks',identity]
    environment=dict(os.environ)
    source=str(Path(__file__).resolve().parent.parent)
    environment['PYTHONPATH']=source+os.pathsep+environment.get('PYTHONPATH','')
    options={'cwd':str(project),'env':environment}
    if os.name=='nt':
        terminal=shutil.which('wt.exe')
        if terminal:command=[terminal,'-w','new','new-tab','--title','codelaboon task','--startingDirectory',str(project),*command]
        else:options['creationflags']=subprocess.CREATE_NEW_CONSOLE
    elif sys.platform=='darwin':
        raise ValueError('Opening a terminal on macOS is not configured. Run codelaboon '+engine+' --tasks '+identity)
    else:
        terminal=shutil.which('x-terminal-emulator') or shutil.which('gnome-terminal') or shutil.which('konsole')
        if not terminal:raise ValueError('No desktop terminal found. Run codelaboon '+engine+' --tasks '+identity)
        command=[terminal,'--' if Path(terminal).name=='gnome-terminal' else '-e',*command]
    subprocess.Popen(command,**options)
    return {'task':identity,'engine':engine,'message':'Opening this task in '+engine+'. Sign-ins and task history are shared with the web workspace.'}
