# Codelaboon for VS Code

Connect the official Claude Code extension to Codelaboon's verified free-model
backend, using its supported process-wrapper setting. Native editor context,
permission prompts, diffs and sessions remain in the official extension.

Install with `codelaboon ide install`. Run **Codelaboon: Open Claude Code** or
**Connect Claude Code** from the command palette. **Check Free Models** runs
real reply/tool checks and updates the backend catalog.

The backend runs only while a Claude process needs it. Provider credentials stay
in Codelaboon; editor settings contain no gateway token or upstream API keys.
The wrapper keeps a private Claude profile, preserves IDE protocol arguments,
and maps built-in Claude aliases to free (Auto). Model availability and tool
support depend on successful live health checks.

**Disconnect Claude Code** restores only settings owned by this integration,
while preserving unrelated preferences and environment variables. Existing
sessions must finish/restart to use a different backend.

For Codex, run `codelaboon ide install --engine codex` and select
**Codelaboon: Open Codex**. Reload the window after changing its CLI connection.
The official Codex extension retains its native app-server, tools and approval
UI. **Disconnect Codex** restores the previous CLI setting. The upstream CLI
override is marked development-only. Codex sessions/config remain isolated in
Codelaboon's profile; no ChatGPT account files are copied.

Open the Codelaboon activity-bar icon for **Sessions**. Its Import/Export buttons
support OpenCode, Codex, Kilo, Claude, OMP, Jcode and Crush. Convert Between Agents
performs a one-time native conversion without library registration. Click a shared
session to continue it with another engine. Native resume instructions appear in
the Codelaboon Sessions output panel. Reload VS Code after updating the connector.
