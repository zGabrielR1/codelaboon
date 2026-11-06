# Latest build: 1.0.0rc6

Fixes the TUI model picker and adds Qoder (free plan) account sign-in on
top of RC5's Freebuff lane.

- TUI: `ctrl+m` could never open the model picker — in terminals Ctrl+M
  is carriage return, byte-identical to Enter, so it was always consumed
  as a message submit. The picker now lives on `ctrl+o` and is unified
  across providers: one list spans every connected provider, picking a
  model from another provider switches the provider too, and
  unconnected account providers show a Connect row.
- `codelaboon login chatgpt|claude|gemini|freebuff|qoder`, TUI login
  dialog and web action menu cover all five account providers.
- Qoder uses the official browser device flow (PKCE, token polled from
  the OpenAPI host, automatic refresh) against a free-plan-capable
  account. Chat runs through the installed `qodercli` binary in
  tool-free print mode, because Qoder's inference gateway only accepts
  requests signed by the official client; a Personal Access Token is
  forwarded to the binary via `QODER_PERSONAL_ACCESS_TOKEN`. Model
  discovery is live from `qodercli --list-models` when present, with
  the documented tiers as the offline fallback. Free-plan data policy
  applies; use it for throwaway work, not secrets.
- Offline tests pass. Live Qoder authorization and inference remain
  unverified without a real account and the `qodercli` binary.
- Published as tag `v1.0.0-rc.6`; the tag-triggered release workflow tests,
  builds the wheel/source archive, writes SHA256SUMS and publishes a GitHub
  prerelease with downloadable artifacts.
