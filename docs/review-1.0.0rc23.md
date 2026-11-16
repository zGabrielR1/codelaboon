# RC23 review and release evidence

The prior candidate selected a side panel without navigation and placed the chat below policy/output sections. RC23 uses real task links and history-aware chat routes; mobile hides the task list while a conversation is open. Messages scroll independently and the composer stays in view. No automatic task selection conceals the distinction between list and chat. Missing IDs have an unavailable-task state rather than silently opening another task.

The native engines previously provided no background task entry. A shared launcher now offers task conversations before a bare engine chat; all seven aliases accept --tasks and --direct. Commands with native arguments, non-TTY calls and headless workers bypass it. Native smoke fixtures explicitly use direct mode. The shared optional Textual task app never starts inference just to view a task; base installs fall back to browser conversations.

Reviewed origin/token checks, message idempotency, text-only transcript rendering, terminal Rich markup escaping, immutable elevation snapshots, stale worker delivery, independent verification and viewing-versus-execution semantics. Browser message retries retain request IDs; backend rejects guidance on stopped/completed tasks. No user worker was restarted or modified. Each elevated case remains immutable; notes are not injected into approved runs.

Local verification: 347 unit tests passed, 3 skipped. Textual pilot tests exercised task opening, live output, guidance and older-worker note mode. Real Chromium smoke passed click/deep-link/reload/back, output updates, durable guidance and composer/overflow checks at1440/768/390. Built thin wheel/source and VSIX; engine source provenance verifies680 OpenCode and1856 OMP files. Release CI additionally gates all supported native smoke tests and portable contracts. These fixtures establish protocol and UI behavior, not live provider quota availability or a security assessment result.

Remaining limits: viewing a background task is a shared task conversation rather than an imported native session. Guidance enters the next attempt, not an already-running model request. Long-running old workers need a graceful restart before guidance is supported. Textual task chat requires the optional tui extra; otherwise tasks open in the browser. No RC22 release was published; RC23 contains its candidate changes.

Final responsive inspector: zero failures, one chart-hue warning caused by the navigation SVG (no chart is present). Screenshots viewed at desktop, tablet and mobile. Monospace lint applies to literal task IDs and captured code/output.

Publication evidence: release workflow43937514148 and verify43937484881 succeeded for94dac7bc6187e9ffe7511ac65cc1cd86b86805a4. Public RC23 assets independently downloaded and SHA256-checked; published wheel task entry tests passed in an isolated environment.
