# RC30: task actions, shared connections and verification recovery

Task conversations now offer **Open in engine** and **Delete task** in both the
normal web chat and operations view. Engine handoff opens the same stored thread
in an installed native engine. Retried launch requests do not open duplicate
terminals, and dialogs cannot switch tasks or close while an action is in flight.

Deletion has a confirmation explaining its effect: the task disappears from
conversations and future scheduling, active work and checks finish safely, and
project files and local attempt logs are retained. Scheduler restarts cannot
restore a deleted task. CLI: `codelaboon tasks TASK_ID --delete`.

## Connections shared with engines

The Connections page supports browser sign-in for ChatGPT, Claude, Gemini,
Freebuff, Qoder and GitHub Copilot, plus API-key setup for eight providers.
Sign-in progress includes a provider link and device code when applicable.
Keys remain local and are cleared from the form when it closes. Returning to
the page refreshes connection state; hidden tabs do not poll pending sign-ins.

Engine gateways and the proxy detect saved connections on the next request,
reload credentials and invalidate stale catalogues/account cooldowns. Native
model pickers that cache their own lists may still require reopening the engine.
Provider quotas and account admission still apply.

## Clearer task progress and fewer repeated failures

Phone layouts keep the task title visible. Only relevant controls are shown,
unchanged polling preserves the thread, and routine scheduling updates remain
outside assistant messages. Successful actions use status feedback rather than
error styling.

Failed checks show their command, exit code and bounded redacted output. Workers
reserve 20 percent of a continuous cycle, up to 120 seconds, for verification
within the existing cycle deadline. Missing verifiers and three identical check
failures pause for review instead of looping. Application missing-file failures
remain repairable. Broken verification infrastructure is not negative feedback
about the coding model. Failed checks are never counted as successful cycles.

## Updating

```powershell
codelaboon work stop
codelaboon work status
```

Wait until the worker reports stopped; active work and checks finish first.
Then install the published update and restart:

```powershell
codelaboon update
codelaboon work start
codelaboon tasks --open
```

Restart existing web and native engine processes once to load the new gateway
code. Thereafter saved connections can reload on the next request. The new worker
advertises `task-diagnostics`. Check `codelaboon status` for `1.0.0rc30`.

## Validation and limits

434 offline tests ran with 3 platform skips. All 11 task UX tests also pass
against the installed wheel. Tests cover lifecycle, authenticated handoff, retry deduplication,
verification recovery, and an already-running gateway using newly saved
credentials. Chromium checks at 1440/768/390 cover chat navigation, launch dialogs,
in-flight cancellation protection, deletion, sign-in/key setup, and tab refresh.
Structural, syntax, pinned-source and thin-artifact checks are release gates.
Browser sign-ins and terminal launches use fixtures: real provider authorization
and installed native terminal UIs were not exercised. Windows/Linux terminal
handoff is supported; macOS reports the explicit terminal command. The separate
design inspector timed out at CDP Page.enable; independent browser screenshots
and interaction checks passed.
