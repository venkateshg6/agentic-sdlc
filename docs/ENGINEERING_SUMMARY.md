# Final engineering summary

## Outcome

Delivered a local, dependency-light URL-shortener service and a governed SDLC
prototype. The coordinator supports explicit dependencies, parallel independent
work, synchronization, persisted checkpoints, approval-bound changes, protected
tests, rollback, bounded repair, fallback provider integration, safe stopping,
revision-driven re-planning, artifact lineage and measured run metrics.

## Plan and rationale

The scope prioritizes inspectable control flow over UI complexity. Four business
modules provide a realistic service, with a policy seam supporting a small but
genuine brownfield fix. The fixed lifecycle graph governs model-generated task
content. Human checkpoints are distinct from agent execution. Offline replay
makes all controls demonstrable without sharing API credentials or relying on
model availability during an interview.

## Engineering artifacts

Source modules, API contract, data model, independent tests, CI definition,
scenario contracts, per-revision role outputs, input/output hashes, diffs, audit
journals, architecture decisions, security analysis and setup/demo runbooks are
included. `evidence/verification.json` contains the actual local test results;
`evidence/replay/summary.json` contains scenario results and metrics. Each completed
run also generates its own final summary with decisions, approvals and validation.

## Validation and ownership

The delivered fixture replay executes real source changes and subprocess tests.
Human decisions in replay are labelled simulated. The normal CLI requires an
explicit actor, rationale and current binding at each approval. Automated tests
exercise both successful and failed paths, integrity controls and persistence.
Live-model adapter tests use mock transport. A completed live inference and Docker
run is included under `evidence/live-compound-multi`; it is still a local prototype
demonstration, not production certification. See TESTING.md.

## Assumptions and limitations

- Trusted local reviewer, Python 3.11+, one coordinator per state root.
- The model is not trusted to approve, deploy, choose commands or alter tests.
- Fixture mode is a replay, not a substitute for actual AI reasoning.
- Brownfield scope is a policy bug fix, not general enterprise modernization.
- Snapshot rollback does not reverse external systems or database migrations.
- Hash-linked local logs are not externally immutable or regulator-certified.
- WSGI development server and SQLite are not claims of public production scale.
- CI behaviour must be validated in the target repository after push.

## Recommended handoff

Read the implementation and rehearse the three scenarios. Configure a permitted
provider, run live mode in Docker, export your genuine human-reviewed evidence,
and share a private repository without secrets or the original company document.
Explain these trade-offs explicitly rather than presenting the prototype as a
fully production-hardened autonomous software factory.
