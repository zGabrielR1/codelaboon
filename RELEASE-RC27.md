# RC27: Vercel AI Gateway and free Auto models

Package `1.0.0rc27`; VS Code connector `1.0.27`.

Connect Vercel with `codelaboon configure vercel`, the terminal key dialog, or
the web provider form. `AI_GATEWAY_API_KEY` is also supported. Live discovery
returns Vercel's vendor/model IDs; explicit selections use `vercel/vendor/model`.
Chat, native Messages and Responses use Vercel's supported endpoints. Native
Messages preserve tool schemas, thinking and cache-control blocks.

Free Auto now includes the separate `vercel_free` lane. It reuses the configured
Vercel key only when endpoints match, or uses `AI_GATEWAY_API_KEY`. Only live text
models with explicitly zero input, output and any additional listed prices are
eligible. Variable-provider prices, unknown/malformed prices, paid models,
non-text models and offline/configured fallback IDs cannot establish eligibility.
Upstream model fallbacks and request-scoped BYOK are rejected on the free lane.
Pricing is cached for at most 60 seconds and checked before inference; failed
refreshes clear eligibility. Monthly account credits do not make paid models free.

The public catalogue checked during preparation advertised uniformly zero prices
for Ampersand v0.1, Nemotron 3.5 Lightning Free, Flint, Beam Free and Glyph Cluster.
This is a snapshot, not a pinned roster: models leave Auto when their live pricing
changes. The variable-price Beam route is excluded. Free model provider data
policies and availability still apply.

Use `codelaboon models list vercel_free` to inspect the lane and
`codelaboon models check vercel_free` for the normal authenticated health checks.
The unrestricted `vercel` lane stays available for explicit paid model selection.

Desktop follow-up: query-bearing model discovery now supports Anthropic
pagination and model timestamps. Proxy startup uses the bounded background
catalogue path. `codelaboon proxy --desktop-models --model vercel_free/VENDOR/MODEL`
prints an explicit Desktop model list; Desktop discovery otherwise filters out
non-Claude IDs. This command does not launch or configure Desktop.

Claude Desktop UI/live acceptance remains pending: the earlier Windows helper
could not connect, and this session could not read the installed app's config or
logs. Protocol tests do not establish installed Desktop compatibility. No owner
credentials or paid model inference were used during release preparation.

Validation: 405 offline tests pass (3 platform skips); 16 Vercel/free/discovery
tests pass against the built wheel. Structural, source provenance and thin-core
packaging checks pass. Wheel, source archive, VSIX, engine sources and SHA256SUMS
are prepared for publication.
