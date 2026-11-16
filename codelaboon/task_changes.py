"""Read-only bounded Git evidence; never attribute pre-existing edits to an agent."""
import re
import subprocess
import os


def redact(text):
    text=re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|access[_-]?token|password)\s*[=:]\s*)[^\s,;]+',r'\1[redacted]',text)
    return re.sub(r'sk-[A-Za-z0-9_-]+','[redacted]',text)


def git(project,arguments,limit=32000):
    # Spool bounded output, rather than trusting a potentially huge diff in RAM.
    import tempfile
    with tempfile.TemporaryFile() as output:
        process=subprocess.Popen(['git','--no-pager','-c','core.hooksPath=','-c','core.fsmonitor=false','-c','diff.external=',*arguments],
            cwd=project,stdout=output,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        try:code=process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait();return '',False,False
        output.seek(0);raw=output.read(limit+1)
    return redact(raw[:limit].decode('utf-8',errors='replace')),len(raw)>limit,code==0


def snapshot(project):
    head,_,available=git(project,['rev-parse','--verify','HEAD'],100)
    status,truncated,status_ok=git(project,['status','--short','--untracked-files=normal','--','.'],12000)
    stat,_,_=git(project,['diff','--no-ext-diff','--no-textconv','HEAD','--stat','--','.'],12000)
    diff,cut,_=git(project,['diff','--no-ext-diff','--no-textconv','--relative','HEAD','--','.'])
    return {'available':available and status_ok,'head':head.strip(),'status':status,'stat':stat,'diff':diff,'truncated':truncated or cut,
            'notice':'Current working tree, including pre-existing and other editors\' changes. Untracked file contents are not shown.'}


def fingerprints(project):
    from codelaboon.supervision import project_state
    return project_state(project).get('fingerprints',{})
