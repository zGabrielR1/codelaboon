# RC38 connects desktop control with continuous tasks

Open **Desktop controls** alongside a task to use the browser and workspace
terminal, see connected desktop agents, or pause and resume their desktop
tools. A linked agent entry opens its task.

In the task form, choose a coding engine and an explicit vision-capable model,
then select **Allow desktop control each cycle**. A verified cycle limit of
`0` keeps the job recurring. Every cycle still uses the configured acceptance
checks and desktop permissions.

Interactive desktop MCP agents can list, pause, and resume scheduled tasks.
Desktop-enabled task agents can list and pause or resume other desktop MCP
sessions. Pausing a desktop agent takes effect at its next desktop tool call.
Actions already in progress can finish. Native foreground input still uses
one session at a time.

```sh
python -m pip install 'codelaboon[native-desktop] @ https://github.com/zGabrielR1/codelaboon/releases/download/v1.0.0-rc.38/codelaboon-1.0.0rc38-py3-none-any.whl'
```

Restart existing supervisors and desktop MCP sessions after upgrading.
See [desktop requirements](README.md#foreground-desktop-swarms).
