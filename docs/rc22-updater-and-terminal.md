# RC22 candidate: recovery, continuous tasks and conversations

This source candidate is not a published RC22 release.

## Recovery and terminal

The updater verifies existing cached source dependencies and startup imports. Corrupt dependencies are preserved separately and rebuilt with a fresh cache; Windows uses copied files. A failed repair does not mark the runtime ready. Use `codelaboon status`, `codelaboon runtime status`, or `codelaboon runtime repair --engine opencode --force`. Update receipts record successful maintenance. Missing engines remain lazy unless explicitly requested.

## Tasks as conversations

Run `codelaboon web`, open the printed loopback URL, choose **Tasks**, then open a task. Its conversation contains the objective, orchestrator execution updates and your messages. Raw attempt output is expandable. The worker continues automatically according to the task budget and independent verification checks.

Choose **Guide next attempt** to add guidance at the next worker checkpoint, or **Save note only** for a human annotation. Guidance does not interrupt an active attempt. Pause holds subsequent attempts after current work and checks finish; resume continues the same objective. Drafts survive task switching within the open page.

Messages are persisted with an idempotent message ID. Delivery says **Queued for next attempt** until the worker captures the guidance in an attempt prompt. **Included in attempt** means the prompt contained it, not that a model read it or a verified cycle succeeded. Recent guidance is bounded to sixteen messages and 12,000 characters; conversation history displays the latest hundred messages and forty attempt updates. Scope, permissions and acceptance checks remain fixed.

A running worker must advertise `operator-interventions`; older workers allow notes only until safely restarted. Elevated tasks also allow notes only: an approved native privilege case is immutable. To change elevated work, review and queue a new task/case. The browser never approves elevation. No current worker is automatically restarted by this UI.

## Engines and monitoring

The task queue supports installed Jcode, OpenCode, OMP, Kilo, Claude, Codex and Crush. Jcode uses its native worker pool; the other engines run one portable coordinator per cycle. Protocol contract tests cover each adapter; native availability still depends on the installed engine and configured model.

Use `codelaboon swarm --status --watch --task TASK_ID` or `codelaboon work logs --follow --task TASK_ID` in the terminal. Ctrl+C closes the monitor only. Browser status refreshes every two seconds and exposes pause, resume, stop, verification policy and bounded redacted output.

See [continuous security swarms](continuous-security-swarms.md) for explicit targets, verification and permission setup. Full agent permissions do not grant administrator/root access, remove provider quotas or turn a logon task into a guaranteed pre-login service.
