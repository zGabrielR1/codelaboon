# RC48 validates queued task records consistently

The task supervisor, router, and task controls share validation for inbox records. Records with invalid task IDs, verification commands, swarm options, or settings containers are skipped while valid tasks remain visible and runnable. The supervisor logs the filename and reason when it rejects an inbox record.
