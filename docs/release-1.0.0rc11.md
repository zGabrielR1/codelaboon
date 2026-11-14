# RC11 — Fedora startup repair and optional native CLIs

OpenCode remains the default interface. This release fixes normal startup hanging
on serial provider discovery, unbounded models.dev fetches, and redundant plugin
dependency installation. Provider discovery has a one-second render budget and
uses cached/default catalogues. Setup and installed commands share an archive-hash
runtime directory, with automatic repair on first launch.

Installation prepares production dependencies. Missing Bun is downloaded from its
official package with SHA-512 verification, without Node/npm. Textual is optional.
A fresh Linux OpenCode production runtime measured 626 MB versus roughly 1.1 GB
for the development tree; this is a local measurement, not a cross-platform size
guarantee. Existing credentials, sessions, OMP profiles and queues are preserved.

`codelaboon omp` retains the working OMP source interface. `codelaboon kilo` adds
the official Kilo 7.8.27 native UI through the provider gateway. `codelaboon claude`
adds the official stable Claude Code client with its own native authentication.
Both download only when requested, verify upstream checksums and retain upstream
licenses. Claude Code is proprietary and does not grant free inference.

Local Fedora validation: 183 Python tests; OpenCode type checking; normal startup
through the installed command from a fresh project; OpenCode, OMP and Kilo native
UI response, Up-arrow recall and theme checks; OMP and Kilo real file-tool loops;
a Bun bootstrap without Node/npm; Claude Code native onboarding without signing
in or making an inference request. Bundle integrity and structural checks pass.
CI additionally repeats the native type/UI matrix and source-tool tests before
publishing the tag. Windows/macOS execution and authenticated Claude inference
were not tested on this host.
