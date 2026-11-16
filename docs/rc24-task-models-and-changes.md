# RC24: task models, orchestration, prompts and project changes

## Browser and terminal

Open a task conversation and choose **Models & prompts**. Set the worker model, planning
mode, planning model, worker system instructions and planning system instructions, then
save. Settings are captured at the next eligible attempt; current work, verification and
retry scheduling continue. The dialog shows desired and latest-attempt revisions.

The terminal task viewer has **Settings** and **Changes** buttons. Models use `free` or
`PROVIDER/MODEL`, for example `nvidia/YOUR_MODEL` or `local/YOUR_MODEL`. Suggestions are
configured/default IDs, not live availability guarantees. Use an installed engine and a
model/protocol it supports. Explicit compatible cloud model selections are available
alongside free models; Auto remains limited to its free provider pool.

## Coordinator roles

| Mode | Behavior | Model |
| --- | --- | --- |
| Embedded worker | The selected engine coordinates its own work, as in RC23 | Worker model |
| Cloud planner | A separate model writes a bounded next-step plan; the engine executes it | `free` or `PROVIDER/MODEL` |
| Local planner | A separate configured loopback model writes the plan; no cloud fallback | `local/MODEL` |

This planning coordinator is distinct from the optional legacy local scheduler/scope
reviewer. Changing task planning mode does not replace or disable a configured scope
reviewer. The planning model has no execution tools. Planning, worker execution and
independent checks share the cycle budget; a failed planner prevents worker dispatch.
Its plan or failure appears in the task conversation. No local model is downloaded or
started by selecting local planning: configure/start your local provider first.

Worker settings apply to the engine coordinator and all delegated requests through that
task's gateway. A separate planner uses its own provider/model. Jcode retains its native
worker pool; the other engines remain one portable coordinator per cycle. This does not
create native parallel swarms for engines that do not have them.

## CLI examples

Replace task/model placeholders with real IDs from your installation.

```powershell
$id = 'instruction-YOUR_ID'
codelaboon tasks $id --settings
codelaboon tasks $id --worker-model nvidia/YOUR_WORKER_MODEL
codelaboon tasks $id --orchestrator cloud --orchestrator-model nvidia/YOUR_PLANNER_MODEL
codelaboon tasks $id --orchestrator local --orchestrator-model local/YOUR_LOADED_MODEL
codelaboon tasks $id --orchestrator worker
codelaboon tasks $id --system-prompt-file .\worker-system.md --orchestrator-prompt-file .\planner-system.md
codelaboon tasks $id --changes
```

Prompt files are UTF-8; an empty file clears the additive instructions. These are actual
system-channel additions at the task gateway, preserving native base instructions and
fixed task authority, scope, permissions and independent checks. They do not edit project
AGENTS.md files or grant OS privileges. The planner has its own separate system message. Planning instructions are used only in local/cloud planning modes; embedded coordination uses the worker instructions.

For a new browser task, expand **Planning model and system instructions** before the
review step. Initial settings are embedded atomically in the queued task, so its first
attempt cannot race ahead with default planning settings. CLI creation accepts
`swarm --continuous --execution-settings-file FILE.json` with these exact five fields:

```json
{
  "worker_model": "free",
  "orchestrator_mode": "local",
  "orchestrator_model": "local/YOUR_LOADED_MODEL",
  "worker_system_prompt": "Prefer small changes and regression evidence.",
  "orchestrator_system_prompt": "Prioritize the next verifiable increment and state blockers."
}
```

Each saved update uses an atomic revision and optimistic concurrency check. Reload if
another session has changed the settings. Existing ordinary continuous tasks can be
edited; finished tasks and administrator/root approval snapshots cannot. Elevated tasks
may capture initial settings before native approval, but later changes require a new
reviewed task/case.

## Project changes

**Changes** shows read-only Git status, diff statistics and a bounded patch against HEAD,
including staged and unstaged edits. Existing changes and concurrent editors' changes
are explicitly labelled; this view does not claim everything was made by the agent.
Untracked filenames appear without their file contents. Common credential patterns are
redacted; the view is not a complete secret scanner.

New attempts also record filenames observed changing between checkpoints. This is
bounded observation, not exclusive authorship or a full filesystem audit. Older/in-flight
attempts may have no observation record. Git metadata/committed HEAD is needed for a
useful diff; no commit, staging, rollback or reset is performed by this viewer.

## Upgrade a running worker

After updating to RC24, a worker that was already running still has old code. Settings
are read-only until it advertises `task-execution-settings`. To enable them, stop the
service gracefully, wait until status reports stopped, then start it again:

```powershell
codelaboon work stop
codelaboon work status
# Wait for the active attempt/checks and service shutdown.
codelaboon work start
```

`work stop` preserves queued tasks; stopping a particular swarm with `swarm --stop ID`
is a different operation. The updater/UI does not automatically restart your active
worker. Reload browser/engine interfaces after updating.

For native interactive chats outside a background task, use that engine's model picker
or native model arguments (for example `codelaboon jcode --model PROVIDER/MODEL`). The
settings described here are task-specific, not global changes to every native session.
