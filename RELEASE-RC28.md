# RC28: task conversations and execution fixes

Tasks now work as durable conversations with the orchestrator. Read real model
replies and live partial replies, send a follow-up after completion, and watch
planning, execution and independent verification without mixing command output
into the assistant's reply. Raw logs remain available separately. Engine task
entry points share the same conversation API and stored history.

Follow-ups are consumed at scheduler checkpoints, without duplicating active
work or removing pauses, explicit stops, privilege boundaries or provider
cooldowns. A stopped worker starts when a guidance turn is sent; startup failure
preserves the message and reports how to start scheduling. Old workers must be
restarted safely to enable the new conversation capability.

OpenCode/Kilo no longer mistake the task instruction for a filename. Their
variadic attachment option now follows the positional message. The preceding
SQLite migration notice was not the cause of the task failure.

Free-provider exhaustion now returns retryable HTTP 503 and Retry-After instead
of misleading HTTP 400. Upstream retry delays and account-scoped cooldowns survive
gateway restarts, and other eligible free providers are tried before exhaustion
is reported. These changes do not create quota or permit paid fallback. Synthetic
live Kilo text and tool-call probes passed during preparation; owner Freebuff
credentials/admission were not tested.

The next attempt receives independent-check failures as well as the previous
worker reply, so the orchestrator can direct repairs based on actual evidence.
New web tasks default to one verified coding cycle and require a real project
check. Set the cycle limit to 0 explicitly for continuous work. Existing tasks
retain their configured policy.

Validation: 415 offline tests ran with 3 platform skips. Chromium browser checks
passed at 1440/768/390 widths, covering live replies, reload persistence, completed
follow-ups, task-form defaults, settings/changes, navigation and a visible
composer without horizontal overflow. Source syntax and structural checks pass.
The separate design inspector's CDP connection timed out; no successful report
from that inspector is claimed. Screenshots and real-browser interactions were
verified independently.

## Updating and restarting

After this release is published, in PowerShell:

```powershell
codelaboon work stop
codelaboon work status
```

Repeat the status command until the worker reports stopped. Stop is graceful:
the active attempt and checks finish first. Then run:

```powershell
codelaboon update
codelaboon work start
codelaboon tasks --open
```

Restart any already-open engine and web server processes as well so they load
the new code. If scheduling was intentionally paused, use `codelaboon work resume`
when you want queued work to run. Check `codelaboon status` for core version
1.0.0rc28. The updater selects the newest published release and verifies its
wheel checksum; an unpublished local tag is not an installable update.
