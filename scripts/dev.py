"""Developer runtime preparation outside the backed-up source checkout."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codelaboon.paths import development_dir

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['paths', 'prepare'])
parser.add_argument('--engine', choices=['opencode', 'omp'], default='opencode')
args = parser.parse_args()
if args.action == 'paths':
    print(development_dir())
else:
    os.environ['CODELABOON_DEV_RUNTIME'] = '1'
    from codelaboon.native_tui import setup
    setup(args.engine)
