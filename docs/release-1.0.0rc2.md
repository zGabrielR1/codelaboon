# codelaboon 1.0.0rc2

Verified on Windows / Python 3.14, 2026-11-05.

## User-visible changes

- TUI auto-save after completed replies; Ctrl+S searchable resume and /export JSON path.
- Web conversation search, rename, reversible archive/restore, per-conversation draft recovery and reload recovery.
- Stop waiting aborts the browser wait, preserves the prompt and rejects a late response. It does not cancel upstream execution or billing.
- Model discovery sequence guards, invalid-model clearing and prompt preservation on busy TUI submission.

## Evidence

- 60 offline tests pass, including new session-store validation and TUI resume/race checks.
- Browser fixture checks: draft survived reload, search filtered history, archived conversation restored with both messages, rename updated title, stop preserved draft and re-enabled provider selection.
- No horizontal overflow at 390, 768 and 1440 pixels; inspected mobile screenshot.
- Chat and model browser requests used explicit fixtures. Live account authorization and production provider inference remain unverified.
- JavaScript syntax and git whitespace checks pass.
- Wheel and source archive built; release install validation performed separately.

## Adversarial review

This candidate improves continuity and recovery, rather than provider breadth.
Browser history remains local to its browser origin; TUI sessions live in the config
directory. These stores are independent. Web rename/archive header controls are
desktop-only. Session JSON contains prompt/reply data; keep the config directory private.
