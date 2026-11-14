# RC13 adversarial review — 2026-11-14

Reviewed the default Claude engine route, Messages conversion, streaming error
semantics, catalogue, native permissions and credential/profile isolation.

Findings resolved before commit:

- Base URL alone cannot adapt Claude's Messages wire format to free Chat APIs.
  Added translation and tested actual Claude Code tool requests/results.
- Native custom model defaults can append [1m]. Normalize the suffix for backend
  routing and declare the gateway context window rather than claiming 1M support.
- Built-in Claude picker entries would be unusable without an Anthropic account.
  Supply a replacing free-only picker and allowlist, with provider IDs as labels.
- Preserve tool IDs, error results and parallel fragmented arguments. Validate
  assembled JSON before emitting executable calls; truncated streams emit errors.
- Do not mix personal Claude credentials or sessions into the free route. Use a
  separate profile and a per-session loopback token; never store it in preferences.
- Machine-readable output must stay valid JSON: route the launch banner to stderr.
- Keep workspace trust and permission prompts. The UI test explicitly trusts only
  its disposable fixture project; product code never bypasses permissions.
- Native cost estimates for unknown models are not provider bills; document that
  limitation. No entitlement flags, client binary edits or paid API access tricks.

Evidence: 191 unit tests (including wire/error/credential regressions), native
Claude Read tool loop, fresh-profile UI and free picker, and a live free-provider
reply. Existing engine behavior is guarded by the complete release CI matrix.
No blocker remains for the tested free-provider route. Publication requires CI.
