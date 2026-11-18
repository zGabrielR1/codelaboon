"""One task entry point shared by every native engine and the browser."""
import argparse
import json
import os
import sys
from urllib.parse import urlencode


def browser(identity=None, port=0):
    from codelaboon.web import serve
    path=('/?' + urlencode({'task':identity})) if identity else '/tasks'
    serve(port, start_path=path)


def open_tasks(identity=None):
    try:
        from codelaboon.task_tui import TaskApp
    except ImportError as error:
        name=error.name or ''
        if name not in ('textual','rich') and not name.startswith(('textual.','rich.')):raise
        print('Opening task conversations in the browser. For terminal task chats install codelaboon[tui].')
        browser(identity)
        return
    TaskApp(identity).run()


def launcher(engine, arguments):
    """Return False when the user exits; never intercept automation/native flags."""
    if arguments or os.environ.get('CODELABOON_HEADLESS_TASK')=='1' or os.environ.get('CODELABOON_DIRECT')=='1':return True
    if not sys.stdin.isatty() or not sys.stdout.isatty():return True
    from codelaboon.task_api import snapshot
    while True:
        try:
            state=snapshot()
            tasks=state['tasks']
            print('\ncodelaboon / '+engine+'\n')
            print('  Enter  Open '+engine+' chat')
            print('  t      Task conversations ('+str(len(tasks))+') - live output and guidance')
            print('  w      Task conversations in browser')
            print('  q      Exit\n')
            for task in tasks[:5]:print('  '+task['title'][:65]+' / '+task['state'])
            print('\nDirect next time: codelaboon '+engine+' --direct')
            answer=input('Open [Enter/t/w/q]: ').strip().lower()
            if not answer:return True
            if answer in ('q','quit'):return False
            if answer in ('t','tasks'):
                select_native(engine)
                return False
            elif answer in ('w','web'):browser()
        except (EOFError,KeyboardInterrupt):return False
        except (OSError,ValueError) as error:print('Task view unavailable: '+str(error));return True


def main(argv=None):
    parser=argparse.ArgumentParser(description='Open continuous tasks as live conversations; no inference is started by viewing them.')
    parser.add_argument('task',nargs='?',help='Task ID to open directly')
    parser.add_argument('--open','--browser',dest='browser',action='store_true',help='Open browser task conversations')
    parser.add_argument('--port',type=int,default=0,help='Browser port (default: an available loopback port)')
    parser.add_argument('--list',action='store_true',help='List tasks without opening an interface')
    parser.add_argument('--json',action='store_true',help='List task state as JSON')
    parser.add_argument('--settings',action='store_true',help='Show task model/prompt settings')
    parser.add_argument('--worker-model',help='Default worker/swarm model: free or PROVIDER/MODEL')
    parser.add_argument('--orchestrator',choices=['worker','cloud','local'],help='Embedded worker coordinator or separate planning model')
    parser.add_argument('--orchestrator-model',help='Planning model: free, PROVIDER/MODEL or local/MODEL')
    parser.add_argument('--system-prompt-file',help='UTF-8 additive worker system instructions (empty file clears)')
    parser.add_argument('--orchestrator-prompt-file',help='UTF-8 additive planning system instructions')
    parser.add_argument('--changes',action='store_true',help='Show current project diff and observed attempt changes')
    parser.add_argument('--attempts',action='store_true',help='Inspect the last 50 attempts')
    parser.add_argument('--delete',action='store_true',help='Delete task scheduling; keep project files and local attempt logs')
    parser.add_argument('--retry',action='store_true',help='Retry a failed continuous task at its next checkpoint')
    args=parser.parse_args(argv)
    try:
        if args.delete:
            if not args.task:parser.error('Provide a task ID')
            from codelaboon.task_api import control
            print(json.dumps(control(args.task,'delete'),indent=2));return
        if args.attempts or args.retry:
            if not args.task:parser.error('Provide a task ID')
            from codelaboon import task_api
            print(json.dumps(task_api.control(args.task,'retry') if args.retry else task_api.attempts(args.task),indent=2));return
        edits=any(value is not None for value in (args.worker_model,args.orchestrator,args.orchestrator_model,args.system_prompt_file,args.orchestrator_prompt_file))
        if args.settings or args.changes or edits:
            if not args.task:parser.error('Provide a task ID for settings/changes')
            from codelaboon import task_api
            if args.changes:print(json.dumps(task_api.changes(args.task),indent=2));return
            row=task_api.settings(args.task)
            if edits:
                from pathlib import Path
                values=dict(row['values'])
                for key,value in (('worker_model',args.worker_model),('orchestrator_mode',args.orchestrator),('orchestrator_model',args.orchestrator_model)):
                    if value is not None:values[key]=value
                for key,path in (('worker_system_prompt',args.system_prompt_file),('orchestrator_system_prompt',args.orchestrator_prompt_file)):
                    if path is not None:values[key]=Path(path).read_text(encoding='utf-8')
                row=task_api.settings(args.task,{'values':values,'expected_revision':row['revision']})
            print(json.dumps(row,indent=2))
        elif args.browser:browser(args.task,args.port)
        elif args.list or args.json or not sys.stdin.isatty():
            from codelaboon.task_api import snapshot
            state=snapshot()
            rows=[task for task in state['tasks'] if not args.task or task['id']==args.task]
            if args.json:print(json.dumps({'worker':state['worker'],'tasks':rows}))
            elif not rows:print('No matching tasks. Queue one with codelaboon swarm --help; open browser tasks with codelaboon tasks --open.')
            else:
                for task in rows:print(task['id']+' / '+task['state']+' / '+task['engine']+'\n  '+task['title']+'\n  Open: codelaboon tasks '+task['id'])
        else:open_tasks(args.task)
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')


def select_native(engine):
    from codelaboon.task_api import snapshot
    from codelaboon.task_chat import open_native
    rows=snapshot()['tasks']
    if not rows:print('No tasks yet. Queue a task in the web workspace.');return
    for index,row in enumerate(rows,1):print(str(index)+'. '+row['title']+' / '+row['state'])
    answer=input('Open task number (Enter to cancel): ').strip()
    if not answer:return
    if not answer.isdecimal() or not 1<=int(answer)<=len(rows):raise ValueError('Choose a listed task number')
    return open_native(engine,rows[int(answer)-1]['id'])
