"""Delete task scheduling records without deleting project files or active work."""
import json
import os
from pathlib import Path
import tempfile
import time
from codelaboon.work_queue import controls


def deleted(root,identity):
    return (controls(root,identity)/'DELETED.json').is_file()


def delete(root,task):
    directory=controls(root,task['id']);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    # STOP also protects older workers that do not understand deletion receipts.
    (directory/'STOP').touch()
    path=directory/'DELETED.json'
    if not path.exists():
        fd,temporary=tempfile.mkstemp(prefix='.delete-',dir=directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump({'task':task['id'],'deleted':time.time()},stream)
            os.replace(temporary,path)
        finally:Path(temporary).unlink(missing_ok=True)
    return {'task':task['id'],'deleted':True,'message':'Task deleted. Active work and checks finish safely. Project files and local attempt logs are kept.'}
