# RC21 web and IT security

RC21 extends RC20's scope-bound runner with web probes, local configuration
checks and defensive retesting. The coding harness and security profile share
these tools; profile instructions guide behavior while the runner enforces
network scope, pinned addresses and request budgets.

## Web assessment

Create and review a scope for systems you are authorized to assess:

```bash
codelaboon security capabilities
codelaboon security scope --target http://127.0.0.1:8080/ --check headers --check tls --check exposure --check methods --check cookies --check cors --check browser --max-requests 12 --timeout 5 --output scope.json
codelaboon security assess --scope scope.json --approve PRINTED_SCOPE_ID --output before.json
```

Every applicable check consumes one request. TLS is not applicable to HTTP.
The default checks remain headers, TLS and exposure; additional probes must be
named in the approved scope. URLs are exact, including the path: exposure checks
require explicitly scoped `/.env` or `/.git/HEAD` URLs. Redirects are never followed.
Request receipts include the HTTP method, status, pinned address and evidence ID.
Header values and bounded body samples are hashed; cookie names and values are
not retained. Response bodies and raw tool instructions never enter the report.

| Check | Probe | Observation and limits |
| --- | --- | --- |
| headers | GET | Missing response security headers; context-dependent |
| tls | TLS handshake | Trust validation and negotiated version; no exhaustive cipher scan |
| exposure | GET | Recognizable Git HEAD/environment content at exact approved paths |
| methods | OPTIONS | Known Allow tokens; risky method advertisements are informational, never executed |
| cookies | GET | Attribute counts: Secure on HTTPS, HttpOnly, SameSite, insecure SameSite=None and invalid __Host-/__Secure- prefix attributes; cookie purpose unknown |
| cors | GET with synthetic Origin | Allows `https://codelaboon-probe.invalid` with credentials, or wildcard access; no user credentials supplied |
| browser | GET | HTML framing restrictions, CSP unsafe-eval/wildcard script policy, invalid nosniff, inactive HSTS |

CORS observations do not demonstrate authenticated data access. Public resources
may intentionally allow wildcard access, and wildcard plus credentials is not
reported as a credentialed browser exploit. Duplicate CORS policies are recorded
without assuming the browser accepts them. Browser policy analysis is a limited
token check, not a complete browser/CSP evaluator or an XSS exploit test.

Scope approval freezes URL/address/check/budget data. Invalid ports, address zones,
ambiguous URL characters, malformed pins and nonfinite/future/overlong timing
values are rejected. Expiry is rechecked before each probe. Socket-operation
timeouts are not a hard wall-clock limit against trickling responses, and an
in-flight request is not interrupted when the scope expires. Use process
isolation/timeouts for hostile environments. No path discovery, authenticated
authorization test, destructive method execution or OS sandbox is implied.

## Local IT configuration audit

Local audit is read-only and accepts up to 100 explicit files beneath a project.
It does not walk directories, run project code, follow symlinks/reparse points or
read more than 65,536 sampled bytes per file plus one truncation-detection byte.

```bash
codelaboon security audit-local --project . --file .env --file config/server.pem --output local-audit.json
```

Private-key markers are informational. POSIX checks report group/other access
to recognized sensitive files and world-writable configuration files. Windows
ACL analysis is explicitly unsupported. Reports contain relative paths, hashes,
sample/truncation metadata and remediation, without contents or secret values.
This is not exhaustive secret, malware, dependency or host configuration analysis.
Use a trusted, quiescent directory: opening checks reduce file replacement races
but do not isolate against concurrent ancestor replacement by another process.
Missing, escaping, nonregular or link inputs fail the audit without writing a
partial report. Files beyond the sample limit are not fully analyzed.

## Defensive retest

After remediation, rerun the same checks against the same explicit URLs using a
valid scope. Reports with expired, inconclusive or budget-exhausted coverage are
rejected by comparison. Fresh scopes may have different identities.

```bash
codelaboon security assess --scope scope.json --approve PRINTED_SCOPE_ID --output after.json
codelaboon security compare --before before.json --after after.json --output comparison.json
```

Comparison records new, persisting and `not_observed_on_retest` rule/target pairs.
Absence is not proof of a fix: independently verify deployment identity, response
context, permissions and authenticated behavior. Reports are local observations,
not signed attestations. Output files are never overwritten.

## Architecture and validation

- `security_assessment.py`: explicit network scope, pinned connections, budgets,
  evidence collection, external nmap import and CLI dispatch.
- `security_checks.py`: pure cookie/method/browser/CORS response analysis.
- `security_local.py`: bounded explicit local-file audit.
- `security_reports.py`: size-bounded report reading and conservative comparison.
- `prompts/security.md`: scope, hypothesis, bounded probe, evidence review,
  remediation and independent retest; tool/target content is untrusted evidence.

Nmap XML imports read at most 8 MiB plus one byte, reject DTD/entities and NUL-based
encodings, require an nmap root, and enforce every reported address/port pair.
No script output or vulnerability claim is inferred from an open port.

Local fixtures cover vulnerable/hardened web responses, exact request paths and
Origins, secret redaction, expiry/budgets, malformed scopes, bounded local key
samples, permission handling, incomplete retests and hostile XML. Portable CI
includes the RC20 and RC21 contracts. Local success does not establish remote
coverage or replace manual platform checks documented for RC20.
