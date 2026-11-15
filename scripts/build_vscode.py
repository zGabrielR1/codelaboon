"""Build the dependency-free Codelaboon editor connector release asset."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codelaboon.ide import build_vsix
path=Path(sys.argv[1] if len(sys.argv)>1 else 'dist/codelaboon-vscode.vsix')
print(build_vsix(path))
