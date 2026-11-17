# RC25 adversarial review

Reviewed against public RC24. Initial checkout differences were line endings;
those were preserved. No real task, worker, settings or account was modified.

- Retry uses an atomic control file and the single supervisor remains scheduling
  state owner. Only a finished failed ordinary continuous task is eligible; stale
  requests do not replay newer attempts, paused/finished/stopped/elevated tasks are
  rejected, and only the selected task's cooldown/due time is cleared.
- Historical logs validate task ownership and resolved runtime boundaries. Bounded
  output is redacted, and browser strings use textContent. Form writes require
  trusted origin and the workspace token. Keys are hidden on entry, never echoed
  by the endpoint, and cleared from the form without browser persistence.
- Startup/resume controls explicitly explain that all ready queued tasks can run;
  opening an inspector cannot start a worker or inference. Existing authorization
  and verification rules remain unchanged. Older workers reject unsupported features.
- Portable wrappers retain explicit task permissions. A targeted regression found
  and fixed a missing import in the changed path before completion.
- HowToFix is authenticated live discovery, not guessed model IDs or silently free
  billing. Public endpoint401 was observed. Account verification requires a key.
- Copilot uses the pinned OpenCode public OAuth protocol, with its registered app
  disclosed and an optional client override. No gh credentials are extracted.
  Token forwarding is restricted to the official host; redirect following is
  disabled for account catalogue/chat requests. The gateway preserves tools.
- Windsurf/Devin uses the documented official CLI/account surface. There is no fake
  raw-inference endpoint or unsupported cross-engine SWE provider. Optional binaries
  are installed lazily from official manifest URLs and verified before execution.
  No shell installer is executed. Native account flags do not create OS privilege.
- Remaining limits are explicit: no account inference without authorization, no
  guarantee of free promotions/quotas, seven existing session transfer formats,
  and Windows/macOS native interaction not manually tested by this local run.

Browser regression passes reload-persistent drafts, keyboard sending/recall,
redacted historical output, checkpoint retry, worker pause/resume, mobile width,
and API-key form privacy, with all tasks/accounts mocked. The existing portable/browser workflow carries
that fixture into verification/release gates. Final full tests/build evidence is
recorded in PROGRESS after completion; this review precedes the presented result.


Final evidence:382full regressions pass after the final installer/portability fixes;
structural checks, JS parsing and core packaging checks pass. Chromium source and
isolated installed-wheel regressions pass all new operations, including retained
drafts, delivered guidance, scoped/redacted attempt logs, idempotent retry request,
worker scheduling pause/resume and provider key privacy. Wheel309548B/source537255B
remain below1MiB. Actual users' worker/tasks/accounts/settings were not touched;
all permission operations in QA used disposable state. No live account inference
was claimed. Fresh source modules/flags are feature-gated against older workers.
Existing CRLF changes were preserved; whitespace verification accounts for CRLF.

Publication: release 43985673599 and portable 43985673057 succeeded for
87821ffa035e0df88bd35f750ac9b46369a1e125. The initial verify run failed in the
lightweight Rust worker step, which passed in the release run; empty retry commit
16f3255 passed verify 43986553398 and portable 43986553181 without code changes.
All five published artifacts verified against SHA256SUMS; 27 targeted tests and
the Chromium task-operation smoke pass against the published wheel.
