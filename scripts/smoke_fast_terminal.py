"""Exercise startup when a terminal answers OSC 11 immediately, as VTE does."""
import argparse
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import sys
import termios
import time

from native_fixture import ROOT, REPLY, fixture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--development', action='store_true')
parser.add_argument('--timeout', type=float, default=60)
args = parser.parse_args()
artifacts = ROOT / '.runtime/ui-qa'
artifacts.mkdir(parents=True, exist_ok=True)

with fixture('opencode', development=args.development) as (project, env, observed):
    command = ([sys.executable, str(ROOT / 'codelaboon/cli.py')] if args.development
               else [shutil.which('codelaboon')])
    command.extend(['tui', '--', '--model', 'codelaboon/local/fixture'])
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(project)
        fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 38, 120, 0, 0))
        os.execvpe(command[0], command, env)
    output = bytearray()
    answered = False
    submitted = False
    complete = False
    try:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if not select.select([master], [], [], 0.1)[0]:
                continue
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            output.extend(data)
            if not answered and b'\x1b]11;?\x07' in output:
                # Do not introduce tmux's delay: this reply used to outrun Rpc.listen.
                os.write(master, b'\x1b]11;rgb:0000/0000/0000\x07')
                answered = True
            if not submitted and b'Ask anything' in output and b'c o d e l a b o o n' in output:
                os.write(master, b'fast-terminal-startup-check')
                time.sleep(0.25)
                os.write(master, b'\r')
                submitted = True
            if submitted and REPLY.encode() in output and observed:
                complete = True
                break
    finally:
        (artifacts / 'opencode-fast-terminal.bin').write_bytes(output)
        os.killpg(pid, signal.SIGTERM)
        # Reap the isolated process group without leaving a native UI behind.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if os.waitpid(pid, os.WNOHANG)[0]:
                break
            time.sleep(0.05)
        else:
            os.killpg(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(master)
    assert answered, 'OpenCode never queried the terminal background'
    assert submitted, 'Fast terminal reply left startup blank; see .runtime/ui-qa/opencode-fast-terminal.bin'
    assert complete, 'The native UI did not complete a fixture model request'
    print('PASS: immediate terminal reply rendered OpenCode and completed a model request')
