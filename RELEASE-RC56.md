# RC56 improves task recovery after stopping the worker

- Task history and conversation show when a graceful worker shutdown interrupts execution or verification. On restart, the worker can pick the task up again without counting the interrupted attempt as a completed cycle or applying a harness cooldown.
- Continuous tasks can build their next prompt when a prior attempt receipt contains invalid metadata.
