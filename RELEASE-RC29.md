# RC29: tasks in the actual chat

Tasks now appear beside ordinary conversations in the normal web chat sidebar.
Open a task, send guidance through the usual composer, and follow real
orchestrator plans and worker replies automatically. History belongs to the
worker and survives reloads and switching clients. Task controls remain available
for execution settings, attempts, checks and raw output, with a link back to chat.

## Native engine conversations

Run `codelaboon ENGINE --tasks TASK_ID`, or choose task conversations in the
engine launcher. The existing transcript is imported into that engine's normal
session and the shared `task/TASK_ID` gateway route is selected. OpenCode, OMP,
Kilo, Jcode, Codex, Claude Code and Crush adapters use this route. Human messages
enter the orchestrator's durable queue; planning and worker replies stream back
in the active conversation. Opening history starts no inference.

Use `/task status`, `/task start`, `/task pause`, `/task resume` and `/task stop`
in native task chats. Paused tasks retain messages until resumed. Worker child
environments exclude the interactive task model, preventing recursive task
routing. Existing task scope, permissions, stops and checks still apply.

The custom background-agent sidebar remains specific to the OpenCode fork.
Other engines keep their own layouts. Reopening a native session imports current
shared history; their UIs cannot receive new messages after an active response
ends. The web conversation continues polling between worker cycles.

## Free routing

Free Auto now inspects successful HTTP/SSE responses before committing a route.
An upstream credit-card or billing gate cools down that provider account and
another eligible free provider is attempted. Model catalogue availability does
not guarantee account admission. Exhausted routes return retryable unavailability;
paid fallback is never used. No account billing changes are made by this release.

## Update and restart

In PowerShell, run:

```powershell
codelaboon work stop
codelaboon work status
```

Wait until status reports stopped: active work and checks finish first. Then:

```powershell
codelaboon update
codelaboon work start
codelaboon tasks --open
```

Restart open engine and web processes to load the new code. Resume intentionally
paused scheduling with `codelaboon work resume` when ready. Check
`codelaboon status` for version `1.0.0rc29`.

## Validation and limits

423 offline tests passed (3 platform skips); all 8 focused task tests also pass
against the installed wheel. Structural verification, artifact checks and real Chromium
interaction tests cover the shared web conversation and native HTTP transports.
Browser checks run at 1440, 768 and 390 pixels, including durable follow-ups,
reload, switching between task and regular chats, and a visible composer without
overflow. Chat, Responses and Anthropic task protocols are tested over HTTP.
Installed native engine UIs and live provider account admission were not verified
in the restricted release-preparation environment.
