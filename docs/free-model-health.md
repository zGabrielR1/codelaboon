# Verified free models

A catalog entry is not evidence that inference still works. RC17 separates live
model discovery, real chat checks, and actual tool-call/result round trips.

```bash
codelaboon models check free
codelaboon models check kilo --force --timeout 15
codelaboon models check free --json
codelaboon models check free --jsonl --require-working
codelaboon models list free
```

Checks use small synthetic nonces, never your source files or conversation.
They send real requests and consume free quota. Providers run in parallel with
at most four provider workers, while requests to each provider remain serial.
Checks stop a provider sweep on rate limits/authentication failures, defer the
remaining IDs, and prioritize unchecked/oldest records on later sweeps. A limit
is not evidence that a model was retired. JSONL writes incremental safe records;
normal output streams progress. `--chat-only` skips coding-tool verification.

Native coding pickers show only models with a recent successful reply and tool
round trip. A tool call must have valid arguments, and its follow-up must repeat
an unpredictable receipt from the tool result. A basic HTTP200 is insufficient.
Text-only lists can show verified chat models; tool-only failures do not establish
coding support. The synthetic `free (Auto)` route remains available to bootstrap
new setups and fails over across eligible real provider IDs.

Health is cached privately for four hours, scoped by provider endpoint and
credentials/account context. Credentials and raw upstream errors are never stored
in the health report. Missing model IDs are quarantined longer; transient errors,
rate limits and authentication failures have retry windows. New credentials or
endpoints do not inherit another account's failures. Cache writes are atomic and
serialized across processes; malformed cache data cannot become model discovery.

A successful empty live catalog is authoritative. Discovery failure is distinct
from an empty catalog and may use a last-known/configured roster for checking.
Historical capability hints never invent routable model IDs or resurrect models
that the live catalog removed. Native runtime failures quarantine individual
models; an unavailable model does not automatically disable its healthy siblings.

Discovery runs within the existing UI startup budget. Background verification
checks at most two models initially, then one per minute per provider; catalogs
refresh every five minutes. Fresh health is reused. This avoids spending the free
quota on a full scan every time the editor opens. `models check free` explicitly
checks all available free lanes. Reopen an engine after a check to refresh its
native model-picker snapshot. Live failures can still occur after verification;
Auto's runtime failover and later checks handle them.

## Provider coverage and expansion

- Kilo: discover the current `isFree` catalog, including new IDs absent from the
  old two-router fallback. Only successful checked models enter verified pickers.
- OpenRouter free: reuse an explicitly configured official OpenRouter key, or
  `OPENROUTER_API_KEY`; reject nonzero prices and constrain requests to zero-priced
  providers. Paid model IDs never enter this lane.
- Z.AI free: `ZAI_API_KEY` or `configure zai_free`; the documented zero-priced GLM IDs are candidates (currently three Flash
  models). The official pricing page must still report every price
  column Free. A price-page error fails closed. Successful inference is required
  before advertising a model. Paid FlashX/GLM5 IDs are excluded.
- Our Free Model, Pollinations, Freebuff, free Gemini Code Assist OAuth and free
  Qoder sessions are checked when usable. Unconfigured accounts are reported as
  skipped, not silently claimed healthy. Gemini API keys and Qoder Cloud PATs are
  excluded from free inference checks because they can use paid resources.
- Groq/Cerebras and other generic API-key providers remain available separately;
  a working API key alone does not prove that its account is on a free billing tier.

Sources: [Kilo model catalog](https://kilo.ai/docs/gateway/models-and-providers),
[OpenRouter free models](https://openrouter.ai/collections/free-models),
[Z.AI pricing](https://docs.z.ai/guides/overview/pricing).

LLM7 was inspected but its current catalog contained no explicitly zero-priced
models, so it was not advertised as free. Free status and availability are measured,
not inferred from old third-party lists.

The daily `free-model-health` GitHub workflow tests public free routes and uploads
a JSONL report. `--require-working` returns nonzero when no checked coding route
passes, so a public-pool outage is visible in that monitoring job. Signed-in account lanes are skipped without their credentials.
CI reports are diagnostic; availability from a different account/network is not
silently installed as your local health state. Code releases use deterministic
fixtures rather than treating a public provider outage as a code regression.
