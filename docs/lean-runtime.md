# Lean core, optional engines, and native swarms

OpenCode remains the default interactive interface. The Python core owns provider
credentials, model discovery/failover, gateway adapters, and durable work queues.
Engines keep their own tools, sessions, compaction and native theme behavior.

## Installation and engine modules

Install the core normally. On first use, Codelaboon automatically prepares the
requested engine and its dependencies. `install --prepare-runtime` prepares
OpenCode ahead of time. Optional OMP, Kilo, Claude Code, Crush and Jcode engines
are installed only when selected. No Rust/Go compiler is required for native CLIs.

OpenCode and OMP source bundles are separate GitHub release assets, pinned by
SHA-256 in the packaged `engines.json`. Downloads stream into a temporary file,
are verified before use, and are cached outside the checkout. Existing prepared
runtimes launch without downloading the bundle again. Source bundles, patches,
provenance and licenses remain reproducible release inputs in Git. The source
checkout keeps the small compressed inputs; installed core packages omit them.

## Storage and backups

Preview from the source checkout:

```bash
codelaboon storage audit
codelaboon storage compact                 # same preview, no changes
codelaboon storage compact --apply         # relocate the listed untracked paths
```

The command refuses tracked inputs, existing destinations, unsafe destinations,
and active source processes on Linux. Stop the idle worker before relocating its
runtime. Each completed move is journaled; nothing is deleted. On a partial
failure, inspect the reported exception and `storage-migrations` journal before
retrying. The journal records paths, not credentials or task contents.

| Location | Purpose | Backup policy |
| --- | --- | --- |
| Source checkout | Code, patches, pinned compressed release inputs | Git and normal `ppp` backup |
| `~/.cache/codelaboon/development` | Source trees, reference clones, dependencies, build environments | Rebuildable, except uncommitted development edits |
| `~/.cache/codelaboon/engine-assets` | Verified engine download cache | Re-downloadable |
| `~/.config/codelaboon` | Accounts, sessions, installed engines, worker state and optional router weights | Preserve private state; weights/engines can be large |
| `~/.local/share/codelaboon` | Swarm results, legacy work history, release copies, migration journals | Back up durable results/history separately if desired |

Overrides: `CODELABOON_CACHE_DIR`, `CODELABOON_DEV_DIR`, `CODELABOON_CONFIG_DIR`,
`CODELABOON_DATA_DIR`; standard XDG cache/data roots are also supported. Relocation
reduces `ppp` backups; it does not free the same amount of total disk space. Do not
blindly erase development caches containing unique edits. `scripts/dev.py paths`
shows the development root; `prepare --engine opencode` or `--engine omp`
prepares editable runtimes there. Import/export/bundle scripts use that root.

## Lightweight background execution and swarms

Jcode v0.99.1 supplies the native Rust harness, through Codelaboon's loopback free
model gateway. Its MIT-licensed binary is downloaded unchanged and verified
against the official release checksums. Memory embeddings, telemetry and native
self-update/self-development are disabled for managed workers.

```bash
codelaboon jcode run 'Inspect the current project'
codelaboon swarm 'Implement and verify the requested change' --workers 4 \
  --timeout 1800 --check 'python3 -m unittest discover -s tests'
```

One gateway serves a coordinator and native workers; there is no Python provider
process per swarm member. Jcode's native server manages worker sessions, context,
communication and reports. The worker cap is enforced by native configuration,
not only the prompt. The default is four; select a smaller cap on limited hardware.
Workers may share the project, so the coordinator must divide file ownership and
resolve conflicts. The harness decides when delegation is useful.

Each swarm run saves its private sessions and `result.json` under
`~/.local/share/codelaboon/swarm/runs`. Acceptance commands share the remaining
wall-clock budget, write separate logs and must pass for acceptance to be marked
passed. Without checks, the result explicitly says `not_requested`. Do not treat
an agent's final text as proof that the implementation passes tests.

New background worker configurations use free planning and Jcode building. Existing
builder commands without `--engine` now use Jcode; explicit `--engine opencode`,
`omp` or `kilo` selects those harnesses. Durable independent verification and the
local router's scheduling decisions remain in the supervisor. An idle service
unloads its owned router model; queued work loads it again. Externally managed
router servers are never stopped by this optimization.

## Measurement scope

The Fedora development checkout shrank from 3.9 GB to about 29 MB by relocation;
the RC15 wheel measured 173 KiB before final documentation. The idle user service
measured about 35 MiB via systemd `MemoryCurrent`, with two Python processes and
no llama-server/model loaded. These are local observations, not portable limits.

[Jcode's published comparisons](https://jcode.sh/) measure specific versions and
additional sessions, not Codelaboon's total memory or model weights. We do not
claim their 48x/20x ratios for this integration. Large local models, provider
latency, context length, tools and chosen engine still determine practical cost
and quality. Default worker limits are conservative; thousands of concurrent
sessions are not a tested hardware guarantee.
