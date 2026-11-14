# RC12 adversarial review — 2026-11-14

Reproduced the reported failure rather than inferring success from tmux. A VTE
window rendered a simple alternate-screen control while OpenCode stayed blank.
Captured output stopped after terminal setup; backend logs showed only the event
subscription, with initial config/provider RPC requests missing. Instrumentation
located the UI waiting in SyncProvider. Temporary instrumentation was removed.

Reviewed fix: Rpc.listen installs its listener before emitting rpc.ready. Client
calls await readiness; TuiThread waits with a 15-second bound and terminates an
unready worker on timeout. No arbitrary startup sleep or terminal-specific bypass.
The sole RPC client/server pair was checked for protocol compatibility.

Evidence: RC11 fails the new immediate-background-response test; the fixed source
and installed package both pass. Real VTE rendering, fixture response and history
recall pass with the installed package. Existing wide tmux behavior and themes,
OpenCode types, 183 Python tests, exact patch replay and bundle hashes pass.

No unrelated engine or provider changes. No credentials, session databases or
queues removed. Only diagnostic processes created in this session were closed.
No blocker remains in the reproduced Fedora launch path. Publication claims
remain gated on successful remote CI, including the new VTE job.
