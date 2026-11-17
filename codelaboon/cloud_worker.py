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
    if engine != 'jcode':
        from codelaboon.engine_tasks import run
        return run(engine,model,prompt_file,runtime)
    if engine == "jcode":
        command = [sys.executable, str(Path(__file__).with_name("cli.py")), "jcode",
                   "--model", model.removeprefix("codelaboon/"), "run", "--json",
                   prompt_file.read_text(encoding="utf-8")]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=sys.stderr,
                                   text=True, encoding="utf-8", errors="replace",start_new_session=os.name!='nt',
                                   env=dict(os.environ,CODELABOON_HEADLESS_TASK='1'))
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

def main():
    import signal
    def stopped(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stopped)
    if os.name!='nt':signal.signal(signal.SIGHUP,stopped)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', default='kilo')
    parser.add_argument('--model', required=True)
    parser.add_argument('--agent', action='store_true')
    parser.add_argument('--engine', default='jcode', choices=['jcode', 'opencode', 'omp', 'kilo','claude','codex','crush','devin'])
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
