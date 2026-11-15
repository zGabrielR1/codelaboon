# RC18 focused review

User requested Codex as an optional engine, prioritizing the official VS Code
extension, with focused validation and prompt publication.

- Reuse the unchanged native CLI/app-server; add a Responses-to-chat adapter for
  existing free providers. Native exec and an actual shell Read round trip pass.
- Preserve function/custom call IDs and tool results. Emit Responses lifecycle
  events; preserve upstream failure status. Three focused adapter tests pass.
- Keep Codex auth/config/sessions in a Codelaboon-owned profile. Never rewrite the
  user's Codex home or copy its credentials. Per-process token stays in env;
  temporary private model catalogs contain no secret and are removed on exit.
- Enforce provider overrides after SDK args, retaining native permission/sandbox
  flags. Default model remains Auto; catalog uses verified Codelaboon coding rows.
- The official extension's cliExecutable is explicitly development-only. Use that
  hook transparently; retain its native editor protocol. Back up/restore only the
  owned setting. A running app-server needs a fresh/reloaded window after switch.
- An isolated real VS Code extension host submitted a prompt through the wrapper
  and rendered the fixture response. Tested without touching personal editor
  windows or sharing account credentials. Existing 249 regression tests and Node
  connector contract pass; three adapter tests pass. No broad new test campaign.
- Optional native installer uses upstream npm platform aliases and SHA512; no
  Node runtime or editor runtime added to the core. Other engine defaults remain.

Limits: text responses are buffered before Responses event delivery; cloud
account features are not emulated. Other OS execution is not locally measured.
Model/provider availability remains time-bounded. No real user objective queued.
