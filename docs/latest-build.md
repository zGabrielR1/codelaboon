# Latest build: 1.0.0rc7

Adds the Qoder limitation alert across CLI, TUI and web, and switches
the license from MIT to Personal Use Only. No Qoder provider logic
changed in this build.

- Qoder limitation alert: the CLI prints it for Qoder
  `login`/`configure`/`models list`/`chat`, the TUI logs and notifies
  it when Qoder is selected, and the web workspace shows a banner
  while Qoder is the selected provider. It states that login works
  natively but chat runs through the official `qodercli` binary,
  because Qoder's gateway only accepts signed official-client requests.
- License: MIT replaced with a Personal Use Only license — codelaboon
  is a personal project for the owner's own use, with no redistribution
  or commercial use without permission. Each provider's own terms
  continue to apply.
- Published as tag `v1.0.0-rc.7`; the tag-triggered release workflow tests,
  builds the wheel/source archive, writes SHA256SUMS and publishes a GitHub
  prerelease with downloadable artifacts.
