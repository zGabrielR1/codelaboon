"""A separate, bounded planning step; local mode never falls back to cloud."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def plan(values,prompt,providers=None):
    mode=values['orchestrator_mode'];model=values['orchestrator_model']
    if mode=='worker':raise ValueError('Embedded worker orchestration has no separate planning step')
    if providers is None:
        from codelaboon.cli import CodelaboonCLI
        cli=CodelaboonCLI()
        with contextlib.redirect_stdout(sys.stderr):cli.load_providers()
        providers=cli.providers
    system=('You are the task planning orchestrator. Produce the next concrete bounded work plan, worker assignments, '
            'acceptance evidence and blockers. Do not execute tools, claim completed work or expand the immutable task scope. '
            'Workers implement your plan and the supervisor runs independent checks.\n'+values.get('orchestrator_system_prompt',''))
    bounded=prompt if len(prompt)<=48000 else prompt[:32000]+'\n[Middle context omitted]\n'+prompt[-16000:]
    messages=[{'role':'system','content':system},{'role':'user','content':bounded}]
    if mode=='local':
        if not model.startswith('local/'):raise ValueError('Local orchestration requires a local model')
        text=providers['local'].chat(model.removeprefix('local/'),messages,max_tokens=4096)
    elif model=='free':
        from codelaboon.free_auto import chat
        text=chat({name:value for name,value in providers.items() if name!='local'},messages,max_tokens=4096)[1]
    else:
        provider,separator,identifier=model.partition('/')
        if not separator or provider=='local':raise ValueError('Cloud orchestration requires PROVIDER/MODEL')
        text=providers[provider].chat(identifier,messages,max_tokens=4096)
    if not isinstance(text,str) or not text.strip():raise ValueError('Orchestrator returned no plan')
    return text[:24000]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('settings',type=Path);parser.add_argument('prompt',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    values=json.loads(args.settings.read_text(encoding='utf-8'))
    try:result=plan(values,args.prompt.read_text(encoding='utf-8'))
    except Exception as error:print('Orchestrator planning failed: '+str(error),file=sys.stderr);raise SystemExit(1)
    args.output.write_text(result,encoding='utf-8');print(result,flush=True)


if __name__=='__main__':main()
