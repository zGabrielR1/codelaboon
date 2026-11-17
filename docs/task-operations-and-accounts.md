# Task operations and account sources

These RC25 features build on public RC24's task conversations, checkpoint
model/prompt settings and Git Changes view. Upgrading does not change existing
tasks or start them; older running workers need a graceful restart before using
the new controls.

## Task conversations and execution controls

The browser task view adds state filters, timestamps and clearer human/worker
messages. Drafts survive reloads within the browser tab. Ctrl/Cmd+Enter sends a
message; Up on an empty composer recalls the last sent message. Delivery receipts
still distinguish saved notes, guidance waiting for a checkpoint, and guidance
already included in an attempt. Background polling cannot overwrite a newer
conversation response.

**Attempts** lists the latest 50 attempts, their stage, engine, result and exit
code. Select an attempt to inspect its bounded, redacted captured output, or
switch back to following the latest attempt. A historical log must belong to the
selected task; guessed paths, other tasks and paths outside the runtime are
rejected. The output is rendered as text, never executable HTML.

**Retry failed** requests a new attempt for an ordinary continuous task after a
finished failure. It does not duplicate running work, revive a stopped/completed
task, change verification, or reapprove an elevated snapshot. The request clears
that task's cooldown/due time at the next supervisor checkpoint. Other tasks'
cooldowns remain unchanged. Paused tasks must first be resumed. Older workers
without the feature refuse retries; restart safely after upgrading.

Worker **Start / Pause scheduling / Resume** controls operate on the existing
worker configuration. Starting or resuming requires confirmation because all ready
queued tasks can run. Pausing scheduling lets current work finish. Task permissions,
scope and acceptance commands are unchanged. Nothing runs just by opening a view.

CLI and terminal controls share the same backend:

```bash
codelaboon tasks TASK_ID --attempts
codelaboon tasks TASK_ID --retry
codelaboon tasks TASK_ID
```

The terminal task view also offers **Retry failed**. The nested portable-engine
runner now retains the already selected per-task execution environment; it no
longer accidentally clears the task's full/profile policy between wrappers.

## HowToFix

Use **Workspace actions → Configure API key → HowToFix** in the browser, or:

```bash
codelaboon configure howtofix
codelaboon models list howtofix
```

The terminal key prompt is hidden. `HOWTOFIX_API_KEY` and `HTF_API_KEY` are also
accepted. Keys are saved only by the local backend; responses and browser storage
do not receive a copy. The default endpoint is `https://api.howtofix.id/v1`.
Discovery reads authenticated `/models`, deduplicates the returned IDs and honors
an explicitly empty catalogue. No guessed `gpt-4o-mini` fallback is installed.
Chat and native-engine tool/stream requests use OpenAI-compatible completions.

The public model endpoint returned **401 without a key** during development.
Connect your own key to inspect your account's actual catalogue and test access.
No account inference was sent or billed during development.

[HowToFix's documentation](https://howtofix.id/docs) describes account credits and
model-dependent billing. Its catalogue is not a zero-cost promise, so HowToFix is
an explicit provider rather than a silent addition to free Auto. Standard/free
credit availability, Pro access and remaining quota are determined by the service.
The live catalogue follows changes and does not resurrect withdrawn IDs from a
hardcoded list. Model visibility alone is not proof that inference/tool use works.

## GitHub Copilot

```bash
codelaboon login copilot
codelaboon models list copilot
```

The browser also offers **Continue with GitHub Copilot**; it displays GitHub's
device authorization URL and one-time code. The optional Textual provider picker
supports the same account connection. An explicit `COPILOT_GITHUB_TOKEN` or
configured provider token can be used instead.

Device OAuth follows the public GitHub.com flow and the protocol of the bundled
OpenCode Copilot plugin (`packages/opencode/src/plugin/copilot.ts` in the verified
source archive). Its default registered OAuth client is the upstream OpenCode app;
the authorization screen identifies that app. Set `CODELABOON_COPILOT_CLIENT_ID`
for a separately registered device-flow client. Tokens are saved in the private
Codelaboon configuration directory, not imported from `gh` automatically.

The provider uses only `https://api.githubcopilot.com`, obtains account model IDs
from its catalogue, and omits explicitly disabled or Responses-only models from
the chat-compatible list. Native gateway requests preserve tools and use the
user/agent initiator headers. All existing Codelaboon engines can select
`copilot/MODEL` after connection. Account entitlement, supported models and quotas
still apply. Copilot is not silently mixed into free Auto.

OAuth mechanics, token privacy and gateway requests were tested with fixtures;
a live user login and entitled inference need the account owner's authorization.
See [GitHub's account authentication guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli).

## Windsurf / Devin

Windsurf/Devin is integrated through its official native CLI account, model list
and task engine. It is not represented as an invented OpenAI-compatible model
endpoint. Native account credentials stay under the native CLI's control.

```bash
codelaboon accounts devin setup
codelaboon login windsurf
codelaboon accounts windsurf status
codelaboon accounts windsurf models
codelaboon accounts devin open
```

Setup downloads the official public release selected by its checksum manifest,
verifies SHA256 before executing the version check, and stores the optional native
runtime outside the project. Login/open/explicit native task execution install
lazily when needed; catalogue/status inspection never installs it. A compatible
existing `devin` command or explicit `CODELABOON_DEVIN_BIN` is supported.
No upstream shell installer, privileged system configuration or application-file
patch is executed by this installer. Windows uses the official ZIP bundle;
Linux/macOS use the official tar bundle.

Queue a task with the **devin** engine and `devin/account-default`, or a native
`devin/MODEL` returned by the account model list. It runs as one coordinator using
the same task scope, checkpoint settings, review and independent checks. Account
model names are checked before queueing or saving settings. Ordinary permissions
keep native behavior; an explicitly full task passes the documented dangerous
permission mode. Default workspace-trust restrictions remain native. Native
progress is forwarded to task output, and owned subprocesses are cleaned up on
interruption. Native-account usage can consume plan quota or paid usage; it is
separate from Codelaboon free Auto and requires a worker supporting this connector.

This does not add a Devin transcript import/export adapter to the existing seven
session formats, nor does it expose SWE models as raw inference to another engine.

The official references are [Devin CLI commands](https://docs.devin.ai/cli/reference/commands)
and [model availability](https://docs.devin.ai/cli/models). Native command routing,
permissions, checksum validation and malformed/foreign manifest rejection are
fixture-tested. Actual browser sign-in and inference were not performed without
user credentials. Free promotions can expire; use the native account's current
model list and pricing rather than a permanently free model claim.
