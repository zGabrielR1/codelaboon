"""Engine-specific headless task protocols and offline availability."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ENGINES = ('jcode','opencode','omp','kilo','claude','codex','crush','devin')


def catalog():
    from codelaboon.external_engines import managed_executable
    from codelaboon.runtime_management import inspect
    rows=[]
    for engine in ENGINES:
        if engine=='devin':
            from codelaboon.account_engines import executable
            try:executable();installed=True
            except ValueError:installed=False
        elif engine in ('opencode','omp'):
            state=inspect(engine)
            installed=state['state'] not in ('not_installed','unavailable')
        else:
            installed=bool(shutil.which(engine)) if engine!='jcode' else bool(os.environ.get('CODELABOON_JCODE_BIN') and Path(os.environ['CODELABOON_JCODE_BIN']).is_file())
            installed=installed or managed_executable(engine) is not None
        rows.append({'id':engine,'installed':installed,'native_swarm':engine=='jcode',
            'worker_limit':1000 if engine=='jcode' else 1,
            'coordination':'native swarm' if engine=='jcode' else 'portable coordinator',
            'native_account':engine=='devin',
            'prepare_command':'codelaboon accounts devin setup' if engine=='devin' else f'codelaboon tui --engine {engine} --setup'})
    return rows


def command(engine, model, prompt_file):
    if engine not in ENGINES:raise ValueError('Unsupported task engine')
    if engine=='devin':
        from codelaboon.account_engines import task_command
        return task_command(model,prompt_file)
    native_model=model if model.startswith('codelaboon/') else 'codelaboon/'+model
    wire_model=model.removeprefix('codelaboon/')
    if engine in ('opencode','kilo'):
        # --file is a variadic yargs option: trailing prose becomes another
        # filename. Put the positional message before it, with files last.
        return ['run','Execute the attached task specification.','--format','json','--model',native_model,'--file',str(prompt_file)]
    prompt=prompt_file.read_text(encoding='utf-8')
    if engine=='omp':return ['--print','--mode','json','--model',native_model,prompt]
    if engine=='claude':return ['-p',prompt,'--output-format','json','--model',wire_model]
    if engine=='codex':return ['exec','--skip-git-repo-check','--json','--model',wire_model,prompt]
    if engine=='crush':return ['run','--quiet',prompt]
    return ['--model',wire_model,'run','--json',prompt]


def run(engine, model, prompt_file, runtime):
    """Require a complete native response; acceptance checks remain independent."""
    if engine=='devin':
        from codelaboon.account_engines import run_task
        return run_task(model,prompt_file,runtime)
    arguments=command(engine,model,prompt_file)
    env=dict(os.environ,CODELABOON_NATIVE_DIR=str(runtime/engine),CODELABOON_TASK_MODEL=model.removeprefix('codelaboon/'),CODELABOON_HEADLESS_TASK='1')
    source=Path(__file__).with_name('cli.py')
    process=subprocess.Popen([sys.executable,str(source),'tui','--engine',engine,'--',*arguments],
        stdout=subprocess.PIPE,stderr=sys.stderr,text=True,encoding='utf-8',errors='replace',env=env,start_new_session=os.name!='nt')
    try:
        if engine in ('claude','crush','jcode'):
            output,_=process.communicate()
            if process.returncode:raise RuntimeError(f'{engine} task failed (exit={process.returncode})')
            if engine=='crush':text=output
            else:
                result=json.loads(output)
                if not isinstance(result,dict):raise RuntimeError('Invalid native result')
                if engine=='claude' and (result.get('is_error') or result.get('subtype')!='success'):
                    raise RuntimeError('Claude task did not report success')
                text=result.get('result' if engine=='claude' else 'text','')
            if not isinstance(text,str) or not text.strip():raise RuntimeError(f'{engine} returned no final response')
            return text
        texts=[];complete=False;failure=False
        for line in process.stdout:
            try:event=json.loads(line)
            except ValueError:
                print(line,end='',file=sys.stderr);continue
            if not isinstance(event,dict):failure=True;continue
            kind=event.get('type')
            if kind in ('error','turn.failed'):failure=True
            if engine in ('opencode','kilo'):
                if kind=='text':texts.append(event.get('part',{}).get('text',''))
                if kind=='step_finish' and event.get('part',{}).get('reason')=='stop':complete=True
            elif engine=='codex':
                item=event.get('item',{})
                if kind=='item.completed' and item.get('type')=='agent_message':texts.append(item.get('text',''))
                if kind=='turn.completed':complete=True
            elif engine=='omp' and kind=='message_end':
                message=event.get('message',{})
                if message.get('role')=='assistant':
                    texts.extend(part.get('text','') for part in message.get('content',[]) if part.get('type')=='text')
                    if message.get('stopReason')=='stop':complete=True
                    if message.get('stopReason') in ('error','aborted'):failure=True
            if texts:
                from codelaboon.task_conversation import save_reply
                save_reply('\n'.join(text for text in texts if isinstance(text,str)),partial=True)
            if kind not in ('text','item.completed','message_end'):
                print(json.dumps(event),file=sys.stderr,flush=True)
        code=process.wait()
        if code or failure or not complete or not any(isinstance(text,str) and text.strip() for text in texts):
            raise RuntimeError(f'{engine} task incomplete or failed (exit={code}, final={complete})')
        return '\n'.join(text for text in texts if isinstance(text,str))
    except BaseException:
        from codelaboon.watch import terminate
        if process.poll() is None:terminate(process)
        raise
