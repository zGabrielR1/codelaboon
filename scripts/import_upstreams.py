"""Import the runtime workspaces of pinned upstream releases, with provenance.

Reference repositories must already be cloned under the external development directory forks/. This never fetches,
changes git history, or overwrites an existing import.
"""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
from codelaboon.paths import development_dir
DEV = development_dir()
SPECS = {
    "opencode": ("https://github.com/anomalyco/opencode", "v1.2.27", "opencode"),
    "oh-my-pi": ("https://github.com/can1357/oh-my-pi", "v13.18.0", "@oh-my-pi/pi-coding-agent"),
}
REVISIONS = {"opencode": "4ee426ba549131c4903a71dfb6259200467aca81",
             "oh-my-pi": "3f60ba602abead98563fdab1d9d3db6b28cef429"}


def import_source(name, url, ref, entry):
    checkout = DEV / "forks" / name
    target = DEV / "vendor" / name
    if target.exists():
        raise SystemExit(f"Refusing to overwrite {target}")
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", ref], text=True
    ).strip()
    if revision != REVISIONS[name]:
        raise ValueError(f"Upstream revision mismatch for {name}; import stopped")
    raw = subprocess.check_output(["git", "-C", str(checkout), "archive", ref])
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members = {item.name: item for item in archive if item.isfile()}
        packages = {}
        for path, member in members.items():
            if path.startswith("packages/") and path.endswith("/package.json"):
                if path.count("/") > 3:
                    continue
                data = json.load(archive.extractfile(member))
                if data.get("name"):
                    packages[data["name"]] = (path.rsplit("/", 1)[0], data)
        selected = set()
        queue = [entry]
        while queue:
            key = queue.pop()
            if key in selected:
                continue
            selected.add(key)
            data = packages[key][1]
            for section in ("dependencies", "devDependencies", "optionalDependencies"):
                queue.extend(dep for dep in data.get(section, {}) if dep in packages and dep not in selected)
        roots = [packages[key][0] + "/" for key in sorted(selected)]
        hashes = {}
        for path, member in members.items():
            # Keep build configuration, notices, scripts and native sources.
            include = "/" not in path or path.startswith(tuple(roots + ["docs/", "patches/", "script/", "scripts/", "crates/", ".opencode/skills/", ".pi/skills/"]))
            if not include:
                continue
            content = archive.extractfile(member).read()
            destination = target / path
            if not destination.resolve().is_relative_to(target.resolve()):
                raise ValueError(f"Unsafe upstream path: {path}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            destination.chmod(member.mode & 0o777)
            hashes[path] = hashlib.sha256(content).hexdigest()
        package_path = target / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        workspaces = [root.rstrip("/") for root in roots]
        if isinstance(package["workspaces"], dict):
            package["workspaces"]["packages"] = workspaces
        else:
            package["workspaces"] = workspaces
        # Deployment tooling is outside this terminal-only fork.
        package["dependencies"] = {
            key: value for key, value in package.get("dependencies", {}).items()
            if key in selected or not value.startswith("workspace:")
        }
        package.get("scripts", {}).pop("prepare", None)
        package.get("devDependencies", {}).pop("sst", None)
        package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
        manifest = {"repository": url, "ref": ref, "revision": revision,
                    "entry": entry, "workspaces": workspaces, "upstream_sha256": hashes}
        (target / "UPSTREAM.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        patch = ROOT / "scripts" / "patches" / f"{name}.patch"
        if patch.is_file():
            subprocess.run(["git", "apply", str(patch)],
                           cwd=target, check=True)
        print(f"Imported {name} {revision}: {len(hashes)} files, {len(roots)} workspaces")


if __name__ == "__main__":
    for upstream_name, spec in SPECS.items():
        import_source(upstream_name, *spec)
