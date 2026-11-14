# RC16 adversarial review — 2026-11-14

Reviewed continuous scheduling, verification, control modes, native UI isolation,
process ownership, upgrade behavior and preservation of the RC15 lean layout.

Resolved findings:

- A bounded one-shot swarm is not continuous operation. Queue recurring objectives
  in the durable supervisor, persist successful cycle counts and next due times,
  and expose per-objective pause/resume/stop. Do not create speculative user jobs.
- Model output is not acceptance. Each build and its independent commands share a
  budget; failed checks/timeouts cannot advance cycles. Fix ordinary queued tasks
  that previously skipped checks when no local orchestrator was configured.
- Local control and worker control must behave differently. Local jobs use the
  router and plan/build lifecycle. Native coordinator jobs bypass that dependency;
  an unavailable local router advances fairness rather than starving worker jobs.
  Model demand uses the same pause/due rules and ignores worker-controlled jobs.
- Plain completion planners cannot inspect local log paths. Supply bounded prior
  output context, plus full log references for native tools, so later cycles can
  build on verified progress without repeatedly growing prompt size.
- Stop/pause must not destroy active work. Apply at attempt boundaries; finish the
  active build and independent checks. Successful cycle limits and terminal stop
  state are explicit. Preserve all histories under external runtime/data paths.
- An older live supervisor would silently consume new task metadata incorrectly.
  Publish service capabilities; reject enqueue before writing a task until the
  old supervisor is gracefully restarted after upgrading.
- Jcode's original wrapper used a fresh profile and a headless 30-minute timeout
  even for its UI. Use durable per-project native profiles, preserve display
  preferences, support native resume, and remove the interactive timeout.
- A native UI may spawn a daemon retaining an obsolete gateway token. Start an
  owned temporary server before attaching the UI; private endpoints, profile
  locks, bounded readiness and finally-based cleanup prevent cross-session races.
  Native UI/session resume and actual server exit are exercised, not inferred.
- Terminating detached supervisors must unwind owned child groups. Handle TERM
  and HUP through cleanup in service/watch entrypoints; native execution already
  restores signal handlers and cleans its private server/worker groups.
- Fixed-time worker delays make cap tests flaky. Use a fixture barrier until the
  coordinator observes the native excess-worker rejection. Bound request counts.
- Acceptance commands may contain JSON/Python braces. Preserve literal argv
  instead of formatting checks as supervisor templates.

Evidence: 223 passing unit tests; native Rust tools; native
Jcode UI reply/session resume/owned-server exit; two real swarm cycles across a
supervisor reload; actual background service with CLI pause/resume/status and
independent checks. Installed OpenCode VTE rendering/reply/Up recall and source provenance pass.
Full native release CI remains required before publication.
No new runtime dependency or bundled source tree; checkout stays about29MB.

Limits: continuous work repeats bounded cycles, not immortal resident workers.
The supervisor runs objectives serially while swarm workers run in parallel.
Local routing chooses plan/build jobs; the native coordinator delegates detailed
worker tasks. History naturally accumulates outside ppp; nothing is auto-deleted.
Other platforms are unmeasured locally. Publication requires complete release CI.
