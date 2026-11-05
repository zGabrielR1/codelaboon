# codelaboon 1.0.0rc1

Verified on Windows / Python 3.14, 2026-11-05.

- 55 offline tests passed, including HTTP request protection, model discovery, token refresh, JWT validation contract, TUI picker and login flows.
- JavaScript syntax and git whitespace checks passed.
- Browser QA: desktop 1440x900 and mobile 390x844; no horizontal overflow. Inspected screenshots in dark/light layouts.
- Browser interaction fixtures verified two-message chat, fenced code rendering, persisted conversation restoration, login pending-to-connected UI, model refresh and draft preservation after a simulated 502.
- Sign-in and chat were mocked in browser checks. A failed-resource console entry during the deliberate 502 check is expected. No live account authorization, subscription inference or production provider access was verified.
- Built source archive and wheel; installed wheel into an isolated target and confirmed version 1.0.0rc1 and all four web assets.
- Original SSH remote access fails because the sandbox cannot read the existing known_hosts file. Publication is not verified.

Artifacts are in dist/: codelaboon-1.0.0rc1-py3-none-any.whl, codelaboon-1.0.0rc1.tar.gz and SHA256SUMS.

Adversarial release review: offline and fixture evidence supports an RC for local evaluation. It does not establish live account availability or a complete OpenCode feature port. Those remain explicit acceptance limits.
