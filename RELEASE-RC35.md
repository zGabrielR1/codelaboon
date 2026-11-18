# RC35 adds desktop tools for Windows and Linux

In the web workspace, choose **Workspace actions → Desktop tools**. Open a
terminal in the workspace, run an executable and see its exit code and output,
or use the browser panel to open pages, read their accessible outline, and
click or fill elements. The Tasks link opens the existing queue and its native
engine controls.

## Install browser and MCP support

```sh
python -m pip install 'codelaboon[desktop] @ https://github.com/zGabrielR1/codelaboon/releases/download/v1.0.0-rc.35/codelaboon-1.0.0rc35-py3-none-any.whl'
python -m playwright install chromium
```

Use a graphical session on the workstation. On Linux, install the browser's
system dependencies with `python -m playwright install-deps chromium` if
needed. The browser opens a separate Chromium window for each web server or
MCP process. Existing logged-in browser tabs stay in your regular browser.
Terminal commands run as the account that started the workspace or engine.

## Use desktop tools from an engine

Set `CODELABOON_DESKTOP_MCP=1` before starting a Codelaboon coding session
with Codex, Claude Code, OpenCode, Kilo, or Crush. Use a model that supports
tool calls. For example:

```powershell
$env:CODELABOON_DESKTOP_MCP = '1'
codelaboon codex
```

```sh
CODELABOON_DESKTOP_MCP=1 codelaboon opencode
```

For Oh My Pi or Jcode, merge the output of
`codelaboon desktop config --engine omp` or
`codelaboon desktop config --engine jcode` into the project's
`.omp/mcp.json` or `.jcode/mcp.json` respectively. Other stdio MCP clients
can launch `codelaboon desktop mcp` from the workspace directory.

The MCP tools can run a command, open a terminal, list and pause or resume
tasks, open a task in a native engine, and control their Chromium session.
