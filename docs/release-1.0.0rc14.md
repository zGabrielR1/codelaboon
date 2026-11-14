# RC14 — Crush as a native Codelaboon engine

Run `codelaboon crush` to open the official Crush v0.101.0 native interface on
Codelaboon `free (Auto)`. Setup downloads the native archive only when needed,
verifies its published SHA-256 checksum, and keeps upstream license/notices.
No Go, Node or Bun runtime is needed. OpenCode remains the default engine.

The native model picker exposes free/local models. Crush retains its own editor,
commands, themes, tools, project initialization and interactive permissions.
`Ctrl+L` opens models and `Ctrl+P` opens commands/themes. Saved themes and native
project session databases live in a separate Codelaboon Crush profile.

`codelaboon crush run "your prompt"` uses Crush's native client/server path to
avoid v0.101.0 local-mode stdout dropping fast completions. Its private IPC server
is owned by that launch, readiness-checked, and terminated/reaped afterward;
interactive mode stays in-process. There is no persistent Crush daemon. Scripted
permissions follow native Crush semantics; the wrapper adds no yolo flags.

Validation: 200 Python tests; verified native download; real file-tool loops across
two launches with fresh gateway tokens; native UI response, prompt recall, free
model picker, saved themes and session storage; actual Fedora VTE rendering and
reply/history checks; a live free-provider reply. User confirmed the installed
engine opens in Ptyxis. CI now checks Crush UI/tools and VTE in addition to the
existing OpenCode, OMP, Kilo and Claude gates before publication.

The Linux native package measured about 98 MB locally. Windows/macOS archive
mapping is implemented, but native execution on those hosts was not tested here.
Crush keeps its [FSL-1.1-MIT license](https://github.com/charmbracelet/crush/blob/v0.101.0/LICENSE.md);
it is an optional upstream download, not bundled under Codelaboon's own license.
Source reference: `0dcd3d5fc452343d400b9de876d2dc10883f9519`.
