#!/bin/bash
# codelaboon build-leftover cleanup.
#
# Removes only regenerable artifacts: bytecode caches, build/dist
# output, and packaging metadata. Deliberately leaves alone:
#   releases/          preserved local release artifacts
#   *.local/           local validation sandboxes and workspaces
#   ~/.config/codelaboon/  real credentials and sessions (never touched)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== codelaboon Cleanup Script ==="

find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
find . -name '*.pyc' -delete
find . -name '*.pyo' -delete
rm -rf build dist *.egg-info

leftover=$(find . -type d \( -name __pycache__ -o -name build -o -name dist \) -print -quit)
if [ -n "$leftover" ]; then
	echo "❌ Cleanup incomplete: $leftover remains" >&2
	exit 1
fi

echo "✅ Build leftovers removed (releases/ and *.local/ kept)"
