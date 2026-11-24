# RC52 protects virtual environments whose names match cleanup targets

Build cleanup preserves directories marked by `pyvenv.cfg` even when their names match top-level build output, packaging metadata, Python caches, or source directories. Both `python scripts/cleanup.py --dry-run` and `python scripts/cleanup.py` skip these environments. Cleanup still targets ordinary build output and Python caches.
