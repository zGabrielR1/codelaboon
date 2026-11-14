# Latest release candidate: 1.0.0rc10

RC10 verifies the actual native OpenCode/OMP interfaces and adds a Kilo-derived
palette through their own theme systems. It also fixes OMP profile routing and
startup defaults. See [RC10 notes](release-1.0.0rc10.md) and the
[native runtime guide](native-runtime.md).

Validation covers 178 Python tests, both engines' type checks, actual file-tool
round trips, and terminal checks at 80/160 columns for welcome, response, prompt
recall and theme/settings menus. Wide OpenCode checks delegated/background work;
OMP checks profile-local sessions and logs. Bundle hashes and patch replay are
verified. CI repeats native checks on fresh packaged sources before publication.

The tag workflow for `v1.0.0-rc.10` is the publication authority: it publishes the
wheel, source archive and SHA256SUMS only after required checks pass. Runtime
credentials, dependencies, sessions and model weights are excluded from release
artifacts. Existing background service/queue data is preserved.
