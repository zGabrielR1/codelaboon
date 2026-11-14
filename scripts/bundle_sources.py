"""Package only provenance-listed sources and fork patches, never dependencies or state."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent.parent


def bundle(name):
    source = ROOT / "codelaboon/_vendor" / name
    manifest = json.loads((source / "UPSTREAM.json").read_text(encoding="utf-8"))
    paths = sorted(set(manifest["upstream_sha256"]) | {"UPSTREAM.json"})
    manifest["fork_sha256"] = {
        path: hashlib.sha256((source / path).read_bytes()).hexdigest()
        for path, digest in manifest["upstream_sha256"].items()
        if hashlib.sha256((source / path).read_bytes()).hexdigest() != digest}
    output = source.parent / f"{name}.tar.gz"
    temporary = output.with_suffix(".tmp")
    with temporary.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w") as archive:
            for path in paths:
                file = source / path
                if not file.resolve().is_relative_to(source.resolve()) or not file.is_file():
                    raise ValueError(f"Missing or unsafe source: {path}")
                info = archive.gettarinfo(str(file), arcname=path)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                if path == "UPSTREAM.json":
                    content = json.dumps(manifest, indent=2).encode() + b"\n"
                    info.size = len(content)
                    archive.addfile(info, io.BytesIO(content))
                else:
                    with file.open("rb") as stream:
                        archive.addfile(info, stream)
    temporary.replace(output)
    print(f"{name}: {len(paths)} source files; sha256={hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    for name in ("opencode", "oh-my-pi"):
        bundle(name)
