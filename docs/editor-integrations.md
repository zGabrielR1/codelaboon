# Official engine editor integrations

RC17 adds a small Codelaboon VS Code connector for the official Claude Code
extension. It uses the supported `claudeCode.claudeProcessWrapper` hook; the
extension's own bundled native executable and editor session protocol remain in
use. This retains native editor context, permission prompts, diffs, tools, model
selection and sessions while routing inference to Codelaboon's backend.

```bash
codelaboon ide install
```

VS Code and Python are reused. The command installs a tiny local VSIX, registers
a private wrapper path, and ensures the official Claude extension dependency is
available. Open VS Code and use **Codelaboon: Open Claude Code** or **Connect
Claude Code**. The explicitly installed connector connects once on activation.
**Check Free Models** streams health-check progress in the Codelaboon output panel.
The release also supplies a portable `codelaboon-vscode.vsix`; run `ide install`
to register local wrapper paths after installing it manually.

Each Claude process gets an on-demand, token-protected loopback gateway. Provider
keys stay in Python. No backend token or upstream key is written to editor
settings or VSIX assets. Native Claude aliases map to `free (Auto)`; selected
Codelaboon model IDs pass through. The extension's stdin/stdout SDK, tool and IDE
arguments are preserved. The normal isolated `claude-code` profile is shared with
the Codelaboon Claude engine, so sessions remain in its native architecture.

The connector uses VS Code's settings API rather than rewriting JSONC files.
It changes only its owned wrapper/login preferences and selected environment
entries. It preserves unrelated settings and never stores API secrets in its
restoration record. **Disconnect Claude Code** restores owned prior values while
preserving subsequent unrelated edits, and stays disconnected across restarts.
New sessions use the selected backend; finish existing sessions before switching.
Native tool approvals remain in the official extension.

OpenCode remains the default terminal UI. **Open Coding Terminal (OpenCode)**
opens it directly inside VS Code. **Open Optional Engine Terminal** can open OMP,
Kilo, Claude, Crush or Jcode with their own native interfaces and the same backend.
These use a direct executable/argument launch, not interpolated shell commands.
The dedicated native editor connector in this release is for Claude Code; other
engines retain their own integration mechanisms.
Cloud services tied to an upstream account remain governed by that upstream.
For SSH/remote extension hosts, install/register the backend on the host where the
Claude process runs. Windows uses the installed Python console launcher; POSIX
uses a small executable wrapper, with no additional bundled runtime.

Verification covers the official editor's bundled Claude binary, SDK JSON stream,
a real file-tool round trip, connector settings restoration, and a real isolated
VS Code host that submits a webview prompt and renders the Codelaboon response.
The test instance does not change the user's profile/settings.

Reference: [official Claude Code VS Code documentation](https://code.claude.com/docs/en/vs-code).
