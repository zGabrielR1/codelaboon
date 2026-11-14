# RC11 adversarial review — 2026-11-14

Reviewed installation/launch paths, wire transport, dependency footprint, optional
upstream clients, CI coverage and release assertions before committing.

Findings corrected:

- Local-only smoke tests could pass while the normal path hung on discovery and
  models.dev. Added bounded catalogue regression tests and installed normal-path
  UI coverage without local-only shortcuts.
- Checkout setup and wheel launch selected different directories. Normal use now
  always selects the packaged archive cache; developer source is explicit.
- Kilo run's daemon could choose a different working directory and reject a valid
  project file as external. Wrapper now supplies cwd unless user supplies --dir;
  the real file-tool loop passes without relaxing permissions.
- Test title generation could route to a real keyless provider. All enabled free
  fixture routes now point to the local HTTP fixture.
- Native installation must reject corrupt binaries before activation. A checksum
  mismatch test verifies no current marker is published.
- Claude Code must retain its licensing/authentication model. It is an unmodified
  optional upstream download, with no claim of free or tested account inference.

Evidence: 183 unit tests; actual installed OpenCode normal UI; OMP/Kilo native UI
and tool loops; OpenCode types; source bundle integrity; structural checks;
standalone Bun bootstrap; Claude native onboarding in an isolated profile.
Production OpenCode disk measurement is scoped to Fedora (626 MB). No unsupported
claim of measured RAM savings or native Windows/macOS execution is made.

Accepted limits: custom upstream plugins may perform their own setup; first-time
dependency downloads take network time; cached model discovery updates appear in
the next native session. Authenticated Claude inference needs the user's account.
No blocking issue remains in the tested Fedora launch path. GitHub CI must pass
before publication is reported complete.
