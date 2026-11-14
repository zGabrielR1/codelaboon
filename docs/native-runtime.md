# Native runtimes and continuous workers

## Source and packaging

The default UI executes OpenCode v1.2.27, revision
`4ee426ba549131c4903a71dfb6259200467aca81`. The OMP option executes
Oh My Pi v13.18.0, revision `3f60ba602abead98563fdab1d9d3db6b28cef429`.
Reference clones live under ignored `forks/`. Runtime workspaces are imported by
`scripts/import_upstreams.py`; reproducible patches live in `scripts/patches/`.
`scripts/bundle_sources.py` builds source archives for wheels and source releases.
Only provenance-listed files enter those archives; dependencies, sessions and
credentials are excluded. Each archive includes upstream licenses, original file
hashes, and hashes of modified files. OMP's native addon is downloaded at setup
and checked against npm's SHA-512 integrity value.

Installers prepare the selected engine and install Bun through npm if needed.
`--skip-runtime` installs Python only. Virtual environments use their own script
directory. Externally managed system Python uses a private venv instead of
overriding the operating system's package protections. Fish profiles use
`fish_add_path`. Source updates stop on a failed fast-forward pull; `--no-pull`
explicitly reinstalls local work. Setup needs network access and disk space.

## RC10 native UI verification and Kilo reference

Kilo CLI is itself an OpenCode fork. Its CLI theme at revision
`85eb887a7560f452211bcd382eafe8cb2f8df497` is the palette reference for RC10.
Codelaboon includes that exact native OpenCode theme asset and an adaptation
using OMP's own theme keys. `codelaboon/themes/PROVENANCE.json` records the
source and SHA-256; `KILO-LICENSE` preserves its MIT notice. No Kilo account,
telemetry, extension host or UI renderer is added.

Fresh profiles use `codelaboon-kilo`; OMP also has `codelaboon-kilo-light`.
Saved native theme settings are respected. `codelaboon tui --theme NAME` or
`codelaboon tui --engine omp --theme NAME` supplies an explicit launch choice.
The native menus can still change themes during the session.

OMP's config-root override now accepts an absolute profile directory, so its
logs and caches follow its Codelaboon sessions instead of writing to `~/.omp`.
The upstream condensed-changelog setting is enabled by default in this fork;
checks for a separately installed OMP binary update are disabled by default.
These defaults do not replace the upstream rendering or command behavior.

`scripts/export_source_patches.py` reproduces each source edit from pinned Git
objects and replay-checks it. Run it before `scripts/bundle_sources.py`, then
`scripts/verify_bundles.py`. The release pipeline checks bundle hashes and the
package/tag version before publishing.

```bash
python scripts/smoke_ui.py --engine opencode --width 160
python scripts/smoke_ui.py --engine opencode --width 80
python scripts/smoke_ui.py --engine omp --width 160
python scripts/smoke_ui.py --engine omp --width 80
```

These checks use tmux and a local fixture model. Add `--setup --types` for a
fresh packaged-source runtime and its upstream type checks. Screens and JSON
results are stored in ignored `.runtime/ui-qa/`. GitHub runs this same matrix
before a tagged release and retains the terminal evidence as workflow artifacts.

## Providers and free selection

The gateway preserves chat tool calls/results, Responses input items,
Anthropic content blocks, Gemini function calls, and SSE. Python credentials
stay out of generated model files; native clients receive a per-launch loopback
token. ChatGPT account tokens remain restricted to OpenAI; Claude/Gemini account
tokens retain the providers' endpoint restrictions. Gemini Code Assist requests
use the existing account/project onboarding and unwrap its response envelope.

Native free Auto rotates among compatible Our Free Model, Kilo, Pollinations,
Freebuff and authenticated OpenRouter free routes before streaming a response.
It never replays a partially emitted tool turn. Gemini is individually selectable
through its native Google protocol; Python free Auto can also use its account lane.
Gemini API keys and Qoder Cloud PATs are excluded from free Auto because their
presence does not establish free inference. Groq/Cerebras are explicit account
options; account plans and quotas determine cost. WusRouter and paid OpenRouter
models remain explicit selections. OpenRouter free routes reject paid model IDs.
Availability and limits can change; no finite list represents every free service.

OpenCode's own built-in provider/connect flows remain available in the native UI.
The current free Console inference restriction is documented by
[OpenCode](https://opencode.ai/docs/console/api/inference).
OpenRouter documents its free variants and limits in its
[free catalogue](https://openrouter.ai/collections/free-models).

`codelaboon providers check --live` checks local credential presence and asks
providers for their catalogues. Some providers have offline fallback catalogues;
a listed model does not prove a valid login, inference quota, or free access.
Browser OAuth completion and authenticated inference need the user's account.
Qoder PAT inference always uses its HTTP Cloud Agents API without a local CLI;
it requires Cloud Agents access and an existing remote environment. Browser device
tokens still belong to the optional Qoder CLI lane.

## Our Free Model source

The official source clone is `forks/dsh-our-free-model`. The reviewed revision is
`edfdaf2cb64bb39c7c682b90c96ef9e3fef3be15`. It supplies an independent local
service without requiring the DeepSeek Harness host. Node >=22.19 is required.

```bash
codelaboon ourfree setup    # installed users: fetch the pinned official source
codelaboon ourfree start    # keep this running; local management page is printed
codelaboon ourfree connect  # another terminal: import the generated local key/port
```

Source checkouts reuse the restored fork, so skip `setup` when it exists.
The gateway uses its own Codelaboon data directory and starts with LAN forwarding
disabled. `connect` stores the key privately and never prints it. Follow the
[upstream standalone guide](https://github.com/Ebony-Vinyl/dsh-our-free-model/blob/main/packages/standalone/README.md)
for channel setup and account eligibility. This is a client integration; it does
not remove provider authentication, quotas, geography restrictions or terms.

## Local and security use

Configure `local` with a literal loopback HTTP endpoint such as Ollama's
`http://127.0.0.1:11434/v1` or llama.cpp's `/v1`. Local catalogue and inference
requests ignore system proxies and refuse redirects. Any locally installed model
can be selected; Codelaboon does not download an unspecified large model.

`codelaboon tui --local-only` limits gateway inference to the local provider and
disables cloud model fallback. It also disables OpenCode catalogue fetches,
automatic LSP downloads and default plugins. Initial SDK setup still needs a
package cache. Tool execution is not an OS network sandbox. Local context budgets
are conservative and OMP's local compaction defaults are reduced for small models.
Both engines retain native automatic compaction and persisted sessions.

`codelaboon tui --profile security` loads the packaged authorized-pentesting
instructions. Combine it with `--local-only` and a locally selected model if desired.
It uses the existing file, terminal and task tools, with scoped evidence collection
and remediation reporting. It does not install offensive binaries or imply that a
target is authorized merely because it can be reached.

## Background operation

```bash
python3 scripts/setup_orchestrator.py  # pinned CPU runtime/model; Windows or Linux x64
codelaboon work init                  # creates a separate empty task queue
codelaboon work enable                # OS autostart and service start
codelaboon work status --json
codelaboon work add "Implement the requested change" --project /path/to/project \
  --check "python3 -m unittest discover -s tests"
codelaboon work pause
codelaboon work resume
codelaboon work stop                  # finish the current attempt, then stop
codelaboon work disable               # remove OS autostart; stop the service
```

Linux uses a user systemd service with restart-on-failure and lingering after
logout. Windows uses a login-triggered Scheduled Task with restart-on-failure;
macOS uses a LaunchAgent. Those two platforms need a user login after reboot.
Sleep, power loss, offline providers and quota limits still stop useful work.
Linux registration requires a working user service manager; some hosts require
administrator permission for lingering. No paid fallback is installed.

The supervisor owns/restarts the local routing server and cloud scheduler. Qwen
receives routing metadata only: candidate task IDs, stage, worker capabilities,
success/failure counts and timing. It can select only a listed job. Worker
cooldowns, optional `available_argv` probes, task/harness rotation and independent
acceptance commands control dispatch. Builds execute the bundled OpenCode source
through the tool-preserving gateway; they do not require an external OpenCode binary.
Native session compaction handles long tool runs. Background native state is
isolated below the worker runtime; interactive state remains under the user config. Plans, attempt logs and task state
persist across restarts; prior attempts are linked in subsequent prompts.

The queue is intentionally empty after initialization. Add concrete tasks with
acceptance commands; the service does not invent work. `work enable --config PATH`
registers a specific configuration. Status and the native sidebar use user
`work.json`, then source `.runtime/work.json`, then the preserved legacy queue.
An installed runtime can set absolute `local_model` and `local_executable` paths.

## Checks

```bash
bash scripts/test.sh
bash scripts/verify.sh
python3 scripts/smoke_native.py --engine opencode
python3 scripts/smoke_native.py --engine omp
```

The native smoke checks use a local fixture model to require a real file read and
return its tool result to the model. They exercise source execution and gateway
compatibility without spending cloud inference quota. They require engine setup
and may populate first-run SDK caches. The offline suite also checks provider
protocol boundaries, paid-route exclusion and platform autostart specifications.


## Startup and optional native CLIs (RC11)

`codelaboon` always opens OpenCode; installation has no engine picker. Setup and
installed entry points use the same archive-hash runtime cache. Missing setup is
repaired on launch. Production dependencies use Bun's normal shared cache; Python
Textual remains available in `.[tui]` for the legacy reference interface and tests.
A missing Bun runtime is downloaded from the official npm package with SHA-512
verification, without Node/npm. Provider discovery waits at most one second before
using cached/default models. Remote model metadata is fetched during setup rather
than first render. Native custom plugins may still perform their own setup.

`codelaboon omp` retains the source-forked OMP interface. `codelaboon kilo` downloads
the official Kilo native binary and connects its UI/tools to the gateway.
`codelaboon claude` now starts the unmodified Claude Code client on `free (Auto)`.
Its private loopback token and isolated `claude-code/` profile replace account
setup for this route. Local onboarding preferences are prepared automatically;
workspace trust and native permissions remain active. The free-only model picker
uses the Codelaboon catalogue. Personal Claude OAuth/API credentials are excluded
from this launch, and the gateway never automatically falls back to paid providers.

The Messages adapter translates text/images, tool schemas/calls/results, streaming
and usage to OpenAI-compatible free providers. Tool JSON fragments are combined
and validated before emission; interrupted streams produce errors rather than a
successful completion. Output is capped at 4096 tokens per request, matching the
existing native gateway configuration. Token counting uses a conservative local
UTF-8 size estimate (not a provider tokenizer). Native Claude cost displays are
client estimates for an unknown model; they are not Anthropic charges. Claude-only
cloud/account features are outside this third-party provider route.

These optional CLIs each add their native binary only when requested (roughly
250–300 MB on Linux x64); they do not install their development monorepos.

Development source directories are used only with `CODELABOON_DEV_RUNTIME=1`;
normal commands consume the verified packaged source archives. Existing sessions,
credentials, OMP profiles and background queues are preserved during upgrades.


## Crush engine (RC14)

`codelaboon crush` runs the official native Crush v0.101.0 binary and its Bubble
Tea UI. Automatic setup downloads the pinned release archive from Charm's GitHub
release and verifies checksums.txt before activation. Matching native binaries
can be reused; npm/script wrappers and mismatched versions use the managed native
install. The upstream license and notices remain with the extracted release.
Crush is FSL-1.1-MIT, not covered by Codelaboon's own source license.

The wrapper generates native crushrc configuration for the loopback provider,
using environment references instead of provider credentials. Both model roles
start on free (Auto); the native picker also exposes individual free/local models.
Default provider discovery, Catwalk refresh and metrics are disabled for this
route. Project configuration, initialization choices and interactive permissions
retain native behavior. Context configuration supports the existing security
profile, and `tui --engine crush --local-only` restricts inference to local models.

Native project databases live below `crush/projects/<project-hash>` inside the
Codelaboon profile; global preferences and caches have separate directories.
Each launch gets temporary gateway metadata, preserving concurrent-session token
isolation. Themes are native and persist through Crush's own state files.

Interactive mode stays in-process. `crush run` uses the upstream client/server
path because v0.101.0 local-mode stdout can drop a fast final reply. A private
per-launch IPC server is probed for readiness, then terminated/reaped when the
client finishes. Its temporary logs and configuration are removed. This is not
a persistent background daemon. Noninteractive permissions follow upstream
Crush's own behavior; the wrapper does not add yolo flags.

The Linux x64 native package measured about 98 MB locally; no Go/Node/Bun runtime
or development source tree is required. Windows/macOS archives are mapped by the
installer but native execution on those hosts has not been verified here.
