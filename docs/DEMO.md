# Interview demonstration (10–15 minutes)

1. Explain the two products: business URL API and governed engineering control
   plane. Show the traceability matrix and distinguish offline replay from live.
2. Run the test suite and show measured evidence. Start the API and demonstrate
   create -> redirect -> analytics -> disable. Explain 302 vs 410, atomic counts,
   idempotency and the scope of auth.
3. Start a fixture greenfield run. Show architecture/test-design parallel batch,
   explicit graph and generated diff. Demonstrate that no files change before
   your approval. Approve with your name and the current content binding.
4. Resume. Show real test output and parallel security checks. Approve release
   readiness separately; show the final summary. This does not deploy anything.
5. Start brownfield using the completed greenfield parent. Show AST inventory,
   baseline hashes, the exact `<` to `<=` diff and boundary regression test.
6. Start ambiguous. The run pauses before implementation. Answer the documented
   questions and show revision increment, re-planning and subsequent validation.
7. Show `--inject once`: actual tests execute, the explicit simulated fault
   rejects the quality gate, snapshot is restored and new approval is required.
   Show `--inject always` stopping after two repairs, not looping indefinitely.
8. Show `revise` invalidating approvals. Present events, lineage, audit validation
   and metrics. Explain that hash linking is tamper evidence, not immutable storage.
9. If configured, run live mode to demonstrate actual model calls and Docker
   validation. Do not call fixture outputs AI-generated at runtime.
10. Close with limitations and next steps: enterprise identity, durable distributed
    workers, externally anchored audits and production HTTP/security hardening.

## Likely interview questions

**Why not only use an AI coding tool?** The evaluated artifact explicitly
implements orchestration state, governance, recovery and evidence independently
of whichever assistant helped write this repository.

**Why a custom graph rather than LangGraph?** Small, explicit state transitions
make this assignment easy to run offline and review. For distributed execution I
would evaluate an established durable workflow framework against operational needs.

**What if the model hallucinates?** Its response is an untrusted proposal. Parse
and scope gates precede human approval, followed by isolated real tests and
security checks. Those controls reduce risk but do not prove correctness.

**What is your own contribution?** Accurately describe what you reviewed,
configured, tested and changed. AI assistance was used; do not imply otherwise.
