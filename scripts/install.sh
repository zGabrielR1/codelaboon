#!/usr/bin/env bash
# Install codelaboon for the current user and add it to PATH.
#
#   bash scripts/install.sh
#   curl -fsSL https://raw.githubusercontent.com/zGabrielR1/codelaboon/main/scripts/install.sh | bash
#
# The Python installer does both steps: `pip install --user` and an idempotent
# PATH entry for bash/zsh/fish.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
	PYTHON=python
fi

cd "$ROOT"
exec "$PYTHON" -m codelaboon install "$@"
