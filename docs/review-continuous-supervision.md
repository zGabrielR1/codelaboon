# RC20 adversarial release review

Reviewed policy propagation, native options, process lifetime, root/admin cases,
assessment target boundaries, streaming metrics, queued receipts and claims before
commit. User explicitly authorized public RC20 publication. No privileged action
was authorized for the user's actual host; development never executed one there.

## Findings addressed

- Full agent permissions must not imply root: separate native sudo/UAC cases;
  interactive approval, immutable snapshot/digest, executable hash, expiry,
  timeout, exclusive single-use claim. Sudo timestamp is invalidated. No service
  auto-elevation or privileged system configuration. Background scheduling skips
  elevated tasks and old-service feature negotiation rejects unsupported grants.
- Root receipt ownership must not follow a raced path: use descriptor fchown on
  POSIX. Receipt bookkeeping is not a signed attestation or privilege boundary.
- Recurring elevated swarms must not finish after one cycle or replay a receipt:
  consume case IDs once, count verified cycles and await fresh explicit approval.
- Child environment must not inherit full/profile from another task: explicit
  default isolation. Supported native flags checked on Codex/Jcode fixtures.
- Short tasks need final supervision; repeated review failures/redirects pause.
  Operator controls do not race scheduling state. Terminate owned process trees.
- Staged/reverted files and unavailable Git cannot escape observable allowlists:
  fingerprint both index/worktree/untracked changes; union with baseline; pause
  when inspection is unavailable or capped. Windows path normalization checked.
- A tiny model cannot be advertised as an infallible controller: reproducible
  regression report is 11/13, zero false interventions, two coding drift misses.
  Classification uses fixed bounded corrections, not model-authored new authority.
  Model-independent allowlists pass separately. No OS confinement claim.
- Security must execute/evaluate checks, not just inject instructions: actual local
  HTTP/TLS labs, explicit URL/IP scopes, no redirects, request/time/sample bounds,
  evidence hashes, no body/secret retention, scoped XML tool-result import.
  External tool availability is separate from execution; open ports are not CVEs.
- Interactive Jcode security gap: native additive overlay in private JCODE_HOME;
  preserve base prompt/user preference. Actual UI, resume and server cleanup pass.
- Routing cannot mistake probes/plans/cancelled/empty/error responses for quality:
  task-aware private measured telemetry, independent check feedback, health-probe
  exclusion, bounded storage and learned influence. Corrupt/read-only storage
  cannot break inference. Nonstreaming duration is not claimed as true TTFT.
- Doctor must preserve installation checks and avoid loading models: existing
  doctor retained, JSON diagnostics are offline; sidebar refresh is explicit.

## Evidence and remaining limits

296 unit regressions pass after the final empty-response telemetry refinement;
focused connector checks and thin builds pass. CI remains required before publication. Structural
verification, native full/security Codex/Jcode fixtures, actual security Jcode UI,
connector contract tests and thin artifact builds pass locally. No real targets
or user objectives queued. POSIX native elevation bootstrap/worker and Windows
UAC parser fixtures are gated to disposable CI, not run on the user's machine.
Portable CI must pass before release. Interactive Windows UAC consent is manual
coverage, not simulated as proven. macOS native engine UI is not covered locally.

This is an evaluated modular assessment harness for the shipped HTTP/TLS/exposure
checks and nmap evidence path. It is not certification of every pentesting tool,
all vulnerability categories or hostile same-account/root worker confinement.
Native hard restrictions/provider refusals remain possible. A privileged Python
worker trusts its installed imports, and full/root workers can act before sampled
reviews. Reports clearly distinguish contextual observations from exploitability.
The small-model cases were development regressions, not held-out intelligence data.

Review disposition: proceed to final gates; no blocker hidden by a passing claim.
UI/permission scope is covered by explicit cases and declared platform limits.

CI follow-up: portable contracts pass on Linux/macOS/Windows, including actual
read-only root bootstrap/elevated worker on disposable POSIX runners and Windows
PowerShell parsing. All native gates except OMP80 passed. Its capture shows the
reply while OMP still displays Working, before its asynchronous transcript flush.
Keep the persistence assertion and wait at most ten seconds for the native file;
do not remove the gate or fake a persisted session. Include the JSON evaluation
in source-distribution docs and bound portable job time to five minutes. Changes
reviewed before follow-up commit; release remains gated by the same native checks.
