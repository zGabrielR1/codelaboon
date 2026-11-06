#!/bin/bash
# codelaboon structural verification script.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== codelaboon Verification Script ==="

fail() {
	echo "❌ Error: $*" >&2
	exit 1
}

required_files=(
    ".github/workflows/verify.yml"
    ".github/workflows/release.yml"
    "README.md"
    "LICENSE"
    "CHANGELOG.md"
    "pyproject.toml"
    "MANIFEST.in"
    "Makefile"
    "CURRENTTASK"
    "codelaboon/cli.py"
    "codelaboon/__init__.py"
    "codelaboon/__main__.py"
    "codelaboon/decision.py"
    "codelaboon/tui.py"
    "codelaboon/claude_auth.py"
    "codelaboon/gemini_auth.py"
    "codelaboon/freebuff_auth.py"
    "codelaboon/qoder_auth.py"
    "providers/__init__.py"
    "providers/base.py"
    "providers/chatgpt/chatgpt_provider.py"
    "providers/claude/claude_provider.py"
    "providers/gemini/gemini_provider.py"
    "providers/freebuff/freebuff_provider.py"
    "providers/qoder/qoder_provider.py"
    "providers/nvidia/nvidia_provider.py"
    "providers/openrouter/openrouter_provider.py"
    "providers/luna/luna_provider.py"
    "providers/ourfree/ourfree_provider.py"
    "providers/kilo/kilo_provider.py"
    "config/__init__.py"
    "config/providers.py"
    "config/providers.toml.example"
    "docs/AGENTS.md"
    "docs/ARCHITECTURE.md"
    "docs/PROGRESS.md"
    "docs/DECISIONS.md"
    "examples/questions.json"
    "scripts/verify.sh"
    "scripts/test.sh"
    "tests/test_codelaboon.py"
    "tests/test_claude.py"
    "tests/test_gemini.py"
    "tests/test_freebuff.py"
    "tests/test_qoder.py"
)

echo "Checking required files..."
for file in "${required_files[@]}"; do
	if [ ! -f "$file" ]; then
		fail "Required file '$file' not found"
	fi
	echo "✅ $file"
done

required_dirs=(
    "codelaboon"
    "providers"
    "providers/chatgpt"
    "providers/claude"
    "providers/gemini"
    "providers/freebuff"
    "providers/qoder"
    "providers/nvidia"
    "providers/openrouter"
    "providers/luna"
    "providers/ourfree"
    "providers/kilo"
    "config"
    "docs"
    "docs/utils"
    "docs/archive"
    "examples"
    "scripts"
)

echo ""
echo "Checking required directories..."
for dir in "${required_dirs[@]}"; do
	if [ ! -d "$dir" ]; then
		fail "Required directory '$dir' not found"
	fi
	echo "✅ $dir/"
done

echo ""
echo "Checking Python syntax..."
if ! find codelaboon providers config -name '*.py' -print0 | xargs -0 python3 -m py_compile; then
	fail "Python syntax check failed"
fi
echo "✅ All Python files compile"

echo ""
echo "Checking imports..."
python3 - <<'PY' || fail "Import check failed"
from codelaboon.cli import CodelaboonCLI
from config.providers import get_providers_config, save_provider_config
from providers.base import BaseProvider
print("✅ Imports OK")
PY

echo ""
echo "Checking required Python packages..."
if python3 -c "import requests" 2>/dev/null; then
	echo "✅ Python package 'requests' available"
else
	fail "Python package 'requests' not available (install python3-requests or 'requests')"
fi

echo ""
echo "Checking that no real credentials are committed..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	if git ls-files | grep -E '^config/(api_keys\.toml|providers\.toml)$' >/dev/null; then
		fail "A real provider configuration file is committed"
	fi
	echo "✅ No real configuration files are tracked by git"
else
	echo "⚠️  Not a git repository yet; skipping tracked-file check"
fi

if [ ! -x "scripts/verify.sh" ]; then
	chmod +x scripts/verify.sh
fi

echo ""
echo "=== Verification Complete ==="
echo "✅ All structural checks passed!"
echo ""
echo "Next steps:"
echo "1. Optionally run: make check   (requires make)"
echo "2. First run creates ~/.config/codelaboon/providers.toml automatically"
echo "3. Add your API keys, then: python3 -m codelaboon providers list"
