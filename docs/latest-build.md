# Latest build: 1.0.0rc8

Local release candidate built on 2026-11-08. Artifacts and SHA-256 checksums
are in `releases/`; this build has not been published or tagged remotely.

Includes WusRouter live discovery, browser signup and account-key switching;
native Qoder Cloud Agents support for PAT users without a local CLI; and a
responsive whale ASCII TUI welcome screen.

Low-level fixes cover atomic private configuration writes, concurrent updates,
stale TUI requests after switching accounts, bounded UTF-8 event parsing,
recoverable Qoder errors, and source-archive verification.

Live WusRouter public discovery was checked. Authenticated inference requires
provider credentials; Qoder Cloud Agents also needs access, quota and an
existing environment. Account availability and free-tier eligibility have not
been established by offline tests.

Validation: 132 tests pass from the extracted source archive. Both the checkout
and source archive pass `make check` and structural verification. The wheel is
installed and smoke-tested outside the checkout, and both artifacts have SHA-256
checksums in `releases/SHA256SUMS`.
