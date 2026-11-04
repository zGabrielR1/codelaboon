# AGENTS — codelaboon

Instruction map — read first (what/how/verify) for codelaboon.

## Five-subsystem index

| Subsystem | Where | Role |
|-----------|-------|------|
| Instruction | `docs/AGENTS.md` | This overview, structure, workflow, constraints |
| State | `PROGRESS.md`, `CURRENTTASK` | Done/in-progress/blocked tracking; objective continuity |
| Feedback | `Makefile`, `scripts/verify.sh` | Executable verification: structure, links, referential integrity |
| Environment | repo layout (self-describing) | Dependency-free; reproducible by construction |
| Tool | agent runtime | Native file/shell access, least privilege |

## Structure

| File | Role |
|------|------|
| `AGENTS.md` | This instruction map (read first) |
| `ARCHITECTURE.md` | System map: layout, lifecycle, subsystems |
| `PROGRESS.md` | State tracker — what is done / in progress / blocked |
| `CURRENTTASK` | Active objective tracker |
| `Makefile` | Feedback subsystem entry points (`make check`, `make lint`) |
| `scripts/verify.sh` | Structural + link-integrity verification |
| `docs/glue.md` | GLUE orchestrator — lifecycle routing, context budgets, telemetry |
| `docs/UniversalMasterPromptDSL.md` | Operator prompt (observe → model → experiment → synthesize) |
| `docs/verifierAgentforUniversalMasterPromptAgent.md` | Adversarial critic / evolution verifier |
| `docs/skillsLoader.md` | External skill loader — imports provider configurations |
| `docs/utils/` | Bootstrap, state resume, continuous improvement, token condensation |

## Workflow

1. Read `CURRENTTASK`, then `AGENTS.md` and `PROGRESS.md` — establish objective and state.
2. Consult `ARCHITECTURE.md` for the system map and `docs/glue.md` for routing/budgets.
3. Execute under the operator (`docs/UniversalMasterPromptDSL.md`): observe → model → experiment → synthesize.
   When the task has no execution oracle and multiple defensible answers, run it as an arena fan-out (`docs/arena.md`) instead of picking one path.
4. Verify with the adversarial critic (`docs/verifierAgentforUniversalMasterPromptAgent.md`).
5. If scores fall below threshold, run `docs/utils/frameworkContinuousImprovement.md` to mutate the operator prompt as a diff.
6. Before ending a session, update `PROGRESS.md`, compact history via `docs/utils/tokenCondensation.md`, and archive obsolete materials.

## Verification commands

```text
Verification commands:
- Structure & links:        make check
- Markdown lint:            make lint          (best-effort; needs markdownlint-cli2)
- Full verification:        make all
```

Rules live in the repo, not in chat/Slack/Confluence/engineers' heads. A new session can start work without asking a human.

## Conventions

- Prompts under `docs/` are treated as source. Evolve them via `docs/utils/frameworkContinuousImprovement.md` diffs, never by casual rewrites.
- Prefer lowercase `.md`. No `.txt` prompts, no uppercase extensions.
- `AGENTS.md` stays a ~100-line map. Push depth into `docs/`.
- Keep one source file per concern; archive obsolete materials in `docs/archive/`.
- Context budgets: 32k recon / 8k worker / 16k adversarial review / 32k synthesis (see `docs/glue.md`). An arena fan-out multiplies the worker budget by n — budgets are per agent, never shared (see `docs/arena.md`).

## Session discipline

SESSION_LAST_TIME: sessions are temporally independent — re-validate, retest, reconfirm the current landscape before trusting stale assumptions.

CONTEXT WRAPPING: record what you did differently from last time as guidance for future runs. Update this file with tips so new runs/evals start from better sources. Do not just repeat what was already done.

VERIFY_BEFORE_COMMIT: run the adversarial critic before any commit or presented result, never after.

## Engineering principles (apply to any harness change)

- Do not preserve backward compatibility. Remove obsolete paths instead of adding compatibility layers or migrations.
- Choose the simplest implementation that fully meets current requirements. Avoid speculative abstraction and indirection.
- Grow in layers: smallest working version first, each capability on top of a product that already works.
- Prefer established, well-maintained tools when they reduce complexity; lean on what is already present.
- Make architectural decisions for the long term; reject stopgaps that must be replaced later.
- Work in runs: one finding per session. When done, record it in `PROGRESS.md` and state the next objective so a fresh session continues without asking a human.
- Self-evolution is scoped: you may update meta-prompts, but only as diffs via `docs/utils/frameworkContinuousImprovement.md`, never by casual rewrite; log in `REG_AST_DELTAS` and re-verify.