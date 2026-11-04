#!/bin/bash
# codelaboon offline test runner.
set -euo pipefail
cd "$(dirname "$0")/.."

TMPDIR_CONFIG="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_CONFIG"' EXIT

CODELABOON_CONFIG_DIR="$TMPDIR_CONFIG" python3 -m unittest discover -s tests -v
