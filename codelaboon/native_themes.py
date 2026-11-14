"""Install additive themes through each upstream engine's native theme loader."""
from pathlib import Path
import os
import tempfile

ASSETS = Path(__file__).parent / "themes"
DEFAULT = "codelaboon-kilo"


def install(engine, directory):
    source = ASSETS / ("omp" if engine == "omp" else "opencode")
    destination = Path(directory) / "themes"
    destination.mkdir(parents=True, exist_ok=True)
    for asset in source.glob("*.json"):
        target = destination / asset.name
        content = asset.read_bytes()
        if target.is_file() and target.read_bytes() == content:
            continue
        descriptor, temporary = tempfile.mkstemp(prefix=".theme-", dir=destination)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
