"""Exercise a real native source tool loop using only a local fixture model."""
import argparse
import subprocess
import sys

from native_fixture import ROOT, MARKER, fixture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--engine", choices=["opencode", "omp", "kilo"], default="opencode")
parser.add_argument("--setup", action="store_true")
args = parser.parse_args()

with fixture(args.engine, args.setup, tools=True) as (project, env, observed):
    native = ["--print", "--mode", "json"] if args.engine == "omp" else ["run", "--format", "json"]
    result = subprocess.run([sys.executable, str(ROOT / "codelaboon/cli.py"), "tui", "--engine", args.engine,
        "--local-only", "--", *native, "--model", "codelaboon/local/fixture",
        "Read marker.txt using the read tool, then report its content."],
        cwd=project, env=env, capture_output=True, text=True, timeout=120)
    logs = ROOT / ".runtime"
    logs.mkdir(exist_ok=True)
    (logs / f"{args.engine}-smoke.log").write_text(result.stdout + "\nSTDERR\n" + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stderr[-3000:]
    assert any(message.get("role") == "tool" and MARKER in str(message.get("content"))
               for body in observed for message in body.get("messages", [])), "No real tool result reached model"
    assert "Verified " + MARKER in result.stdout, result.stdout[-3000:]
    print(f"PASS: {args.engine} read a real file, returned its tool result through the gateway, and completed")
