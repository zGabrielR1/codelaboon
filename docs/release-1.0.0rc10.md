# RC10 — native UI verification and Kilo-derived themes

RC10 keeps the actual OpenCode and Oh My Pi source runtimes. Codelaboon's provider
transport, orchestration and state routing remain behind those native UIs.
Kilo Code is the UI reference: its native charcoal/yellow theme is included with
its MIT notice and pinned revision/hash, and adapted to OMP's native theme format.

## User-visible changes

- Fresh profiles start with the Kilo-derived palette. Existing native theme
  choices are respected. `codelaboon tui --theme NAME` selects an explicit theme;
  `--engine omp` runs the real OMP editor, welcome screen, menus and effects.
- OMP state, sessions, logs and themes stay in its Codelaboon profile. The native
  changelog starts condensed and unrelated binary-update notices are off by default.
- Both UIs are exercised at 80 and 160 columns with local fixture inference:
  welcome, response, prompt recall, and native theme/settings pickers. Wide OpenCode
  also checks the delegated/background sidebar; OMP checks session/log persistence.
- GitHub publishing is gated by this UI matrix, upstream type checks, native
  file-tool round trips, Python regressions, bundle integrity and tag/version checks.

## Sources

- OpenCode v1.2.27: `4ee426ba549131c4903a71dfb6259200467aca81`.
- Oh My Pi v13.18.0: `3f60ba602abead98563fdab1d9d3db6b28cef429`.
- Kilo theme reference: `85eb887a7560f452211bcd382eafe8cb2f8df497`.

Each runtime bundle contains upstream licensing and original/modified hashes.
`export_source_patches.py` verifies that the fork edits replay exactly against
pinned Git objects. `verify_bundles.py` validates every bundled source file.

## Validation and limits

178 Python tests pass locally. OpenCode type checking and OMP Biome/type checking
pass. Both engines complete a real file-tool request/result round trip using a
local fixture model. Terminal screenshots are plain-text evidence under
`.runtime/ui-qa/`; CI preserves equivalent evidence as workflow artifacts.

These are Linux terminal and protocol checks, not proof of provider quota or
account eligibility. Windows/macOS service execution and real Claude/Gemini/Qoder
inference still need their host/account environments. The existing background
service and queue are preserved; the queue remains empty.

The release workflow publishes the wheel, source archive and SHA256SUMS for
`v1.0.0-rc.10` only after all required checks succeed.
