# Latest release candidate: 1.0.0rc12

RC12 fixes the reproduced blank OpenCode screen in Fedora Ptyxis/GNOME Terminal:
frontend requests could outrun the backend worker listener. An explicit worker
readiness handshake replaces the accidental dependency on terminal timing.
See [RC12 notes](release-1.0.0rc12.md) and [review](review-1.0.0rc12.md).

Validated locally with the installed command in real VTE: home screen, fixture
model response and Up-arrow recall. The new immediate-terminal-response test
fails against RC11 and passes with the fix. Existing tmux UI, OpenCode types,
183 Python tests, patch replay and bundle integrity pass.

[RC12 is published](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.12).
Release run `43612181195` and verify run `43612181008` succeeded, including actual
VTE under Xvfb. Published wheel/source checksums verified. The user confirmed
that the installed fix opens correctly in a fresh Ptyxis terminal.
