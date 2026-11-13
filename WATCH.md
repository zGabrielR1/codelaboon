# Persistent runner

For a local routing model with all planning/building delegated to cloud workers,
see [CLOUD-WATCH.md](CLOUD-WATCH.md) and `examples/watch-cloud.json`.

This supervisor launches configured commands, rotates tasks/projects and harnesses,
records logs, and resumes completed task IDs after restart. It cannot supply free
hosted quota or keep a ChatGPT conversation alive. Local inference avoids hosted
token quotas but uses your hardware and electricity. Provider limits still apply.

## Start on Windows

Install Ollama separately and download a model that fits your RAM/VRAM. Run
`ollama list`, then replace `REPLACE_WITH_INSTALLED_MODEL` in `examples/watch.json`
with its exact name. The example only generates text, saved in output.log; it
does not read the project or edit code. Prompts must include necessary context.

From the codelaboon directory:

```powershell
python -m codelaboon.watch examples/watch.json --once
python -m codelaboon.watch examples/watch.json
```

Use `--once` to verify one attempt before leaving the runner unattended.
Ctrl+C stops the runner and its active child process tree. Creating `.watch/STOP`
stops it after the current attempt. Remove that file before restarting.
The OS lock prevents two supervisors using the same runtime directory.

## Other harnesses and providers

Add harness objects to the array. `argv` is a list of arguments, with no shell
interpretation. Placeholders: `{python}`, `{source}`, `{project}`, `{prompt}`,
`{prompt_file}`. Escape literal braces as `{{` and `}}`. Commands run in the
task's project directory. Use full executable paths if absent from PATH.

For a codelaboon provider completion, use this argv:

```json
["{python}", "{source}/codelaboon/cli.py", "chat", "gemini", "YOUR_MODEL_ID", "{prompt}"]
```

Configure and authenticate that provider normally first. Adding it is an explicit
choice to use its allowance and data policy. A free label does not guarantee quota.
For an installed coding agent, substitute its documented noninteractive command
and keep its normal permission controls. The scheduler grants no extra access.
Only commands with exit status zero mark a task complete; this is process success,
not proof that a coding task meets its acceptance criteria. Include verification
in your harness command. Use wrapper scripts for multi-step commands or stdin.

On failure or timeout the harness rests for `cooldown_seconds` (default one hour),
and other eligible harnesses can run. This conservative cooldown applies to all
failures; it does not parse provider reset headers. No account cycling or quota
bypass is implemented. When all providers are unavailable the runner waits.

Project paths resolve relative to the config file. Completed tasks run once.
Give new work new task IDs; restart the runner after editing its configuration.
It stays idle when the queue is complete. It does not invent new objectives.
The sample second project path is the projects directory; replace it with a
specific project and task when ready.

## Persistence and Windows startup

`.watch/state.json` stores completed IDs and cooldowns. Each attempt has a UUID
directory with prompt.txt, output.log and result.json. Keep these private; prompts
and child output may contain sensitive data. Logs are not automatically pruned.
An interrupted attempt can be rerun after restart: execution is at least once,
so task commands should be safe to retry. Avoid automatic deployment/publishing
unless those actions are intentionally part of the configured task.

For reboot recovery, create a Windows Task Scheduler task at logon with:

- Program: the absolute path printed by `python -c "import sys; print(sys.executable)"`
- Arguments: `-m codelaboon.watch examples/watch.json`
- Start in: the absolute codelaboon directory
- Restart on failure; do not start a second instance; disable its execution time limit.

Ensure the model service starts too. Review Windows sleep settings: the process
cannot work during sleep, power loss or an OS restart. A supervisor can restart
failed workers; no program can guarantee uninterrupted execution.
