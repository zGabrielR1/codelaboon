"""Cloud completion/agent adapters for the local orchestration supervisor."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def completion(provider, model, prompt):
    from codelaboon.cli import CodelaboonCLI
    if provider == 'free':
        from codelaboon import free_auto
        with contextlib.redirect_stdout(sys.stderr):
            cli = CodelaboonCLI()
            cli.load_providers()
        return free_auto.chat(cli.providers, [{'role': 'user', 'content': prompt}], max_tokens=4096)[1]
    if provider == 'kilo':
        # Keyless pool: do not read or create any account configuration.
        from providers.kilo.kilo_provider import KiloProvider
        worker = KiloProvider('')
    else:
        with contextlib.redirect_stdout(sys.stderr):
            cli = CodelaboonCLI()
            cli.load_providers()
        worker = cli.providers[provider]
    text = worker.chat(model, [{'role': 'user', 'content': prompt}], max_tokens=4096)
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Cloud provider returned no text')
    return text


def agent(model, prompt_file, runtime, engine="jcode"):
    if engine == "jcode":
        command = [sys.executable, str(Path(__file__).with_name("cli.py")), "jcode",
                   "--model", model.removeprefix("codelaboon/"), "run", "--json",
                   prompt_file.read_text(encoding="utf-8")]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=sys.stderr,
                                   text=True, encoding="utf-8", errors="replace")
        try:
            output, _ = process.communicate()
        except BaseException:
            from codelaboon.watch import terminate
            terminate(process)
            raise
        if process.returncode:
            raise RuntimeError(f"Lightweight agent failed (exit={process.returncode})")
        result = json.loads(output)
        if not isinstance(result.get("text"), str) or not result["text"].strip():
            raise RuntimeError("Lightweight agent returned no final response")
        return result["text"]

    environment = os.environ.copy()
    environment['CODELABOON_NATIVE_DIR'] = str(runtime / 'opencode')
    for kind in ('DATA', 'STATE', 'CACHE', 'CONFIG'):
        environment['XDG_' + kind + '_HOME'] = str(runtime / 'opencode' / kind.lower())
    source = Path(__file__).resolve().parent
    process = subprocess.Popen([sys.executable, str(source / 'cli.py'), 'tui', '--engine', engine, '--', 'run', '--format', 'json',
                                '--model', model, '--file', str(prompt_file),
                                'Execute the attached task specification.'],
                               stdout=subprocess.PIPE, stderr=sys.stderr, text=True,
                               encoding='utf-8', errors='replace', env=environment)
    texts = []
    failure = False
    complete = False
    try:
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                print(line, file=sys.stderr, end='')
                continue
            kind = event.get('type')
            if kind == 'error':
                failure = True
            if kind == 'text':
                texts.append(event.get('part', {}).get('text', ''))
            if kind == 'step_finish' and event.get('part', {}).get('reason') == 'stop':
                complete = True
            if kind != 'text':
                print(json.dumps(event), file=sys.stderr, flush=True)
        code = process.wait()
    except BaseException:
        from codelaboon.watch import terminate
        terminate(process)
        raise
    if code or failure or not complete or not any(text.strip() for text in texts):
        raise RuntimeError(f'Cloud agent incomplete or failed (exit={code}, final={complete})')
    return '\n'.join(texts)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='kilo')
    parser.add_argument('--model', required=True)
    parser.add_argument('--agent', action='store_true')
    parser.add_argument('--engine', default='jcode', choices=['jcode', 'opencode', 'omp', 'kilo'])
    parser.add_argument('--runtime', required=True)
    parser.add_argument('prompt_file', type=Path)
    args = parser.parse_args()
    try:
        if args.agent:
            text = agent(args.model, args.prompt_file, Path(args.runtime), args.engine)
        else:
            text = completion(args.provider, args.model,
                              args.prompt_file.read_text(encoding='utf-8'))
        print(text, flush=True)
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
