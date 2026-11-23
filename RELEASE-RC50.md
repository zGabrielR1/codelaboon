# RC50 resolves duplicate task IDs consistently

The supervisor, router, status views, and task controls now select the same record when a configured task and an inbox record share an ID. The configured task takes precedence. If several valid inbox files share an ID, the first by filename wins. Status shows the task once, and a shadowed inbox record cannot start the router or change which task the controls apply to. When the selected inbox task's project is unavailable, that task waits for its directory to return.

Build cleanup now works directly on Windows with `python scripts/cleanup.py` and supports `--dry-run`. It removes packaging output and source caches while preserving local runtimes, release archives, and vendor checkouts. Source distributions include the engine manifest and omit vendor checkout contents.
