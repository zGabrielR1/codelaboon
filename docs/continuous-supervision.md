# Continuous permissions and active scope supervision

The worker remains an idle service until you queue an objective. Full access is
an explicit per-task choice, independent of the objective's allowed scope.

```bash
codelaboon work add "Fix README spelling only" --project . \
  --permissions full --supervise --scope "README.md only" \
  --allow-path README.md --check "git diff --check"
```

The same options are available on `swarm --continuous`: `--permissions`,
`--profile`, `--scope`, `--supervise`/`--no-supervise`, `--review-interval` and
repeatable `--allow-path`. Security tasks use `--profile security` and require an
explicit scope describing owned/authorized targets. Include real independent
acceptance checks for your task; the example's Git check checks formatting only.

## Permissions

`default` preserves native engine behavior. `full` turns off the supported agent
approval gates for that task's children: OpenCode/Kilo permission rules, Codex's
native approval/sandbox bypass, Claude Code's permission bypass, and Crush's
full `-yy` mode. Jcode/OMP already execute as ordinary native user processes;
there is no fictional privilege flag added to them. Native hard command rules,
model refusals and organizational controls may still apply.

Full mode does not grant root, configure sudo, override filesystem ownership,
SELinux or other operating-system restrictions, or change your login account.
Root/admin execution is available separately through [explicit privilege cases](rc20-security-and-operations.md). No passwordless sudo or privileged service is configured.
Permissions and security profiles are passed in each child's environment and
recorded with the attempt. They do not change another queued task's policy.

## Active supervision

Local-controlled tasks default to supervision when a local orchestrator is
configured. Worker-controlled swarms retain their independent controller unless
you explicitly add `--supervise`. The service loads the local router on demand,
including for a worker-controlled swarm that requests local scope review; it
unloads the model while idle to save RAM.

The controller samples bounded worker logs and Git status/diff metadata, with a
baseline of pre-existing changes. Supervised Jcode workers expose live tool traces
without corrupting their machine-readable final result. The local review chooses:

- Continue: retain the current attempt.
- Redirect: stop the active owned process group, invalidate the old plan, and
  replan the same objective with the saved correction and previous progress.
- Pause: stop the active attempt and leave a durable task control for review.

Original objective, permissions and scope cannot be changed by a model response.
Interventions require evidence present in the observed text. The optional file
allowlist pauses for observed changes outside the relative patterns without
asking the model. Reviews happen every 15 seconds by default (configurable
1–300 seconds) and before accepting even a short successful worker. Repeated
review errors, failed final review, or three repeated redirects pause the task.
Interrupted attempts do not pass acceptance or count as completed cycles.

```bash
codelaboon work status --json
codelaboon work pause TASK_ID
codelaboon work resume TASK_ID
codelaboon work stop TASK_ID
```

Only the supervisor writes scheduling state; operator commands use control files.
Restart an older worker after upgrading before queuing these task policies. The
CLI detects advertised service features and refuses to enqueue a policy the
running worker cannot honor.

This is sampled oversight, not an OS sandbox, a network target firewall, a
per-tool authorization gate, or an automatic rollback. An action can occur before
a review detects drift. File patterns cover observable project changes, not every
write anywhere on the machine. Full access and strong isolation are separate
choices. Keep one objective's scope explicit; use external isolation/per-tool
controls when an operation needs prevention before execution.

## What was actually checked

The reproducible RC20 local evaluation passed 11/13 synthetic scope cases, with
zero false interventions and two missed drift cases. The small controller is
fallible; this is a regression suite, not proof of general reasoning. See
[RC20 coverage and results](rc20-security-and-operations.md) for recorded model
identity, latencies, known misses and the independently tested file guard.

Native Codex and Jcode received the security profile and wrote only disposable
fixture files outside the fixture project under the selected full mode. Tests
cover active process interruption, redirect/replan with an unchanged objective,
file-limit pauses, review outages, final-review failure, task resume, and policy
isolation. No real user objective or active target was queued during this work.
