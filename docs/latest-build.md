# Latest build: 1.0.0rc4

Adds Claude (claude.ai plan) and Gemini (Google free tier) account sign-in on
top of the RC3 visual rework and RC2 session/recovery improvements.

- `codelaboon login chatgpt|claude|gemini`, TUI login dialog and web action
  menu cover all three account providers.
- Gemini's Google-account lane onboards to the free Code Assist tier with no
  billing account or API key; free-tier data policy is documented. It uses a
  user-supplied Desktop OAuth client stored privately (`configure gemini`), so
  no OAuth client credentials are embedded in the repository.
- Claude uses Anthropic's public Claude Code OAuth PKCE flow for Pro/Max/Ultra/
  Team/Enterprise plans; free accounts can connect but get no inference until
  Anthropic grants it.
- 86 offline tests pass. Live account authorization and inference remain
  unverified without real accounts.
- Published as tag `v1.0.0-rc.4`; the tag-triggered release workflow tests,
  builds the wheel/source archive, writes SHA256SUMS and publishes a GitHub
  prerelease with downloadable artifacts.
