# RC14 adversarial review — 2026-11-14

Reviewed native installation, configuration generation, free-model routing,
profile separation, interactive behavior, noninteractive output and lifecycle.

Findings resolved:

- Main-branch docs can differ from a binary release. Inspected the exact
  v0.101.0 source and native release asset naming/checksums.
- An npm wrapper would add a Node dependency or select a different configuration
  version. Reuse matching native executables; otherwise install the pinned binary.
- Native config is executable Bash. Quote model IDs/labels and keep URL/token as
  environment references; temporary configuration is private to each launch.
- Default provider/catalogue refresh could introduce unrelated login/network
  stalls. Configure the gateway explicitly and disable defaults/refresh/metrics.
- Headless local-mode select can finish before stdout consumes final message
  events. Reproduced missing output, then used the native client/server run path.
  A private per-launch IPC endpoint avoids stale gateway credentials. Readiness
  is bounded; termination/reaping is tested on success, failure and failed startup.
- Native theme names and Escape timing differ from other engines. Test actual
  Crush theme selection/persistence and separate terminal actions.
- Noninteractive permissions differ from interactive mode upstream. Document the
  native semantics instead of claiming every mode prompts for permissions.
- Preserve FSL-1.1-MIT attribution and license rather than mislabeling Crush as MIT.

Evidence: 200 unit tests; real file reads/results across two launches; native UI,
model picker, history, theme persistence and project databases; actual Fedora VTE
with the installed package; live free-provider reply and user acceptance. Native
Go source remains unmodified. No new runtime package dependencies.

No blocker remains in the tested Fedora path. Other OS execution is explicitly
unverified. Publication remains conditional on the complete release CI matrix.
