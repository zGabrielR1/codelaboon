"""Export and replay-check fork edits against pinned Git objects, excluding import transforms."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "scripts/patches"
DESTINATION.mkdir(exist_ok=True)

for name in ("opencode", "oh-my-pi"):
    source = ROOT / "codelaboon/_vendor" / name
    manifest = json.loads((source / "UPSTREAM.json").read_text(encoding="utf-8"))
    changes = {}
    for path, digest in manifest["upstream_sha256"].items():
        if path in ("package.json", "bun.lock"):
            continue  # Importer/workspace dependency transforms are separate from fork patches.
        after = (source / path).read_bytes()
        if hashlib.sha256(after).hexdigest() == digest:
            continue
        before = subprocess.check_output(["git", "-C", str(ROOT / "forks" / name),
                                          "show", manifest["revision"] + ":" + path])
        if hashlib.sha256(before).hexdigest() != digest:
            raise ValueError("Pinned original hash mismatch: " + path)
        changes[path] = before, after
    content = "".join("".join(difflib.unified_diff(before.decode().splitlines(keepends=True),
        after.decode().splitlines(keepends=True), fromfile="a/" + path, tofile="b/" + path))
        for path, (before, after) in sorted(changes.items()))
    patch = DESTINATION / f"{name}.patch"
    patch.write_text(content, encoding="utf-8")
    with tempfile.TemporaryDirectory() as directory:
        for path, (before, _) in changes.items():
            target = Path(directory) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(before)
        subprocess.run(["git", "apply", str(patch)], cwd=directory, check=True)
        for path, (_, after) in changes.items():
            if (Path(directory) / path).read_bytes() != after:
                raise ValueError("Patch replay differs: " + path)
    print(f"{name}: {len(changes)} edited source files replayed exactly")
