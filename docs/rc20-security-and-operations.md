# RC20 security and operations

RC20 adds an evaluated assessment workflow alongside the security agent profile.
The profile guides an agent; the assessment runner executes bounded checks and
records reproducible observations. They are distinct parts of the same harness.

## Security assessment

```bash
codelaboon security capabilities
codelaboon security scope --target http://127.0.0.1:8080/ --check headers --output scope.json
# Review the scope file, exact URL, resolved addresses, budgets and printed ID.
codelaboon security assess --scope scope.json --approve PRINTED_SCOPE_ID --output report.json
```

Only run against authorized targets. Scopes expire after 24 hours, pin resolved
IP addresses, and require their exact SHA256 identity at execution. Requests never
follow redirects. The runner does not discover additional paths: explicitly add
`/.env` or `/.git/HEAD` URLs to assess those exposures. Defaults cap an assessment
at 12 requests and five seconds per socket operation; bounds are configurable.
Response samples are capped at 8192 bytes and retained as hashes, not bodies.
Credentials, cookies and exposed file values are not copied into reports.

Built-in coverage is HTTP security-header observations, TLS certificate trust and
negotiated version, and recognizable exposure of explicitly scoped Git/config
paths. Header absence is contextual evidence, not proof of exploitability. The
runner does not invent CVEs, CVSS scores or vulnerability findings from open ports.
Socket timeouts bound individual operations, not a hard wall-clock assessment
budget against a deliberately trickling server. Use process isolation/timeouts
for hostile environments.

Optional installed tools are reported separately. An nmap case pins one approved
IP/TCP port, disables DNS and bounds retries/time. SYN scans can request elevation:

```bash
codelaboon security tool-case --scope scope.json --approve PRINTED_SCOPE_ID --target http://127.0.0.1:8080/ --scan syn
# Review and approve the printed privilege case as below.
codelaboon security import-nmap --scope scope.json --approve PRINTED_SCOPE_ID --source scan.xml --output ports.json
```

The tool's XML goes to its console; save it explicitly before importing. Windows
UAC may use a separate console. Imported XML is size bounded, rejects DTD/entities
and out-of-scope hosts/ports/protocols, and records a source hash. Availability of
Semgrep, Trivy, Nuclei or testssl.sh is capability information only; RC20 does not
claim those tools ran or provide scope adapters for them.

The regression suite exercises real local vulnerable/hardened HTTP responses,
private configuration exposure, redirects, self-signed TLS, request budgets,
expiry, tampering and hostile/out-of-scope XML. This establishes tested coverage
for the shipped assessment checks. It does not establish exhaustive pentesting
coverage of every vulnerability class or every external tool.

## Explicit root and administrator cases

`--permissions full` bypasses supported engine approval gates for that task.
OS elevation is a separate, explicit grant. Linux/macOS use native sudo; Windows
uses native UAC RunAs. No passwords are collected, no sudoers rules are installed,
and neither root login nor passwordless administration is enabled.

```bash
codelaboon privilege create --argv-json '["/absolute/path/to/program","exact-argument"]' --scope "Exact authorized operation" --ttl 300 --timeout 600
codelaboon privilege run PRINTED_FILE --approve PRINTED_CASE_ID --dry-run
codelaboon privilege run PRINTED_FILE --approve PRINTED_CASE_ID
```

Review the generated file before approving it. It freezes argv, working directory,
selected environment, executable checksum, scope, expiry and execution timeout.
Approval requires an interactive terminal, the exact case ID and native OS
consent/authorization. Each case is consumed once and produces a private receipt.
On POSIX, sudo authentication is not cached by this command. Windows execution
requires a native `.exe`; batch/shell arguments require an explicitly reviewed
shell executable. Windows profile ACLs govern files; POSIX files use 0600.

A queued objective can explicitly request an elevated worker:

```bash
codelaboon work add "Perform the specified privileged maintenance" --project . --permissions full --elevation root --scope "Exact operation and allowed files" --check "your-independent-check"
codelaboon privilege worker-case TASK_ID
# Review and approve the generated case with privilege run.
```

Use `--elevation administrator` for Windows terminology. The background service
never elevates itself or approves a case. An approved worker case runs one verified
cycle, with a maximum four planning/build attempts and its overall OS timeout.
It can start an owned authenticated local controller. Recurring elevated swarms
count that cycle once and await a fresh case for another cycle. Failed cases pause
for review. Privileged tools may create root-owned project files; that is normal
OS ownership and requires explicit administration to change later.

This grants actual root/admin process authority, including its child tools.
A scope statement, checksum and supervisor are not an OS sandbox. Approved Python
workers also use their installed package/dependencies; checksums do not seal every
import or defend against a malicious same-account process changing the runtime.
Case receipts are local bookkeeping, not signed remote attestations. Keep the
runtime trusted; use a VM/container or stronger broker when prevention is needed.
Native engine hard restrictions and model/provider refusals can still apply.

## Continuous oversight and model routing

See [continuous supervision](continuous-supervision.md) for worker controls and
file allowlists. Interventions preserve the objective, stop active owned processes
and replan, or pause. Staged files and reversions are included. If Git inspection
is unavailable or exceeds the inspection budget, a configured allowlist pauses.
Windows patterns accept either slash and match without case sensitivity.

Jcode now receives additive native security guidance for new interactive sessions
through its private `JCODE_HOME/prompt-overlay.md`. It preserves native base
instructions and user overlays. Existing native sessions retain their captured
prompt on resume, as specified by [Jcode's prompt configuration](https://github.com/1jehuang/jcode/blob/v0.99.1/crates/jcode-base/src/prompt.rs).
Headless/swarm tasks also carry the immutable scope in their task prompt.

```bash
codelaboon routing status --json
codelaboon routing configure --preset fast
codelaboon routing configure --preset balanced
codelaboon routing configure --preset deep
codelaboon controller-eval
codelaboon doctor --json
```

Routing learns separately for coding/planning/security/general tasks and scoped
provider accounts/endpoints. It observes successful/failed/cancelled calls, streamed
first-token latency, response duration, tool responses and actual reported token
usage. Independent task checks supply acceptance feedback; generated plans do not.
Presets change the bounded speed/acceptance influence on curated health/capability
priors. Sparse models retain those priors. Provider health/tool checks and failover
remain active. Observed trajectory outcomes are not causal quality comparisons or
a guarantee of choosing the most intelligent model. Nonstreaming calls expose
response duration, not measured first-token latency. Paid models are not silently
introduced into free Auto routing.

SQLite observations are bounded (2048 route/task rows, 64 latency samples each;
8192 feedback deduplication records). They contain no prompts, credentials or raw
provider errors. Set `CODELABOON_METRICS=0` to disable learning. This feature adds
no model weights or mandatory runtime dependencies to the thin core.

The optional controller evaluation owns an authenticated loopback model process
and executes synthetic scope fixtures without dispatching user work. It saves an
honest pass/fail report and returns nonzero if any case fails. The installed small
model scored **11/13**, zero false interventions and two missed drift cases;
[recorded results](rc20-controller-evaluation.json) include model/suite hashes and
latencies. The prompt was tuned during development against these regression
cases; this is not a held-out general-intelligence benchmark. The deterministic
file guard passed separately. Model oversight is sampled and fallible, so an
allowlist/isolation remains useful when the allowed file scope is narrow.

The VS Code sidebar adds an offline Diagnostics view showing worker counts,
optional controller readiness/evaluation, routing observations, security tools and
pending privilege cases. Refresh explicitly; no model is loaded by opening it.
`doctor` without `--json` also retains the existing installation/provider checks.

## Platform verification

RC20 portable CI runs the assessment, telemetry, scope and case contracts on Linux,
macOS and Windows. Disposable POSIX CI verifies a harmless real sudo/bootstrap
execution and replay rejection; Windows parses the exact UAC script without
pretending unattended CI can test human consent. Actual Windows UAC approval and
macOS desktop/native engine behavior require manual platform testing. Fedora
native Codex/Jcode full-mode tool fixtures and Jcode security UI/resume/cleanup
were checked locally. No privileged case or real target was run on the user's
machine during development.
