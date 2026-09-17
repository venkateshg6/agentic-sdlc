# Requirement-to-implementation and evidence matrix

The company attachment is intentionally not redistributed. This matrix maps the
supplied brief's numbered requirements to the prototype and identifies limits.

| Requirement | Implementation | Evidence / verification | Boundary |
|---|---|---|---|
| 1. Understand requirements and ambiguity | `requirements` role; scenario contract; live analyst; clarification state | ambiguous replay; `test_three_scenarios` | Fixture recognizes bundled ambiguity, not arbitrary natural language |
| 2. Tasks with dependencies and sequencing | `GRAPH`, `graph_valid`, architecture task list; live planner | graph.mmd in every export; graph cycle tests | Lifecycle topology fixed; task content regenerated |
| 3. Brownfield reasoning | Reads baseline source, hashes and AST symbols; records impacted module and data flow | brownfield architecture output and one-file diff | Bounded Python repo; not arbitrary enterprise services |
| 4. Full lifecycle orchestration | requirements, architecture, test design, implementation, validation, docs, release summary | complete scenario journals | Release readiness only, not cloud deployment |
| 4. Non-linear stateful flow | persisted state; clarification, repair and revision paths | resume, recovery, retry tests | Single coordinator |
| 4. Parallel paths and synchronization | independent architecture/test design and tests/security batches | parallel batch events and test | Thread-based parallelism |
| 4. Entry/exit gates | dependencies, schema checks, policy checks, protected tests | unit tests and node hashes | Checks are prototype quality, not certification |
| 4. Context and decision lineage | role inputs, source fingerprints, artifact hashes and revision journal | events.json and state.json | Hash chain has no external trust anchor |
| 4. Human checkpoints | exact-content-bound change and release approvals | CLI runbook; stale binding/rejection tests | Offline replay approvals explicitly simulated |
| 4. Bounded retries | provider attempts and two quality-repair attempts | provider retry tests, retry/safe-stop replays | No unbounded autonomous loop |
| 4. Fallback | explicitly configured secondary model; deterministic documentation generator | `test_retries_and_fallback` | Live fallback transport tested with mocks |
| 4. Rollback and safe-stop | restore named snapshot files, retain journal, stop on exhausted budget | rollback equality and safe-stop tests | No production DB/deployment rollback |
| 4. Policy/security/change control | allowlists, no agent shell, no symlinks, approval bindings, Docker isolation | path guard, Docker-required tests | Docker execution needs local/CI validation |
| 4. Observability and reliability metrics | hash-linked events, atomic checkpoint, metrics CLI | integrity tests; metrics.json | Audit-oriented, not regulator-certified audit storage |
| 4. Dynamic re-planning | requirement revisions invalidate outputs and approvals; validation feedback regenerates patch | replan replay; revision tests | Conservative invalidation, fixed lifecycle topology |
| 5. Engineering outputs | working API, schema/OpenAPI, generated application/tests and role artifacts | source, docs/openapi.json, evidence | Live code quality must be independently reviewed |
| 6. Risk and validation | threat model, protected tests, static checks, risk register | SECURITY.md; test report | Limited static scan, no full vulnerability audit |
| 7. Controlled autonomy | model proposals separated from deterministic mutation/approval controls | approve/reject CLI; write-blocking test | Trusted local machine/reviewer |
| 8. Final engineering summary | per-run summary with requirement, decisions, validation, approvals, risks | summary node; ENGINEERING_SUMMARY.md | Human ownership remains mandatory |
| Working end-to-end prototype | standalone service + CLI orchestration + replay | scripts.verify, scripts.demo | Python 3.11+; locally tested on Linux 3.12 |
| Three scenarios | greenfield, brownfield, ambiguous JSON | separate exports for all three | Known reproducible fixture contracts |
| Setup, testing, limitations, trade-offs | README, TESTING, ARCHITECTURE, SECURITY | reviewer checklist | Windows CI configured, not yet observed here |

## Evaluation evidence is not a guarantee

All requested categories have a concrete implementation or explicitly scoped
prototype treatment. Evaluator acceptance cannot be guaranteed. Before submitting,
run live mode with your own key and Docker, inspect code and generated outputs,
and add genuine human-review evidence. Do not label fixture output as an LLM run,
simulated approvals as real approvals, or this prototype as production-certified.
