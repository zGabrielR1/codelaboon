# Continuous security swarms: status, scope and permissions

A continuous swarm repeats one fixed objective in verified cycles. It is useful
for regression assessment and hardening of an owned/authorized lab or application.
Starting the supervisor proves it is running, not that any cycle has succeeded.

## Monitor one task

Use the ID printed when the task was queued. In RC22 source builds:

```powershell
$id = 'YOUR-PRINTED-TASK-ID'
codelaboon swarm --status --watch --task $id
```

In another terminal:

```powershell
codelaboon work logs --follow --task $id
```

The status view shows verified cycles, policy, retry cooldown and the latest
attempt status/exit code/log directory. It labels failed attempts as retry waits
rather than simply scheduled. Log following switches to the new `output.log`
when another attempt starts. Ctrl+C closes the monitor/follower only; it does not
pause, stop or change the task. `--json` with a status watch emits one JSON object
per refresh, suitable for scripts.

Existing one-shot commands remain available:

```powershell
codelaboon swarm --status
codelaboon work status --json
codelaboon work logs
```

Task controls are separate:

```powershell
codelaboon swarm --pause $id
codelaboon swarm --resume $id
codelaboon swarm --stop $id
```

Pause/stop requests allow the active cycle and checks to finish; they are not an
instant process kill. A stopped swarm needs a newly queued task to run again.

## Interpret the result

- `cycles_completed` counts successful, verified cycles. Zero means no verified
  success yet, even when the service says running.
- `--workers 4` is a concurrency ceiling. The coordinator delegates when useful;
  it does not prove four agents are currently active.
- `--controller worker` uses the native worker as coordinator. It does not enable
  the separate local scope-review model.
- `--cycles 0` repeats until stopped; each cycle still has its own timeout and
  acceptance checks. `--interval` specifies the delay between cycles.
- Model quota/admission failures require a provider with available quota, waiting
  for limits to reset, or a configured local model. Additional OS privileges do
  not fix HTTP 429 or free-tier admission failures.

If the current attempt repeatedly fails, pause the task and inspect its output
before resuming. Listing a model or provider is not proof of available inference.

## Keep one objective and an actual scope

An objective says what to establish. A scope says where and how testing is
authorized. "Keep going until a production vulnerability is found" is not a
target allowlist or a valid success criterion: a complete assessment may find
no vulnerability. Do not require an agent to invent a finding to finish.

A practical task definition contains:

| Part | Specify |
| --- | --- |
| Fixed objective | One security property to assess and harden, such as authorization boundaries |
| Targets | Exact owned/authorized hosts, ports, environments and local paths |
| Allowed actions | Read-only probes, local test fixtures, approved branch changes, reports |
| Boundaries | Explicitly excluded production writes, destructive tests, unrelated hosts and secrets |
| Evidence | Reproduction prerequisites, actual observations, tool receipts and coverage gaps |
| Blue-team output | Defensive control/fix, regression test and retest evidence |
| Cycle acceptance | Relevant nonempty tests plus a fresh report verified against approved scope |

Use the coordinator to maintain the fixed objective and integrate results.
Assign a red-team role to bounded hypothesis testing, a blue-team role to
controls/remediation, and a verifier role to independently checking evidence and
regressions. Report a rejected hypothesis or no finding honestly. These roles
guide delegation; they are not separate OS security boundaries.

## PowerShell template for an authorized local lab

This template is a lab-only example. Replace the project and model with your
actual configuration. Create and review `tools/verify_security_cycle.py` before
queuing: it must validate fresh, in-scope evidence and relevant nonempty tests,
returning nonzero for incomplete/inconclusive coverage. That script is a
project-specific prerequisite, not a file shipped by Codelaboon.

```powershell
$project = 'D:\path\to\your\authorized-lab'
$scope = 'Only this local project and http://127.0.0.1:8080/. Local test fixtures and reports are allowed. No production systems, unrelated hosts, destructive tests or secret extraction.'
$objective = @'
Continuously assess and harden the local lab authorization boundary.
Keep this objective and scope fixed across cycles. Coordinate red-team,
blue-team and verifier work within the worker limit. Start with bounded,
least-impact probes. Record actual evidence, prerequisites and coverage gaps.
Propose/test defensive changes on a review branch. Independently retest.
Do not fabricate a finding; no vulnerability found is a valid observed result.
Do not change the acceptance verifier or approved scope to make a cycle pass.
Keep credentials out of reports. Stop and request review before leaving scope.
'@

codelaboon swarm $objective --continuous --controller worker --workers 2 --timeout 1800 --interval 300 --cycles 0 --model free --profile security --permissions full --scope $scope --project $project --check 'python tools/verify_security_cycle.py'
```

`free` is shown for syntax, not a promise of 24/7 quota. Select a configured
available model explicitly when needed; a local model uses its configured native
model ID. Begin with a modest worker limit and validate one cycle before leaving
the service unattended. Generic `python -m unittest discover -s tests` validates
only the tests it discovers and can succeed with zero tests; it does not by
itself establish a security finding or a fixed vulnerability.

## Full permission, supervision and administrator authority

| Setting | What it means |
| --- | --- |
| `--permissions full` | Disables supported native agent approval gates for that task; does not grant root/admin |
| `--profile security` | Applies security-oriented behavior guidance; requires scope text |
| `--supervise` | Requests a separate local scope-review controller; requires a configured/available local controller |
| `--allow-path` | Restricts observed project-file changes with supervision; repeat for multiple patterns |
| `--elevation administrator` / `root` | Queues the task awaiting an explicit native privilege case |

Check local controller readiness with `codelaboon doctor --json` before adding
`--supervise` to the template. Add only the relative file patterns the task needs
with repeatable `--allow-path`. Worker coordination alone is not active local
oversight. Scope prose, model review and file patterns are not an OS sandbox or
a network firewall; choose external isolation where prevention is required.

For an operation that genuinely needs elevation, queue it explicitly (using the
same reviewed project-specific verifier prerequisite):

```powershell
codelaboon work add 'Perform the specifically approved privileged lab operation and verify the result' --project $project --profile security --permissions full --elevation administrator --scope 'REPLACE with the exact authorized operation, targets and files' --check 'python tools/verify_security_cycle.py'
codelaboon privilege worker-case PRINTED_TASK_ID --timeout 1800
codelaboon privilege run PRINTED_CASE_FILE --approve PRINTED_CASE_ID --dry-run
codelaboon privilege run PRINTED_CASE_FILE --approve PRINTED_CASE_ID
```

Read the generated case before approval. Native Windows UAC or POSIX sudo
authorization is required. Cases expire, are single-use and bound execution time.
An elevated continuous swarm consumes one approved cycle and waits for a fresh
case for the next cycle. The supervisor does not approve or elevate itself.
A service launched under an already elevated OS account can inherit that
account's authority, but this is separate OS deployment, not a grant supplied
by `--permissions full`. The explicit-case workflow does not configure an
unattended, permanently privileged service.

## Reboots and 24/7 operation

`codelaboon work enable` registers OS autostart for the configured worker. The
Windows registration uses an interactive user logon trigger, so it does not
promise execution before sign-in after a reboot. Continuous operation also
depends on machine uptime, model availability, working acceptance checks and
network access where required. No queued-task flag guarantees those conditions.

See [continuous supervision](continuous-supervision.md),
[privilege cases](rc20-security-and-operations.md) and
[RC22 updater and terminal changes](rc22-updater-and-terminal.md).
