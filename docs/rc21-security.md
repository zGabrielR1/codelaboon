# RC21 web and IT security

RC21 extends RC20's scope-bound runner with web probes, local configuration
checks and defensive retesting. The coding harness and security profile share
these tools; profile instructions guide behavior while the runner enforces
network scope, pinned addresses and request budgets.

## What changed from RC20

| Area | RC20 baseline | RC21 change | What it gives you |
| --- | --- | --- | --- |
| Web assessment | Headers, TLS trust/version and explicitly scoped Git/config exposure | Opt-in `methods`, `cookies`, `cors` and `browser` checks | More web misconfiguration evidence at each approved URL |
| Method testing | No built-in OPTIONS check | Records known advertised methods | Identify methods to review without attempting writes or deletes |
| Cookie and browser defenses | Missing-header observations | Cookie attribute/prefix counts, CORS, CSP/framing and policy-value checks | Pair observed policy weaknesses with remediation and a retest |
| Local IT configuration | No built-in explicit-file audit | `security audit-local` | Inspect selected files for key markers and supported permission issues |
| Retesting | Review separate assessment reports manually | `security compare` with equivalent coverage and matching evidence | Track `new`, `persisting` and `not_observed_on_retest` observations |
| Scope and evidence | Approval hash, pinned IPs, request budget and no redirects | Stricter inputs, expiry checks before probes, hashed header values, tighter XML import | Reject more malformed scopes/evidence and retain fewer raw response values |
| Windows storage | String-based relocation matching | Path-based matching and relative-path reconstruction | Rewrite stored local model/executable paths correctly during relocation |

The default assessment still runs `headers`, `tls` and `exposure`. Include each
new web check with `--check` when creating the scope. RC20's separate privilege
cases, worker supervision and routing remain available; RC21's added probes do
not grant additional process privileges.

## Behavior and architecture changes

The security profile now explicitly follows:

1. Establish the objective and exact scope.
2. Form a hypothesis and choose a bounded probe.
3. Review the evidence and distinguish an observation from an exploit.
4. Propose a defensive control or fix.
5. Retest independently within scope and preserve evidence references.

The profile treats target responses, repository content and tool output as
untrusted evidence. Discovered URLs and redirects do not extend authorization.
These are model instructions; the runner's URL/address/budget checks enforce
the built-in assessment boundary. Neither layer is an OS sandbox.

The code now separates network execution (`security_assessment.py`), pure web
analysis (`security_checks.py`), local-file auditing (`security_local.py`) and
report comparison (`security_reports.py`). This makes the new rules testable
without requiring remote targets or model calls.

## Get the published version

Download assets from the [RC21 release](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.21).
For an existing Python environment, install the published wheel and confirm the
version with that same interpreter:

```bash
python -m pip install --upgrade "https://github.com/zGabrielR1/codelaboon/releases/download/v1.0.0-rc.21/codelaboon-1.0.0rc21-py3-none-any.whl"
python -m codelaboon --version
```

The core reports `1.0.0rc21`; the VS Code connector is `1.0.21`. A new assessment
scope is needed for additional checks or an expired scope. Output files must use
new names: the assessment, audit and comparison commands do not overwrite files.
The Windows dependency-recovery fix described in
[native runtime recovery](native-runtime.md#windows-damaged-runtime-dependencies)
is a subsequent source change, separate from the original RC21 assets.

## Web assessment

Create and review a scope for systems you are authorized to assess:

```bash
codelaboon security capabilities
codelaboon security scope --target http://127.0.0.1:8080/ --check headers --check tls --check exposure --check methods --check cookies --check cors --check browser --max-requests 12 --timeout 5 --output scope.json
codelaboon security assess --scope scope.json --approve PRINTED_SCOPE_ID --output before.json
```

`PRINTED_SCOPE_ID` is the `scope_id` returned by the scope command. Read the scope
file first, then substitute that exact value. The example uses a local server
you supply on port 8080; it does not start one. Each extra `--target` adds another
exact URL to the scope. For HTTPS coverage, use an explicitly approved HTTPS URL.

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

For example, a recognized private-key marker produces `private-key-material`;
on POSIX a recognized sensitive file accessible to group/other users produces
`sensitive-file-permissions`. A file writable by other users produces
`world-writable-config`. Check the file's purpose and ownership before changing
permissions. On Windows, `permission_check: "not_supported"` means ACL coverage
was not performed, even if key-marker sampling completed.

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

| Comparison field | Meaning | Next action |
| --- | --- | --- |
| `new` | A rule/target pair appears only in the later report | Review the new evidence and deployment changes |
| `persisting` | The same rule/target pair appears in both reports | Review whether the intended control was applied |
| `not_observed_on_retest` | The earlier pair is absent from the later report | Independently confirm the response context and intended fix |

Comparison accepts network assessment reports, not local-audit or imported nmap
reports. Each completed check needs matching evidence; a certificate failure
during a browser/cookie/CORS probe cannot substitute for successful response
coverage. A TLS trust-failure observation remains valid evidence for the TLS
check itself. If coverage is incomplete, correct the failed check or budget and
run a fresh assessment before comparing.

## What the release verification established

The [release workflow](https://github.com/zGabrielR1/codelaboon/actions/runs/43865513858)
and [verification workflow](https://github.com/zGabrielR1/codelaboon/actions/runs/43865002117)
passed, including Python 3.11-3.13, native engine/tool gates and portable security
contracts on Linux, macOS and Windows. The local Windows/Python 3.14 suite ran
310 tests with zero failures/errors and three platform skips. The downloaded
public wheel passed 32 isolated security tests with one platform skip; all five
published artifacts matched `SHA256SUMS`.

This verifies the shipped checks and tested flows. It does not establish
exhaustive penetration-testing coverage, Windows ACL analysis, authenticated
authorization testing, or resistance to arbitrary local runtime corruption.
The later Windows cache failure and recovery are documented separately.

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
