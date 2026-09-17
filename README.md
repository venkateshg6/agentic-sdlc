# Governed Agentic SDLC — URL Shortener

A runnable engineering-assignment prototype: a URL-shortener REST service plus a
stateful, dependency-driven engineering orchestrator with approvals, controlled
file edits, parallel validation, recovery, and traceable artifacts.

**Start here:** run the tests and replay, then demonstrate the human-operated CLI.
No API key, package download, cloud account or database server is needed for the
offline demonstration. Python 3.11 or 3.12 is recommended.

## Important honesty and scope statement

There are two explicitly labelled modes:

| Mode | What actually happens | What it does not claim |
|---|---|---|
| `fixture` (default) | Bundled deterministic role outputs generate files, run real tests, exercise approvals/state/retries/rollback | This is not live AI reasoning or novel code generation |
| `live` | Configured model performs requirement analysis, architectural planning, independent test generation and code generation; same gates apply | Requires your key and Docker; `evidence/live-compound-multi` contains a completed live run |

The repository's `shortener/` contains the final corrected service. Greenfield
fixture generation intentionally seeds a documented exact-expiration boundary
bug, which the brownfield scenario fixes. This is a demonstration fixture, not a
claim that every generated baseline is defect-free. Protected baseline tests are
extended with a boundary regression test in the enhancement scenario.

## 1. Setup on Windows (VS Code / CMD)

Extract the ZIP and open the `agentic-sdlc` directory in VS Code.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
python -B -m scripts.verify
python -B -m scripts.demo
```

Linux/macOS: use `python3 -m venv .venv`, `source .venv/bin/activate`, and
`cp .env.example .env`. No runtime packages are required; `requirements.txt`
records that intentional dependency choice. Do not upload `.venv` or `.env`.

`scripts.demo` automatically simulates reviewer decisions only for reproducible
fixture replay. Its output says `SIMULATED-DEMO-REVIEWER`; it is not evidence of
an actual human sign-off. Normal CLI execution never auto-approves.

## 2. Run the URL-shortener API

Edit `.env` and set `SHORTENER_API_KEY` to a long random value (at least 16
characters; a 32-byte random token is recommended). Then:

```bat
python -m shortener.api --port 8000
```

In a second CMD window, replace `YOUR_KEY` with your configured token:

```bat
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/api/v1/urls -H "Authorization: Bearer YOUR_KEY" -H "Content-Type: application/json" -H "Idempotency-Key: demo-1" -d "{\"url\":\"https://example.com\",\"alias\":\"demo\",\"ttl_seconds\":3600}"
curl.exe -i http://127.0.0.1:8000/r/demo
curl.exe http://127.0.0.1:8000/api/v1/urls/demo/analytics -H "Authorization: Bearer YOUR_KEY"
curl.exe -X DELETE http://127.0.0.1:8000/api/v1/urls/demo -H "Authorization: Bearer YOUR_KEY"
```

Use `curl` instead of `curl.exe` on Linux/macOS and single-quote the JSON body.
API contract: [docs/openapi.json](docs/openapi.json). There is intentionally no
frontend or public deployment; these were not required by the brief.

## 3. Human-operated greenfield demonstration

```bat
python -m orchestrator new greenfield
python -m orchestrator run RUN_ID
python -m orchestrator inspect RUN_ID
```

Replace `RUN_ID` with the ID printed by `new`. Execution pauses at
`change_approval`. Inspect `completed.implementation.diffs`, requirements,
architecture and test plan. Copy the **entire** `pending.binding` value.

```bat
python -m orchestrator approve RUN_ID --actor "Your Name" --note "Reviewed scope, patch and tests" --binding BINDING_FROM_STATUS
python -m orchestrator run RUN_ID
```

Execution runs tests and security checks concurrently and pauses again at
`release_approval`. Inspect results, copy the **new** binding, then:

```bat
python -m orchestrator approve RUN_ID --actor "Your Name" --note "Reviewed passing tests and release risks" --binding NEW_BINDING
python -m orchestrator run RUN_ID
python -m orchestrator verify RUN_ID
python -m orchestrator export RUN_ID --output evidence/my-greenfield
python -m orchestrator metrics
```

Nothing is deployed. `completed` means approved, review-ready local artifacts.
Workspaces are under `.runtime/engineering/RUN_ID/workspace/`; role outputs are
under `artifacts/vN/`. Changes never touch the orchestrator's source repository.
To serve a generated fixture application, enter its workspace, set the API key
environment variable, and run `python -m shortener.api`. The final top-level app
is easier for the first API demonstration.

## 4. Brownfield and ambiguous scenarios

```bat
python -m orchestrator new brownfield --parent COMPLETED_GREENFIELD_ID
python -m orchestrator run NEW_RUN_ID
```

Follow the two approval gates above. Review the AST symbol inventory and source
hashes. Only `shortener/policy.py` should change from `<` to `<=`; the new boundary
regression test checks that clicks are not counted at expiry.

```bat
python -m orchestrator new ambiguous --parent COMPLETED_GREENFIELD_ID
python -m orchestrator run NEW_RUN_ID
python -m orchestrator clarify NEW_RUN_ID --actor "Your Name" --text "Expiry means now >= expires_at. Return 410 without incrementing clicks. Change only the policy; preserve APIs and database schema."
python -m orchestrator run NEW_RUN_ID
```

The fixture accepts that exact documented answer. It refuses to pretend to
understand arbitrary requirements. Use live mode for alternative wording or
requirements within the bounded URL-shortener module scope.

## 5. Retry, rollback, safe-stop and re-planning

```bat
python -m orchestrator new brownfield --inject once
python -m orchestrator new brownfield --inject always
```

Use the usual `run`/`approve` sequence for each ID. `once` injects one explicitly
labelled validation failure *after actual tests execute*. The engine restores
the snapshot, invalidates downstream results, increments the revision, and
requires new approval. `always` stops after the initial attempt plus two repairs.
These flags are rejected in live mode.

```bat
python -m orchestrator revise RUN_ID --actor "Your Name" --text "NEW REQUIREMENT"
```

Revisions conservatively restore the baseline and invalidate all downstream
outputs and approvals. The audit journal retains the superseded requirement and
output hashes. Fixture mode only implements its bundled requirements; live mode
regenerates analysis, plan, tests and patch for the new input. The lifecycle graph
is fixed for governance; its task content is re-planned. This is not an arbitrary
agent-generated scheduler or an unconstrained coding assistant.

## 6. Optional live-model mode

Configure `.env` with your own OpenAI-compatible provider:

```dotenv
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=YOUR_PRIVATE_KEY
LLM_MODEL=EXACT_MODEL_ID_FROM_YOUR_ACCOUNT
```

No OpenAI or Anthropic subscription is required if your chosen provider supports
the chat-completions interface. Model availability, cost and limits belong to
the provider; no model ID or free quota is assumed. The adapter uses HTTP directly,
so an `openai` Python package is not required. Local compatible providers may use
`http://127.0.0.1:PORT/v1`. Optional fallback is another explicitly configured
provider, not an unannounced switch to deterministic fixtures.
The optional `LLM_FALLBACK_*` settings configure one explicitly selected
secondary provider. The adapter never silently substitutes fixture outputs, and
no model can call shell commands or bypass approval gates.

Install and start Docker Desktop (Linux containers), then:

```bat
docker pull python:3.12-slim
python -m scripts.sandbox_smoke
python -m orchestrator new greenfield --mode live
python -m orchestrator run RUN_ID
```

Use the same human gates. Live-generated Python is never executed on the host:
validation uses a non-root, network-disabled, resource-limited container with
read-only source and protected tests. Missing Docker/provider configuration
causes an auditable safe stop. Do not manually run unreviewed generated code.

The supplied `evidence/live-compound-multi` records one completed live run with
real provider calls, Docker validation, both human approval gates and audit
verification. The HTTP adapter also has mock tests for valid output, malformed
output, retries and provider fallback. CI results must still be verified in your
own GitHub repo.

## Deliverables and reviewer navigation

| Deliverable | Location |
|---|---|
| Working service and orchestration | `shortener/`, `orchestrator/` |
| Architecture, lifecycle and decisions | `docs/ARCHITECTURE.md` |
| Requirement-to-evidence matrix | `docs/TRACEABILITY.md` |
| Three scenario contracts | `scenarios/` |
| Tests and measured evidence | `tests/`, `evidence/` |
| Security, limitations, assumptions | `docs/SECURITY.md` |
| Setup and demo instructions | This README, `docs/DEMO.md` |
| Final engineering summary | `docs/ENGINEERING_SUMMARY.md`, per-run summary output |
| API and data schema | `docs/openapi.json`, `docs/DATA_MODEL.md` |
| References and AI disclosure | `docs/REFERENCES.md`, `AI_USAGE.md` |

## GitHub submission

Create a **private** repository unless the recruiter explicitly permits a public
submission. The company-labelled assignment, email screenshots and keys are
deliberately excluded. From this extracted folder:

```bat
git init
git add .
git status
git commit -m "Implement governed agentic SDLC prototype"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Review staged files before committing. Never include `.env`, `.venv`, databases,
personal emails or the original assignment. Add the evaluator as a collaborator
if private, and share the repository URL. Run live mode, understand the design,
and accurately disclose AI assistance before presenting this as your submission.
