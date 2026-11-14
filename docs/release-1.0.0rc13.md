# RC13 — Claude Code on Codelaboon free providers

`codelaboon claude` starts the official, unmodified Claude Code client on
Codelaboon `free (Auto)` without a Claude subscription or Anthropic login. The
wrapper prepares an isolated profile and local onboarding preferences, configures
the loopback gateway, and supplies a free-only native `/model` picker. Personal
Claude OAuth/API credentials are not reused by this route. Project trust and
native tool permissions remain active.

A lightweight Messages adapter preserves text/images, client tool schemas,
parallel tool calls/results, streamed text, completion/error markers and usage
when routing to OpenAI-compatible free providers. Provider credentials stay in
the backend; the client receives only a private per-launch loopback token. Free
provider failures retain the existing free-pool failover. There is no automatic
fallback to paid Claude models. OpenCode remains the default engine; its RC12
worker-readiness/VTE fix and the working OMP/Kilo integrations are retained.

Validation: 191 Python tests; official Claude Code file-read/result loop and native
UI/model-picker checks with no Anthropic account; a live free-provider reply from
an empty temporary project. CI gates the release on the new Claude checks alongside
the existing OpenCode/OMP/Kilo and actual VTE matrix. No new runtime dependencies.

Limits: inference comes from the chosen free provider and remains subject to its
availability/quotas. Anthropic does not support non-Claude models in its client;
this compatibility adapter is maintained by Codelaboon. Claude account/cloud-only
features and server-executed Anthropic tools are outside this route. Output is
capped at 4096 tokens per request. Token counting is a local size estimate, and
native cost displays for unknown models are client estimates, not Anthropic bills.

Configuration references: [gateway connection](https://code.claude.com/docs/en/llm-gateway-connect),
[model picker](https://code.claude.com/docs/en/settings-reference#modelpicker),
[environment variables](https://code.claude.com/docs/en/env-vars).
