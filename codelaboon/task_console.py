"""One task entry point shared by every native engine and the browser."""
import argparse
import json
import os
import sys
from urllib.parse import urlencode


def browser(identity=None, port=0):
    from codelaboon.web import serve
    path='/tasks'+('?' + urlencode({'task':identity}) if identity else '')
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
            if answer in ('t','tasks'):open_tasks()
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
    args=parser.parse_args(argv)
    try:
        if args.browser:browser(args.task,args.port)
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
