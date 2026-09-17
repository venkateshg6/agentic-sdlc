# Run engineering report

Run: `e3806ffd259f` | Scenario: ambiguous | Mode: fixture
Status: **completed** | Revision: 2

## Requirement

Make expiration handling more reliable.

## Decisions and plan

See graph.mmd and state.json for exact tasks, dependencies, role outputs and hashes.
Snapshot rollback protects the managed workspace. Change and release approval are separate.

## Changes

- `shortener/policy.py`

## Validation

Final validation passed: True
Repair retries: 0; snapshot restores: 1

```text
test_exact_boundary (test_boundary.BoundaryTests.test_exact_boundary) ... ok
test_expired_click_not_counted (test_boundary.BoundaryTests.test_expired_click_not_counted) ... ok
test_no_expiry (test_generated.GeneratedAcceptance.test_no_expiry) ... ok
test_past_expiry (test_generated.GeneratedAcceptance.test_past_expiry) ... ok
test_auth (test_shortener.APITests.test_auth) ... ok
test_health_and_headers (test_shortener.APITests.test_health_and_headers) ... ok
test_http_flow (test_shortener.APITests.test_http_flow) ... ok
test_json_and_body_limits (test_shortener.APITests.test_json_and_body_limits) ... ok
test_rate_limit_http (test_shortener.APITests.test_rate_limit_http) ... ok
test_weak_key_refused (test_shortener.APITests.test_weak_key_refused) ... ok
test_alias_conflict (test_shortener.ShortenerTests.test_alias_conflict) ... ok
test_bad_urls (test_shortener.ShortenerTests.test_bad_urls) ... ok
test_collision_exhaustion (test_shortener.ShortenerTests.test_collision_exhaustion) ... ok
test_collision_retry (test_shortener.ShortenerTests.test_collision_retry) ... ok
test_concurrent_clicks (test_shortener.ShortenerTests.test_concurrent_clicks) ... ok
test_create_redirect_analytics (test_shortener.ShortenerTests.test_create_redirect_analytics) ... ok
test_disable (test_shortener.ShortenerTests.test_disable) ... ok
test_expiration (test_shortener.ShortenerTests.test_expiration) ... ok
test_idempotency (test_shortener.ShortenerTests.test_idempotency) ... ok
test_invalid_fields (test_shortener.ShortenerTests.test_invalid_fields) ... ok
test_not_found (test_shortener.ShortenerTests.test_not_found) ... ok
test_rate_limit_and_reset (test_shortener.ShortenerTests.test_rate_limit_and_reset) ... ok
test_sql_parameterization (test_shortener.ShortenerTests.test_sql_parameterization) ... ok

----------------------------------------------------------------------
Ran 23 tests in 2.370s

OK

```

## Approval evidence

- change_approval: SIMULATED-DEMO-REVIEWER; revision 2; Automated replay approval; not a human sign-off
- release_approval: SIMULATED-DEMO-REVIEWER; revision 2; Automated replay approval; not a human sign-off

## Assumptions, risks and limitations

Local trusted reviewer, no deployment, single coordinator. Fixture output is deterministic replay, not live inference.
Replay approvals are simulated and labelled. Live model and Docker results must be verified separately.
Hash-linked local audit is not externally immutable. Source rollback does not restore production databases.
See repository docs/SECURITY.md and docs/TRACEABILITY.md for full limits and acceptance mapping.
