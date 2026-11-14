# RC15 adversarial review — 2026-11-14

Scope: preserve the working OpenCode UI while reducing backed-up source size,
modularizing engine installation, and adding bounded lightweight native swarms.

Resolved findings:

- Ignoring generated folders in Git does not remove them from whole-directory
  backups. Relocate specific untracked paths, including source trees and local
  weights, outside `ppp`. Do not delete unique source edits or legacy task history.
- Moving active state can corrupt it. Require an idle stopped service, reject
  active Linux source processes and pre-existing destinations, journal moves,
  update local-model paths, and re-register the preserved service configuration.
- Removing source archives from wheels needs a cold-install path. Package pinned
  asset metadata, stream downloads, verify hashes, atomically publish cached
  archives, and use explicit local assets for pre-publication CI. Separate engine
  assets are staged and hashed in the release workflow.
- Development import/export must follow relocated trees. Use one external
  development root throughout; source bundles retain upstream provenance/licenses.
- An empty queue previously kept a large router model loaded. Determine demand
  from durable tasks/inbox/completion state, unload only the owned server, and
  preserve external server ownership. Service remains available while idle.
- Prompt-only concurrency is insufficient. Set the native concurrency guard and
  prove it rejects a third worker while two native workers are live.
- A scripted fixture initially finished coordinator todos before asynchronous
  workers reported completion, and unbounded diagnostics consumed excessive RAM.
  Wait for actual reports, cap fixture requests, isolate test data and keep logs
  concise. Corrected test verifies real child file tools and completion reports.
- Killing only a Python wrapper can leave a separately grouped native child.
  Signal wrappers before forced group cleanup; native execution handles signals,
  timeout and cancellation with bounded termination and handler restoration.
- Successful model text is not implementation acceptance. The durable supervisor
  retains independent checks; swarm checks share the remaining budget and record
  failure, timeout or explicitly unrequested acceptance in durable result files.
- Upstream RAM ratios describe additional sessions of specific versions. Report
  measured local checkout/core/idle service sizes and avoid inherited multipliers
  or untested thousand-session promises.

Evidence: 208 passing Python regression tests, real Rust file tool,
native two-worker completion plus excess-worker rejection, actual installed
OpenCode VTE home/reply/Up recall, real OpenCode file-tool roundtrip, verified
thin wheel/source artifacts and unchanged source-bundle provenance. Local paths
were preserved in two external move journals, and the empty service restarted.

Limitations: Fedora execution measured locally; other platforms rely on existing
CI/platform support. Agent quality depends on model/provider and meaningful
acceptance commands. Native Jcode UI is optional; OpenCode remains the default.
Final publication remains conditional on all release CI gates.
