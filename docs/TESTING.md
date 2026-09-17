# Testing strategy and reproducibility

Run `python -B -m scripts.verify`. It executes unittest discovery and records
`evidence/test-results.txt` and `evidence/verification.json` with measured results.
The test runner returns a nonzero exit code on failure.

Test layers:

- Unit: URL validation, expiry policy, aliases, bounded collision handling,
  idempotency, transactional counting and rate-window reset.
- HTTP contract: WSGI request/response status, bearer auth, invalid JSON, body
  limits, redirect Location, analytics, deletion and security headers.
- Integration: real SQLite, concurrent updates, generated workspace tests in a
  child Python process; human gate/resume and complete scenario workflows.
- Orchestration: DAG cycles, path policy, blocked writes, stale approvals,
  parallel batches/join, requirement revision, rollback, bounded retry exhaustion,
  audit and checkpoint tampering, lock exclusion, crash recovery.
- Provider: fake HTTP transport for success, malformed JSON, insecure endpoint,
  transient failure, bounded retries and configured fallback.

`python -B -m scripts.demo` executes all three scenarios plus retry, safe-stop and
re-plan cases. It uses real file generation and real tests. One-shot and persistent
validation faults are explicitly injected after tests run; they are not real
product bugs. The safe-stop run is expected to fail its quality gate and counts
as a failure in reliability metrics. Every replay approval is explicitly simulated.

Live-mode isolation validation: `docker pull python:3.12-slim`, then
`python -m scripts.sandbox_smoke`. This uses bundled code inside the same restricted
container as live validation. It does not call an LLM. The exported
`evidence/live-compound-multi` contains a completed real live scenario with Docker
validation; provider availability and quota remain external runtime dependencies.

CI defines a Python 3.11/3.12 and Windows/Linux matrix and a Docker smoke job.
Configured CI is not evidence of passed GitHub runs until you push and inspect it.
Dependency/image security scanning, stress/soak tests and exhaustive property
testing are future work. No percentage coverage claim is made.

## Metrics

- Success rate = completed / (completed + stopped); waiting runs excluded.
- Retry frequency = workflow repair attempts / all created runs.
- Rollback frequency = snapshot restores / all created runs, including revisions
  and rejected changes. It can exceed 1.
- MTTR = average elapsed time from failed validation to subsequent successful
  validation, for recovered incidents. Unrecovered incidents are not counted.
- End-to-end latency = terminal timestamp minus original creation timestamp.
- Human waiting time is included in both MTTR and latency. Provider retries and
  fallback choices are separately recorded in role outputs; they are not mixed
  into the workflow repair counter.

The small replay sample is functional evidence, not an availability benchmark.
