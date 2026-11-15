# RC17 adversarial review — 2026-11-15

Scope: stop advertising broken/retired free models, expand real free discovery,
and connect official Claude editor resources to Codelaboon without duplicating UI.

Resolved findings:

- Static capability hints were treated as discovery, even when a provider omitted
  those IDs. Build candidates from actual/cached provider rosters; hints only rank.
  Distinguish authoritative empty catalogs from transport/malformed-data failures.
- An HTTP200/catalog entry does not prove inference or coding tools. Check real
  nonce replies, valid function arguments and an unpredictable tool-result receipt.
  Detect JSON/SSE error envelopes, bounds and partial function arguments.
- A model-level404 should not disable healthy siblings. Track scoped per-model
  health, prefer verified coding routes, and retain provider backoff for shared
  failures. Record direct-route/admission failures too. Never turn a good response
  into a failed turn merely because a diagnostic cache write failed.
- Quota failures are not retirement. Honor Retry-After, defer remaining probes,
  and rotate unchecked/oldest models so one limited ID cannot starve discovery.
  Background verification has a small per-minute budget; explicit checks stream
  progress/results. Monitoring can fail when no route passes without making code
  releases depend on public-provider uptime.
- Cache state must not cross endpoints/credentials. Scope it privately, store no
  credentials/raw errors, use atomic writes and OS locks, tolerate malformed data,
  and memoize unchanged reads rather than reread JSON for every candidate.
- Free credentials are not necessarily a zero-cost API route. Exclude paid Gemini
  API-key/Qoder PAT modes. Restrict OpenRouter IDs/prices and zero-price routing.
  Z.AI candidates require current official all-Free pricing plus successful probes.
  LLM7's current catalog had no zero-priced rows and was not added as free.
- Editor integration needs the actual extension protocol. Inspect the installed
  official wrapper contract: bundled executable first, then native SDK arguments.
  Keep native stdio, editor context, tools and permission flags; map Claude aliases
  to free. Spawn/own its process and gateway, with private onboarding preferences.
- Do not put upstream keys or a stale daemon token in editor settings. Each native
  process gets an on-demand loopback gateway; only wrapper/profile paths are stored.
  The tiny connector uses the official settings API, not JSONC rewriting, backs up
  only owned values, preserves unrelated secrets/preferences and restores on demand.
  Serialize startup/manual connection operations; disconnect remains disconnected.
- Project Claude settings can override inherited backend environment. Supply
  gateway settings at CLI priority in a temporary 0600 file, remove it on exit,
  and test a conflicting project API URL/key with native file tools.
- POSIX wrappers must quote interpreter paths; Windows uses installed console EXE
  launchers. Native terminals use executable/argument arrays, not shell interpolation.
- Native fixtures must stay isolated from real credentials/checks, and catalog
  fixtures must actually mark their Kilo models free. Propagate clean fixture env.
- Test the real editor UI: an initial prompt is only prefilled. An isolated VS Code
  host plus its own loopback debugger submits the actual webview input and verifies
  the rendered response. Do not point fixture hosts at the user's extension store.

Evidence: full Python/Node regression gates; real HTTP health checks admit a
working model and remove it after a failed recheck; native SDK/file Read; actual
VS Code prompt/reply; native Claude/Jcode UI and OpenCode tools. Live public checks
verified Kilo Auto and Nemotron SuperVL, including fresh tool receipts. Other
models/accounts are explicitly failed/deferred/skipped, not claimed healthy.

Local gates pass: 249 Python tests, Node connector contract, thin wheel/source
verification, installed OpenCode VTE rendering and real editor UI. Connector
installed locally. Complete native CI remains a publication gate. No new
runtime dependency, bundled editor runtime or upstream UI fork was introduced.

Limitations: verification is time-bounded evidence, not permanent availability.
Native pickers use launch snapshots; reopen after checking. Only the Claude
extension gets the dedicated editor connector in this release; other engines can
use integrated native terminals. Upstream cloud/account-only features remain
upstream. Other OS execution is not locally measured. No user objective is started.

CI follow-up review: the clean runner displayed the pinned Jcode native welcome
chooser, while the model-screen assertion assumed a completed first run. Verified
upstream v0.99.1 navigation: any non-Enter key rotates its two choices. The smoke
now selects the fixture-project new session once, then retains all reply, durable
resume and owned-server cleanup assertions. Local native checks pass. No product
behavior or user onboarding settings are changed. RC17 was not published.
