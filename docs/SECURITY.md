# Security, assumptions and limitations

## Threat model

Untrusted inputs: URL request bodies, requirement text, repository source and
model responses. Trusted boundary: local reviewer, this repository's coordinator
and protected tests, Python runtime and Docker host. The sample runs under a
single local OS user. It is not a multi-tenant agent execution service.

| Threat | Control | Residual risk |
|---|---|---|
| Unauthorized link administration | Required long bearer key, constant-time comparison | Shared key is not per-user identity; TLS required when hosted |
| SQL injection | Parameterized statements | Future queries must follow the same rule |
| Malicious URL / header injection | HTTP(S) only, no credentials/control characters, basic local/private destination checks | Public hostnames may resolve privately; phishing destinations still possible |
| SSRF | Server never fetches a submitted destination | Redirect service can still facilitate phishing; deploy an allowlist/abuse system before public access |
| Denial of service | Body size bound, per-address rate windows, DB timeout | Local WSGI server is not a hardened public HTTP server; proxy timeouts and distributed rate limiting are needed |
| Prompt injection / generated commands | Source treated as data; no model tool executes shell; file allowlist | Model may output malicious Python; pattern checks alone are not a sandbox |
| Untrusted Python execution | Live mode requires Docker, no network, read-only binds, non-root, dropped caps, resource limits, timeout | Containers share a kernel; use hardened disposable VMs for hostile multi-tenant workloads |
| Approval bypass | Binding includes inputs, revision and workspace; stale approval rejected | Local actor name can be impersonated by someone with machine access |
| Lost decisions / crash | Atomic state+journal transaction; explicit snapshot recovery | Lock recovery is manual; machine/disk loss requires backups |
| Audit alteration | Hash-linked events plus checkpoint hashes | Database owner can rewrite the entire chain; external signed anchor/WORM is NOT implemented |
| Secret leakage | .env ignored; credentials not given to test processes; basic secret scan; raw provider error bodies omitted | Prompts/results can still contain confidential material supplied by an operator |
| Unapproved deployment | No deploy command exposed to agents | Manual deployment still needs organizational controls |

## Data handling

Do not provide the company-labelled brief, recruitment emails, personal data or
company source to public model providers unless authorized. Only sanitized generic
requirements and this prototype source should be used. Logs omit API keys,
destination URLs and raw client addresses. The rate-limit database temporarily
stores client addresses as bucket keys; stale entries are purged on later requests.
They are not used for analytics. This is data minimization, not a compliance claim.

Provider privacy, retention and training policies must be checked by the user
before live use. No automatic fallback to an unconfigured provider is permitted.
No shared public API keys are provided. Never put credentials in a repository.

## Release-readiness checklist

- Review source, actual tests, patch and assumptions yourself.
- Confirm both approval gates reference the current revision.
- Verify audit integrity and matching workspace hashes.
- Test live-provider behaviour and Docker isolation on your machine.
- Do not represent the deterministic demo as live inference.
- Do not expose the development server to the internet.
- Before production: SSO/RBAC, TLS, production WSGI server, backups, monitoring,
  retention policy, abuse controls, external audit anchor, dependency/image
  scanning, SAST, load testing, database migrations and security review.

## Runbook: interrupted coordinator

1. Confirm no orchestrator process is still running. A file called
   `.runtime/engineering/coordinator.lock` contains the last coordinator PID.
2. Only if that process has exited, manually remove that **specific** lock file.
   Do not delete the runtime directory or database.
3. Run `python -m orchestrator recover RUN_ID --actor "Your Name"`.
4. Review the recovered journal. `run` restarts from the baseline with a new
   revision and fresh approvals. No previous change or release approval survives.

Snapshots restore only managed source files in the private run workspace. They do
not reverse a database migration, deployed service, external API action or user
files elsewhere. None of those actions are performed by this prototype.
