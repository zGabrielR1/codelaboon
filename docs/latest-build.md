# Latest build: 1.0.0rc5

Adds Freebuff (ad-funded free tier) account sign-in on top of RC4's Claude and
Gemini account lanes.

- `codelaboon login chatgpt|claude|gemini|freebuff`, TUI login dialog and web
  action menu cover all four account providers.
- Freebuff uses device-code login — the same flow the Freebuff CLI uses — with
  no subscription, no credits and no API key. Free sessions are admitted per
  model for an hour; limits and withdrawn-model rejections are explained in
  plain language. The provider speaks the compiled catalog by plain wire model
  ids, so no catalog handles or device signing are needed; models that exist
  only in the server-driven catalog are not listed. Free-tier data policy
  applies; use it for throwaway work, not secrets.
- A token from an installed Freebuff CLI, `CODEBUFF_API_KEY` /
  `FREEBUFF_API_KEY`, or an explicit `[freebuff]` token is honored without a
  new browser sign-in.
- 100 offline tests pass. Live account authorization and inference remain
  unverified without real accounts.
- Published as tag `v1.0.0-rc.5`; the tag-triggered release workflow tests,
  builds the wheel/source archive, writes SHA256SUMS and publishes a GitHub
  prerelease with downloadable artifacts.
