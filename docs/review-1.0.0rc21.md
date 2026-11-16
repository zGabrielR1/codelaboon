# RC21 adversarial review

## Result

The source adds bounded web probes and explicit local IT checks while retaining
RC20's approval identity, pinned connections and request-budget enforcement.
New findings are observations with contextual remediation. Method advertisements,
CORS response policies and missing cookie attributes are not described as exploits.

## Attack and defense review

- Exact paths and a fixed synthetic Origin are asserted by real HTTP fixtures.
  Hardened fixture responses remove the corresponding observations on retest.
- Cookies and arbitrary policy/redirect values could contain credentials. Reports
  now retain attribute counts/known tokens and header hashes rather than values.
  The fixtures assert body, cookie and CSP-report-path secrets are absent.
- Nonfinite timestamps, malformed pins, zero ports and address zones are rejected.
  Expiry is rechecked before subsequent probes; request budgets remain enforced.
- UTF-16 XML could evade byte-oriented DTD checks. NUL encodings are rejected,
  alongside DTD/entities, oversized evidence and an unexpected root. Every address
  and port in a multi-address nmap host must be approved.
- Local audit requires explicit relative regular-file inputs, rejects traversal,
  alternate-stream syntax and links/reparse points, bounds each sample, and
  reports unsupported Windows permission coverage rather than inventing ACL results.
- Retest comparison rejects incomplete or mismatched target/check coverage.
  Findings absent on retest are named `not_observed_on_retest`, never resolved.
  Completed checks must reference matching evidence. Certificate failures during
  response probes cannot stand in for successful browser/cookie/CORS coverage.

## Platform review

Full-suite investigation found a real Windows relocation issue: slash-based
source matching and string-prefix rewriting failed for Windows/short paths.
Path-based comparisons and relative-path reconstruction fix the existing
preservation test. Other failing tests assumed POSIX mode bits/path spelling,
text launchers and a writable `/tmp`. They now assert their platform's contract
and use temporary screenshot output. Windows launcher validation inspects the
executable path rather than decoding a PE file as a shell script.

## Remaining limitations

Socket timeouts do not stop deliberate response trickling, and expiry does not
cancel an in-flight request. Reports and hashes are not signed attestations.
Local-file race checks are not isolation against concurrent ancestor replacement.
Cookie/CSP parsing is deliberately limited; CORS probes carry no authenticated
session. There are no destructive method tests, exhaustive host audits or new
scope adapters for the optional tool inventory. No remote systems, actual
privilege cases, native-engine changes or provider calls were tested for RC21.
Cross-platform CI and human OS-consent testing remain separate release gates.

## Verification recorded on this host

Windows/Python 3.14 full offline suite: 310 tests, zero failures/errors, three
platform skips. Targeted web/IT contracts were rechecked after the final retest
evidence validation change. Required-file/directory, syntax/import and whitespace
checks passed. Core wheel and source archive build successfully below 1 MiB.
An isolated installed wheel with declared dependencies also passed all 32
RC20/RC21 security tests (one platform skip). Source archive contents, connector
version 1.0.21 and artifact checksums were verified.
