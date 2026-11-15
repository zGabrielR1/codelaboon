# Universal sessions and standalone conversion

Codelaboon keeps a shared session library for OpenCode, Kilo, Codex, Claude Code,
OMP, Jcode and Crush. A universal ID identifies the conversation; native engines
receive a projection in their own format. Their UI, tools and resume machinery
remain native. The central library can recreate a destination projection.

## Import and Export buttons

Install/update the connector with `codelaboon ide install`, then reload VS Code.
Open the Codelaboon icon in the activity bar and its **Sessions** view. The view
has **Import**, **Export**, **Convert Between Agents**, and **Refresh** buttons.
Import accepts a native session ID or file and registers a shared session. Export
selects a library conversation, destination engine and new file. Convert reads
an independent source and writes an independent destination without library
registration. Each supports all seven agents. Native continuation instructions
appear in the **Codelaboon Sessions** output panel. Click a session to resume it
in an integrated native engine terminal; its inline Export action is also available.
These are Codelaboon's shared controls; upstream engine interfaces remain native.

## Continue one conversation across engines

```bash
codelaboon sessions list
codelaboon sessions resume UNIVERSAL_ID --engine codex
codelaboon sessions resume UNIVERSAL_ID --engine opencode
codelaboon sessions resume UNIVERSAL_ID --engine kilo
```

Keep using the same universal ID. After closing an engine, its native conversation
is synchronized into the library. `sessions list` also synchronizes running
engines' saved records, which is useful for long-lived editor app-servers.
`codelaboon sessions sync` performs that scan explicitly. Unchanged native files
are skipped. Only Codelaboon-owned profiles are indexed automatically.

For a single headless continuation:

```bash
codelaboon sessions resume UNIVERSAL_ID --engine codex --prompt "Continue the implementation"
```

The native session resumes in its saved project directory; `resume --cwd PATH`
selects a new location after moving a project. A different engine
gets the current conversation rather than an old copy from the last time that
engine ran. Codelaboon binds the resulting native ID back to the universal ID.
The central database lives outside the project checkout at
`~/.local/share/codelaboon/session-library/sessions.sqlite3` (or beneath
`CODELABOON_DATA_DIR`). It stores compressed original records and conversation
content privately. Native runtime databases remain local projections; they are
not bundled into the source checkout or release.

## Import an existing independent agent session

```bash
codelaboon sessions import --engine codex --source 01a1bc57-01bf-7f72-a438-9d31070edc1e
codelaboon sessions import --engine opencode --source ses_e3d2a9631ffeKIubcsF1T0i18e
```

The command prints a universal ID. Source lookup is read-only. `--home PATH`
selects a nonstandard native data directory. `--source PATH` accepts a native
Codex/Claude/OMP JSONL, Jcode JSON or OpenCode/Kilo exported JSON. For a Crush ID,
`--home` points to the project's Crush data directory containing `crush.db`.
Existing authentication files and original sessions are not migrated or changed.

Codex lookup consults its native thread index for active reverted rollouts.
Linked fork prefixes are materialized using their saved byte boundary. OMP and
Claude select the active branch. Compaction summaries and retained context are
carried forward; original records remain archived. Missing linked source files
cause an explicit error rather than an incomplete import.

## Convert once, then use independent native agents

This path does **not** add anything to the Codelaboon library and does not need a
Codelaboon backend when continuing in the destination.

```bash
codelaboon sessions convert --from codex --source YOUR_CODEX_ID \
  --to opencode --output ./opencode-session.json --model YOUR_PROVIDER/YOUR_MODEL
opencode import ./opencode-session.json
opencode --session PRINTED_NATIVE_ID --model YOUR_PROVIDER/YOUR_MODEL
```

Kilo uses the same export/import pattern with `--to kilo` and `kilo import`.
Choose a provider/model already configured in the independent destination agent.
Without `--model`, the converter prints a reminder to select one; it does not
silently route the standalone agent through Codelaboon.

For an existing OpenCode export going to ordinary Codex:

```bash
opencode export YOUR_SESSION_ID > ./source-session.json
codelaboon sessions convert --from opencode --source ./source-session.json \
  --to codex --output ./codex-session.jsonl --install
codex resume PRINTED_NATIVE_ID
```

`--install` creates a new native session in the destination's ordinary home.
`--target-home PATH` selects another home, and `--cwd PATH` selects another project.
Codex, Claude, OMP and Jcode use new native files; Crush inserts a new session into
its project database in a transaction. OpenCode/Kilo use their native `import`
command instead of `--install`. Existing export files are never overwritten.

Other independent continuation commands printed by the converter:

```text
claude --resume PRINTED_NATIVE_ID
omp --session /absolute/path/to/export.jsonl
jcode --resume PRINTED_NATIVE_ID
crush --session PRINTED_NATIVE_ID
```

`--to crush --install` defaults to the current project's `.crush` data directory.
For another project, supply `--target-home /project/.crush` and `--cwd /project`.
The converter performs no inference; the destination uses its own credentials
and model settings. Codelaboon can be removed after conversion.

An existing library session can also leave Codelaboon:

```bash
codelaboon sessions export UNIVERSAL_ID --engine codex \
  --output ./native-session.jsonl --install
```

## What transfers

Conversation text, completed tool results, project location, source summaries
and original native records are retained. Foreign tool calls are rendered as
historical text: the destination reasons about the work using its own tools.
Source system/developer instructions become labeled history, not destination
policy. Approval grants, running processes, sandbox state, encrypted reasoning,
provider credentials and authentication entitlements do not transfer. Image/binary
attachment records remain in the original archive; cross-engine replay currently
uses attachment notices rather than pretending every engine can replay them.

Repository changes remain in the working tree; this feature does not copy project
files or reset Git. The target model's context limit still applies. Switching
engines changes harness behavior; it does not make their internal execution state
identical. Use one engine at a time for a shared continuation; simultaneous edits
to different native projections are not a conversation-merge mechanism.

Verification: native headless conversation resume in all seven engines, plus an
actual Codex-to-OpenCode continuation retaining one universal library ID. Unit
checks cover private/non-overwriting exports, original archives, compaction tails,
linked fork boundaries, branch selection, and conversion without library access.
