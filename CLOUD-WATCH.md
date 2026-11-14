# Local orchestration, cloud planning and building

> Current runtime: use `codelaboon work init` and `codelaboon work enable` for
> OS-managed startup (Linux user systemd with lingering, Windows Scheduled Task,
> macOS LaunchAgent). Native builders now use the bundled OpenCode source and
> its provider gateway. See [the current guide](docs/native-runtime.md).
> The dated operational notes below describe the earlier detached-process setup.


The local Qwen3 0.6B model receives only task IDs, project paths, stage names and
available cloud harness IDs. It returns a validated job index. It has no tools
and never gets source code, writes plans or builds the project. A fixed state
machine enforces cloud plan -> cloud build -> acceptance commands. Missing or
invalid local responses pause cloud dispatch; there is no cloud orchestrator or
local coding fallback.

## Installed runtime

`python scripts/setup_orchestrator.py` installs a pinned CPU llama.cpp build
and the official Qwen Q8 model into gitignored `.watch/local`. Downloads are
SHA256 verified (about 665 MB total). It does not install anything globally.
The loopback-only model server uses two CPU threads, a 4096-token context and
port 18765. For a different local runtime, set the orchestrator URL/model and
run `codelaboon.watch` directly rather than the bundled service.

## Start / stop

From the codelaboon checkout:

```powershell
python scripts/setup_orchestrator.py
python -m codelaboon.service examples/watch-cloud.json --background
```

The launcher starts a hidden process. Omit `--background` to run it in the current
terminal. `scripts/start-cloud-watch.ps1` is also available where PowerShell
script execution is enabled. The service restarts a failed local server or supervisor. It requests
that Windows prevent automatic idle sleep while running, leaving display sleep
available. Set `keep_awake` false to disable that request. Manual sleep, logout,
shutdown and OS updates can still interrupt it. This is not a registered Windows
service or startup task and it does not promise survival through logout/reboot.

Graceful stop after the active attempt and its checks:

```powershell
New-Item -ItemType File -Path .watch/cloud/STOP
```

Remove STOP before starting again. A local server reused from an earlier launch
is not owned or stopped by the service. Ctrl+C in foreground mode stops owned
processes immediately; interrupted tasks may run again after restarting.

## Cloud workers

`examples/watch-cloud.json` contains two cloud planners using Codelaboon's Kilo
adapter and two OpenCode coding workers using that gateway's free-model routes.
Both routes share the same gateway and may share quota or underlying models;
they are not independent allowances. No paid fallback is configured. Live free
availability is determined by the gateway. Failures cool the harness down for
one hour; when no eligible cloud worker exists, the runner waits. A model's free
label is not a promise of unlimited access.

OpenCode is discovered from PATH or its Windows npm installation. It runs in
standalone mode with explicit cloud model IDs and workspace-local data/config
paths. The adapter requires a successful final event and nonempty output;
empty/incomplete/failed runs are not accepted. Normal agent permissions remain
in effect; permission requests can prevent unattended completion. No blanket
permission bypass is enabled. The two initial demo projects need file writes.

Cloud plans are saved before building and included in the builder's prompt.
The current completion planners see the task prompt; include required source
context there or configure a cloud planning harness that can read the project.
Cloud OpenCode builders can inspect and edit their task project. Free-tier data
policies apply to any context they send. Do not queue secrets for a public pool.

## Queue and verification

The initial tasks create and test tiny Python modules in `.watch/demo-clamp`
and `.watch/demo-slug`, demonstrating project alternation without choosing
feature work in unrelated repositories. Replace these with specific authorized
project tasks and acceptance commands. Project paths are relative to the config.
Directories must already exist. Each task needs a unique ID, prompt and nonempty
`verify_argv` list of commands (argument arrays, no shell interpretation).

Restart after editing the config; completed task IDs remain complete. To repeat
work, use a new ID. Successful planning alone does not complete a task. Successful
building plus all configured checks does; those checks must express the desired
behavior. The local model does not judge implementation quality. Tasks and
harnesses rotate, subject to stage and cooldown eligibility. The process stays
idle after finishing its queue rather than inventing objectives.

State, cloud plans, prompts, per-attempt logs and checks live under `.watch/cloud`.
`state.json` records completion, cloud plans and cooldowns. `supervisor.log` shows
dispatches; `service.stderr.log` records service errors. `service.pid` and
`supervisor.pid` identify background processes. Logs are private local artifacts
and are not automatically pruned. All execution is at least once: a crash after
editing files but before saving completion can rerun the task.

Runtime sources:
[llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b12360),
[official Qwen model](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF),
[OpenCode automation](https://opencode.ai/docs/cli/commands/).

## Isolated DigiSat recomp test

The session's project-specific queue is `.watch/watch-active.json`. Restart it
with `python -m codelaboon.service .watch/watch-active.json --background`.
`scripts/prepare_decomp_test.py ORIGINAL_PROJECT_ROOT` creates that queue once,
copying only AGENTS.md, the reconstructed-workspace README and build_workspace.py
into `.watch/workspaces/digisat-recomp`. `.watch/baselines/digisat-recomp` retains
the original files for review; snapshot-provenance.json records their hashes.
The original checkout is not modified. Existing snapshots are never overwritten.

The cloud task handles compiler timeout/launch failures while preserving a build
manifest. `scripts/check_decomp_build.py PATH_TO_COPIED_BUILD_WORKSPACE_PY` checks
this independently using mocked subprocesses. It never builds or starts vendor
binaries, reads MongoDB or establishes binary equivalence. Actual recompilation
and reconstruction remain separate work.

## Control it from Codelaboon

From this source checkout, use `python -m codelaboon work` to open the interactive
control menu. If Codelaboon is installed from this checkout in editable mode,
`codelaboon work` is equivalent. Exiting the menu leaves background work running.
The default config is `.watch/watch-active.json` when present, otherwise the cloud
example. Pass `--config PATH` to control a different queue.

```text
codelaboon work
codelaboon work start
codelaboon work status
codelaboon work pause
codelaboon work resume
codelaboon work logs
codelaboon work stop
```

Start is idempotent. Stop and pause take effect after the active attempt and its
checks finish. Resume clears pause; start launches a stopped service. These
commands preserve task progress. Status reports pending tasks, completed count,
active/interrupted attempts, provider cooldowns and log locations. Logs shows the
supervisor/service log tail; detailed attempt logs are linked from status.

Queue a new instruction at any time:

```text
codelaboon work add "Fix the failing offline tests and explain the changes" --project "/path/to/project" --check "python -m unittest discover -s tests"
```

On Windows use a Windows project path. Each `--check` is one command and can be
repeated; `--checks-json` accepts exact argument arrays when quoting is complex.
Checks are required to avoid accepting an agent's claim of success alone. They
must actually test the requested behavior. Queued instructions are saved as
individual atomic files under the runtime inbox. The supervisor reads them on
each polling cycle, without a restart; active work is allowed to finish first.
The new instruction is a new task, not a live message injected into the current
cloud agent. Use pause to prevent another dispatch while deciding the next task.

## Platforms and operational limits

The Python scheduler, inbox, control commands, file locking and detached process
launcher have Windows and POSIX paths. Windows is verified on this machine.
Linux/macOS execution has not been tested here. On those systems install native
`llama-server` and `opencode` executables on PATH, then run the setup script to
download the same verified GGUF model. A full local routing server already
running on port 18765 with model alias `local-router` can also be reused. Set
`local_executable` to an absolute native llama-server path if it is not on PATH.

The Windows setup downloads a Windows CPU binary; it is not used on Linux/macOS.
Windows idle-sleep prevention is implemented; Linux/macOS sleep settings are left
to the operator. This is a detached process, not a systemd/launchd/Windows service;
auto-start after reboot and survival through logout are not configured.
Closing the control menu does not stop background work.

Cross-platform orchestration does not make every project portable. DigiSat's
native Windows/.NET Framework reconstruction and runtime checks still require
their Windows toolchain. Cloud workers can continue other platform-compatible
tasks. Hosted free routes still have limits; if all are unavailable the queue
waits. An empty queue also waits rather than creating new goals.
