"""Check every packaged native source against its upstream/fork provenance manifest."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent.parent
for name in ("opencode", "oh-my-pi"):
    path = ROOT / "codelaboon/_vendor" / f"{name}.tar.gz"
    with tarfile.open(path) as archive:
        members = archive.getnames()
        if any(Path(member).is_absolute() or ".." in Path(member).parts or "node_modules" in Path(member).parts
               for member in members):
            raise ValueError("Unsafe or runtime dependency path in " + str(path))
        manifest = json.load(archive.extractfile("UPSTREAM.json"))
        expected = {**manifest["upstream_sha256"], **manifest["fork_sha256"]}
        if set(members) != {*expected, "UPSTREAM.json"}:
            raise ValueError("Unlisted or missing source files in " + str(path))
        if "LICENSE" not in expected:
            raise ValueError("Missing upstream license in " + str(path))
        for file, digest in expected.items():
            if hashlib.sha256(archive.extractfile(file).read()).hexdigest() != digest:
                raise ValueError("Source digest mismatch: " + file)
    print(f"PASS {name}: {len(expected)} source files, license and fork provenance")
