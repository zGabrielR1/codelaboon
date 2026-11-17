# Codelaboon 1.0.0rc23 - Task conversations and recovery

RC23 makes continuous tasks accessible as live conversations in the browser and terminal, and includes the previously unpublished RC22 recovery work.

- Clicking a task opens its own chat route. Reload, direct links and browser history work; the composer stays visible on desktop and mobile.
- Watch orchestrator updates and live captured output; send checkpoint guidance, save notes, pause or resume. Queued and included receipts do not imply a successful model response.
- Bare engine launches offer Task conversations. `codelaboon tasks`, `codelaboon ENGINE --tasks [ID]` and `codelaboon tasks --open` share the same queue. `--direct` skips the launcher.
- Installed Jcode uses its native worker pool. OpenCode, OMP, Kilo, Claude, Codex and Crush support one portable coordinator per cycle with independent checks.
- The updater validates existing source runtimes, repairs corrupt/NUL dependency manifests with a fresh cache and Windows copyfile installs, verifies startup imports and records maintenance receipts. Missing engines remain lazy.

## Use it

```powershell
codelaboon update
codelaboon tasks
codelaboon tasks --open
codelaboon opencode --tasks
```

For an installed older release whose updater cannot fetch wheels yet, install the wheel attached to this release with the Python interpreter used by your codelaboon installation. Source installs can pull main and run `codelaboon update --no-pull`.

Terminal task chats use the optional `tui` extra; a base install falls back to the browser. Old running workers remain note-only until safely restarted. No active user task is automatically restarted or altered. Guidance joins the next attempt rather than interrupting current work. Approved administrator/root cases remain immutable and accept notes only; full agent permissions do not create OS elevation.

See [task chat usage](https://github.com/zGabrielR1/codelaboon/blob/main/docs/rc23-task-conversations.md), [continuous security setup](https://github.com/zGabrielR1/codelaboon/blob/main/docs/continuous-security-swarms.md) and [recovery details](https://github.com/zGabrielR1/codelaboon/blob/main/docs/rc22-updater-and-terminal.md).

The release workflow gates publication on offline tests, portable contracts, a real Chromium task-chat regression, source integrity and native engine smoke tests. Download artifacts with SHA256SUMS for integrity verification.
