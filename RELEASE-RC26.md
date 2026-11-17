# RC26: terminal task creation and desktop proxy

Pre-release. Package `1.0.0rc26`; connector `1.0.26`.

Create a background task without leaving the terminal: run `codelaboon tasks`,
click New task or press Ctrl+N, enter the objective, project, scope and independent
verification commands, choose an installed engine and queue. The default is one
verified cycle with the coding profile, default permissions and no elevation.
Validation errors preserve input. Submission cannot be repeated or cancelled
while queue publication is in progress. A queued task opens as a conversation;
worker startup failure is reported without prompting another enqueue.

Run `codelaboon proxy --model free` to serve desktop and editor clients through
the existing wire adapters. The listener stays on 127.0.0.1:8766, with a persistent
local key in the config directory's `proxy.token`. Use `--show-token` when entering
the key into a client; the server does not print it during normal startup.
`--port`, `--token-file` and `--model PROVIDER/MODEL` select another instance or
Claude built-in model destination. Existing per-launch editor gateways keep
ephemeral ports and credentials.

Claude Desktop setup and feature limits are in the [README](https://github.com/zGabrielR1/codelaboon/blob/v1.0.0-rc.26/README.md#coming-in-rc26),
based on Anthropic's official third-party inference documentation. Use the app's
Gateway form, a root base URL without `/v1`, and Bearer or x-api-key authentication.
Do not expect shell environment variables or Claude Code settings to configure
Desktop. Non-Claude routes are experimental compatibility routes; translated
requests do not preserve Anthropic prompt caching and token counts are estimates.

Validation:

- Full offline Python suite: 389 tests pass (three platform-dependent skips).
- Seven new regression tests: terminal creation and recovery, missing engine,
  in-flight submission guard, stable credential, HTTP auth/discovery/stream/token
  count, model alias boundaries and selected backend round trip.
- Structural checks and VS Code connector settings/restoration test: pass.
- Core wheel, source archive and VSIX build locally; thin-core checks pass.
- No user account inference was performed.

Desktop acceptance remains open: Windows Computer Use returned “native pipe is
unavailable” on both app and window discovery. The installed Desktop UI, provider
inference, and Chat/Cowork/Code feature compatibility have not been verified.
Before publishing as Desktop-ready, configure the installed app, send a small
test message, exercise a tool round trip, then restart the proxy and confirm the
saved credential still works. The local gateway must remain running.
