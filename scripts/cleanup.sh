#!/bin/bash
# Keep make clean and the shell entry point available on Unix.
set -euo pipefail
exec "${PYTHON:-python3}" "$(dirname "$0")/cleanup.py" "$@"
