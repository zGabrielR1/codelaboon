# Latest release candidate: 1.0.0rc12

RC12 fixes the reproduced blank OpenCode screen in Fedora Ptyxis/GNOME Terminal:
frontend requests could outrun the backend worker listener. An explicit worker
readiness handshake replaces the accidental dependency on terminal timing.
See [RC12 notes](release-1.0.0rc12.md) and [review](review-1.0.0rc12.md).

Validated locally with the installed command in real VTE: home screen, fixture
model response and Up-arrow recall. The new immediate-terminal-response test
fails against RC11 and passes with the fix. Existing tmux UI, OpenCode types,
183 Python tests, patch replay and bundle integrity pass.

Publication requires successful `v1.0.0-rc.12` CI, including actual VTE under Xvfb.
