# Task actions and shared connections

Tasks use the normal web chat sidebar and composer. Open a task to follow the
orchestrator and send guidance. Routine scheduling updates appear in a compact
activity region in operations, rather than repeated dated assistant messages.
The task title remains visible on a phone. Unchanged polling responses preserve
the thread DOM, scroll position and text selection.

## Open in an engine

Choose **Open in engine** from the task chat or operations view, select an
installed engine, and choose **Open engine**. A desktop terminal opens the same
task conversation with its stored history. The engine uses the same local
connections as the web workspace. Launching is an authenticated POST and passes
an argument vector to the terminal, with no shell interpolation. Relative project
paths resolve against the worker configuration directory.

Windows uses Windows Terminal when available and a new console otherwise.
Linux uses an available desktop terminal. macOS currently displays the explicit
terminal command instead of attempting an unconfigured terminal handoff.

## Delete a task

Choose **Delete task** in either view and review the confirmation. Deletion
removes the task from the chat library, operations, and future scheduling. An
active attempt and independent checks finish safely. Project files and local
attempt logs are retained. The durable deletion receipt prevents a scheduler
restart from bringing the task back. It also writes a stop control understood by
older workers.

The terminal equivalent is `codelaboon tasks TASK_ID --delete`. Deleting an
already deleted ID is safe to repeat. Deleted task conversations reject new
messages and cannot be opened through the task gateway.

## Understand failed checks

A failed check shows its command, exit code, and bounded, redacted output. The
next orchestrator attempt receives that evidence automatically. Worker execution
reserves 20 percent of a continuous cycle, up to 120 seconds, for independent
verification while keeping the original overall cycle deadline.

A missing verifier pauses scheduling so it can be fixed, rather than repeatedly
spending model requests on a broken setup. Three identical check failures also
pause for review. Fix the project or verification configuration, or choose a
more suitable model, then resume. Resuming from the web resets this review
counter. Missing application fixtures remain ordinary repairable test failures;
they are not treated as a missing verification command. Configuration and
verification timeout failures do not count as negative coding-quality feedback
for the selected model. A failed check is never marked as a successful cycle.

## Connections

Open **Connections** in the web navigation. Account sign-in is available for
ChatGPT, Claude, Google Gemini, Freebuff, Qoder and GitHub Copilot. Pending sign-in
shows its provider link, device code when applicable, and completion state.
API-key setup is available for Vercel AI Gateway, HowToFix, WusRouter, Groq,
Cerebras, OpenRouter, NVIDIA and Luna. Keys stay in the local configuration and
are cleared from the form when it closes.

Sign-ins and keys use the same provider adapters and configuration directory as
the engines. Engine gateways and the proxy detect saved connection changes on
their next request, reload providers, and invalidate stale model catalogues and
account cooldowns. Native model pickers that cache their own configuration may
need an engine restart to list newly available models. Provider access, account
admission and quotas still apply.

After installing this source change in a release, restart existing web and engine
processes once. Stop the background worker gracefully and wait until it reports
stopped before updating and restarting it; the new worker advertises the
`task-diagnostics` feature. This source change does not itself update an installed
release or interrupt active work.
