# RC23: open and follow task conversations

RC23 fixes task access and ships the RC22 candidate features, which were not published separately.

## Browser

Run `codelaboon tasks --open` or choose **Tasks** in `codelaboon web`. Click a task.
It opens `/tasks?task=TASK_ID`, with its own conversation, scrolling messages and visible
composer. Task policy moves into a collapsible details section. Browser Back/Forward,
reload and direct links work. Mobile opens the conversation rather than leaving it
below the task list. **Back to tasks** returns to the list.

Worker output refreshes every two seconds while live updates are enabled and the page
is visible. Captured output is labelled separately from orchestrator execution status.
A model failure is shown as a failure; it does not become a fabricated assistant reply.
Send guidance for the next attempt, or save a note. Pausing allows current work and
verification to finish before further attempts. Viewing a task never starts inference.

## Terminal and every engine

Bare `codelaboon` and bare engine aliases show a launcher with **Task conversations**,
**Task conversations in browser**, or the selected engine chat. This makes tasks visible
before entering a native engine. The task viewer returns to the launcher when closed.
Native engine session history remains separate from background task conversations.

```powershell
codelaboon tasks
codelaboon tasks instruction-YOUR_ID
codelaboon tasks --list
codelaboon tasks --open
codelaboon opencode --tasks
codelaboon omp --tasks instruction-YOUR_ID
codelaboon tui --engine codex --tasks
codelaboon opencode --direct
```

`--tasks` works with OpenCode, OMP, Jcode, Codex, Claude, Kilo and Crush. The terminal
viewer uses the optional Textual extra (`pip install 'codelaboon[tui]'` in the same
installation environment); the base install falls back to browser task conversations.
Select a task from the left, read live output, enter guidance and press Send/Enter.
Ctrl+Q returns to the engine launcher; Ctrl+R refreshes. Notes remain available for
older workers. Commands with native arguments and headless jobs bypass the launcher;
`--direct` explicitly bypasses it for an interactive engine session.

This is a shared task viewer, not a claim that every native engine embeds the same
custom pane or slash command. To switch from an already running native chat, leave
that native session or use another terminal to run `codelaboon tasks`.

## Update and worker compatibility

Update to RC23 before testing the new navigation. A long-running background worker
retains its loaded code; new guidance requires a worker advertising
`operator-interventions`. The UI explicitly uses note-only mode for older workers;
it does not restart them or discard active work. Stop the service gracefully and
start it again at a safe checkpoint if you want it to consume new guidance.

Guidance stays within the original objective, scope, permissions and checks. Receipts
say queued or included in an attempt, not that a model successfully read the prompt.
Elevated cases accept notes only because their approved payloads are immutable.
See [recovery and task policy](rc22-updater-and-terminal.md) and
[continuous security setup](continuous-security-swarms.md).

## Validation

Real-browser regression covers click-to-open, direct links, reload, Back, live output,
guidance persistence and composer visibility at 1440, 768 and 390 pixels, using an
isolated fake worker and no provider calls. Terminal tests cover live output and
guidance, old-worker note mode, seven engine aliases and headless bypass.
