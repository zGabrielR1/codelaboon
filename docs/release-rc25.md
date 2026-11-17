# Codelaboon 1.0.0rc25 - Task operations and account sources

- Filter task conversations by state, see timestamps, keep drafts across reloads,
  send with Ctrl/Cmd+Enter and recall the last message with Up.
- Inspect the latest 50 attempts, their stage/result/exit code and bounded,
  redacted captured output. Historical logs must belong to the selected task.
- Retry a finished failed continuous task at the next checkpoint without
  duplicating active work, changing verification or reapproving an elevated case.
- Start, pause scheduling or resume the existing worker from the browser, CLI or
  terminal. Starting/resuming requires confirmation because all ready tasks can run.
- Save a HowToFix API key and read its authenticated live model catalogue. Connect
  GitHub Copilot with device OAuth and use account models through the native gateway.
- Add the optional official Windsurf/Devin native account, model list and task
  engine, installed lazily from its checksum-verified release manifest.

Open `codelaboon tasks TASK_ID`, then use Attempts, Retry failed and the worker
controls, or use the shared CLI:

```bash
codelaboon update
codelaboon tasks TASK_ID --attempts
codelaboon tasks TASK_ID --retry
codelaboon configure howtofix
codelaboon login copilot
codelaboon accounts devin setup
```

Older running workers need a graceful restart before accepting the new controls.
Retry is limited to ordinary, non-elevated continuous tasks. Paused tasks must be
resumed first. Account sources require the owner's authorization and their own
quota/billing; HowToFix, Copilot plan quotas and Windsurf/Devin usage are not
silently treated as zero-cost free Auto routes. Native account use can consume
plan or paid quota. Windsurf/Devin does not expose an invented raw model endpoint
or add another session-transfer format.

[Usage and examples](https://github.com/zGabrielR1/codelaboon/blob/main/docs/task-operations-and-accounts.md)
