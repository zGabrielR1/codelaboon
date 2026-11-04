# codelaboon Makefile - verification commands

.PHONY: help check lint all clean configure verify test

help:
	@echo "codelaboon Makefile - Available commands:"
	@echo ""
	@echo "Verification commands:"
	@echo "  make check      - Check structure, syntax and imports"
	@echo "  make lint       - Lint Markdown documentation (optional)"
	@echo "  make all        - Full verification"
	@echo "  make verify     - Run scripts/verify.sh"
	@echo "  make test       - Run offline unit tests"
	@echo ""
	@echo "Development commands:"
	@echo "  make clean      - Remove build artifacts"

check:
	@echo "Checking codelaboon structure..."
	@for file in codelaboon/cli.py codelaboon/__init__.py codelaboon/__main__.py \
		providers/__init__.py providers/base.py \
		providers/chatgpt/chatgpt_provider.py providers/nvidia/nvidia_provider.py \
		providers/openrouter/openrouter_provider.py providers/luna/luna_provider.py \
		providers/ourfree/ourfree_provider.py \
		config/providers.py README.md LICENSE pyproject.toml MANIFEST.in \
		docs/AGENTS.md docs/ARCHITECTURE.md docs/PROGRESS.md docs/CURRENTTASK; do \
		if [ ! -f "$$file" ]; then \
			echo "Error: $$file not found"; exit 1; \
		fi; \
	done
	@echo "✓ Core files present"
	@echo "Checking Python syntax..."
	@find codelaboon providers config -name '*.py' -print0 | xargs -0 python3 -m py_compile
	@echo "✓ Python syntax valid"
	@echo "Checking imports..."
	@python3 -c "from codelaboon.cli import CodelaboonCLI; from config.providers import get_providers_config; print('✓ Imports OK')"
	@echo "✓ All structural checks passed"

lint:
	@echo "Linting Markdown documentation..."
	@if command -v markdownlint-cli2 >/dev/null 2>&1; then \
		markdownlint-cli2 "docs/**/*.md" || echo "Warning: Markdown linting reported issues"; \
	else \
		echo "Warning: markdownlint-cli2 not found, skipping linting"; \
	fi

all: check lint
	@echo "Full verification completed."
verify:
	@scripts/verify.sh
test:
	@scripts/test.sh
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
	@rm -rf build dist *.egg-info
	@echo "✓ Build artifacts cleaned"
configure:
	@echo "Configuration is stored at ~/.config/codelaboon/providers.toml."
	@echo "It is created automatically on first run with restrictive permissions."
	@echo "See config/providers.toml.example for the format, and never commit real keys."
