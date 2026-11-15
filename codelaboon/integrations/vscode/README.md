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
