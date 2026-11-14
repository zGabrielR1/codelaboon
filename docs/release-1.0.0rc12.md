# RC12 — Fix blank OpenCode startup in Fedora terminals

OpenCode could stay blank in Fedora Ptyxis/GNOME Terminal even though its backend
was alive. VTE answers the terminal background query immediately. That allowed
the frontend to send initial RPC requests before the backend worker registered
its message listener; Bun dropped those messages and the UI waited indefinitely.
The earlier tmux/local-only startup tests masked this timing race.

The worker now announces readiness after installing its RPC listener. The client
waits for that announcement before sending requests, and the terminal frontend
waits up to 15 seconds for worker readiness before displaying a startup error.
This preserves OpenCode's native UI and does not require switching terminals.

Validation: reproduced the blank screen in the actual Fedora VTE 0.84.1 library,
then verified rendering, a fixture model response and Up-arrow recall with the
installed fix. A fast-terminal-response regression fails against RC11 and passes
against RC12. The wide tmux UI check, OpenCode type check, all 183 Python tests,
source bundle integrity and patch replay pass. CI now additionally checks actual
VTE rendering under Xvfb and immediate terminal responses before publication.

Close the previous blank instance and run `codelaboon` in a fresh terminal.
Existing OMP runtime, provider credentials, sessions and worker queues are kept.
