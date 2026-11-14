"""Run the official standalone Our Free Model source, without the DSH host."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from codelaboon.paths import config_dir

REPOSITORY = "https://github.com/Ebony-Vinyl/dsh-our-free-model.git"
REVISION = "edfdaf2cb64bb39c7c682b90c96ef9e3fef3be15"


def checkout():
    reference = Path(__file__).resolve().parent.parent / "forks/dsh-our-free-model"
    return reference if (reference / "packages/standalone/cli.mjs").is_file() else config_dir() / "runtime/ourfree"


def setup(source):
    if source.exists():
        raise ValueError("Source already exists; it was preserved. Use start or choose a new --source directory.")
    source.mkdir(parents=True)
    for command in (["git", "init", str(source)],
                    ["git", "-C", str(source), "remote", "add", "origin", REPOSITORY],
                    ["git", "-C", str(source), "fetch", "--depth", "1", "origin", REVISION],
                    ["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"]):
        subprocess.run(command, check=True)


def connect(data):
    from config.providers import save_provider_config
    settings = json.loads((data / "settings.json").read_text(encoding="utf-8"))
    key, port = settings.get("forwardKey"), settings.get("standalonePort")
    if not isinstance(key, str) or not key or type(port) is not int or not 0 < port <= 65535:
        raise ValueError("Start the standalone gateway first so it records its key and actual port")
    if not save_provider_config("ourfree", {"api_key": key, "models": [],
                                            "base_url": f"http://127.0.0.1:{port}/v1"}):
        raise ValueError("Could not save the gateway connection")
    print("Connected Our Free Model. Its gateway key is stored privately.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start", "connect"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--data-dir", type=Path, default=config_dir() / "ourfree")
    parser.add_argument("--port", type=int, default=18900)
    args = parser.parse_args(argv)
    source = (args.source or checkout()).resolve()
    if args.action == "setup":
        setup(source)
    elif args.action == "connect":
        connect(args.data_dir)
    else:
        node = shutil.which("node")
        entry = source / "packages/standalone/cli.mjs"
        if not node or not entry.is_file():
            parser.error("Node.js >=22.19 and the complete official source checkout are required; run ourfree setup")
        if not 0 <= args.port <= 65535:
            parser.error("Port must be between 0 and 65535")
        raise SystemExit(subprocess.call([node, str(entry), "--data-dir", str(args.data_dir.resolve()),
                                         "--port", str(args.port), "--no-lan"], cwd=source))


if __name__ == "__main__":
    main()
