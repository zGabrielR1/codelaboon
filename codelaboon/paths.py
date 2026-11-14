"""Filesystem paths shared by codelaboon modules.

``CODELABOON_CONFIG_DIR`` is the single override for the configuration
directory. Everything else resolves a home directory lazily: tests and
embedded runs sometimes clear the environment, and ``Path.home()`` raises when
no home variable exists. Falling back to ``HOME``/``USERPROFILE`` and finally
the current directory keeps auth and config code usable instead of crashing.
"""

import os
from pathlib import Path


def home() -> Path:
    """Return the user's home directory without raising when none is set."""
    try:
        return Path.home()
    except RuntimeError:
        pass
    for name in ("HOME", "USERPROFILE"):
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value)
    return Path.cwd()


def config_dir() -> Path:
    """Return the codelaboon configuration directory."""
    configured = os.environ.get("CODELABOON_CONFIG_DIR", "").strip()
    if configured:
        return Path(configured)
    return home() / ".config" / "codelaboon"


def cache_dir() -> Path:
    """Rebuildable downloads/development files, outside project backups."""
    explicit = os.environ.get('CODELABOON_CACHE_DIR', '').strip()
    return Path(explicit) if explicit else Path(os.environ.get('XDG_CACHE_HOME') or home() / '.cache') / 'codelaboon'


def development_dir() -> Path:
    return Path(os.environ.get('CODELABOON_DEV_DIR') or cache_dir() / 'development')


def data_dir() -> Path:
    """Durable optional assets such as local model weights and release copies."""
    return Path(os.environ.get('CODELABOON_DATA_DIR') or Path(os.environ.get('XDG_DATA_HOME') or home() / '.local/share') / 'codelaboon')
