# RC40 makes long-running task workspaces lighter

- Choose **Recent activity** in the task queue to put tasks with newer attempt updates first. Switch back to **Queue order** at any time.
- Idle Tasks and Web Chat views check for changes less often. Active task views continue to refresh frequently, and returning to a hidden tab refreshes its data.
- Task monitoring reads attempt receipts once per snapshot. An unreadable or invalid receipt is skipped so the remaining tasks stay visible.
- Long conversations retain only their newest attempt events during a read. Opening an individual historical log reads that attempt directly.

Run `codelaboon update` after the prerelease is published, then restart the running web workspace and task worker.
