# Latest release candidate: 1.0.0rc11

RC11 repairs default OpenCode startup and automatic dependency installation,
reduces the production dependency footprint, and adds optional official Kilo and
Claude Code native CLIs. See [RC11 notes](release-1.0.0rc11.md) and the
[native runtime guide](native-runtime.md).

Local validation includes 183 Python tests, installed-command normal startup,
OpenCode/OMP/Kilo UI checks and native file-tool round trips. Claude Code's native
onboarding renders; authenticated inference remains account-dependent and untested.

[RC11 is published](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.11).
Release run `43555456667` and verify run `43555456805` succeeded. Downloaded
wheel/source assets match the published SHA256SUMS.
Release artifacts exclude provider credentials, sessions, dependencies and model
weights. Existing background service/queue data is preserved.
