# Run engineering report

Run: `01f7c686fcf9` | Scenario: greenfield | Mode: live
Status: **completed** | Revision: 1

## Requirement

Build a URL shortener with authenticated creation, aliases, idempotency, public redirects, click analytics and basic expiry handling.

## Decisions and plan

See graph.mmd and state.json for exact tasks, dependencies, role outputs and hashes.
Snapshot rollback protects the managed workspace. Change and release approval are separate.

## Changes

- `shortener/__init__.py`
- `shortener/api.py`
- `shortener/policy.py`
- `shortener/service.py`

## Validation

Final validation passed: True
Repair retries: 0; snapshot restores: 0

```text
test_alias_uniqueness (test_generated.ShortenerAPITest.test_alias_uniqueness) ... ok
test_clicks_are_recorded_atomically (test_generated.ShortenerAPITest.test_clicks_are_recorded_atomically) ... ok
test_create_invalid_url (test_generated.ShortenerAPITest.test_create_invalid_url) ... ok
test_create_requires_auth (test_generated.ShortenerAPITest.test_create_requires_auth) ... ok
test_disable_and_expired_behavior (test_generated.ShortenerAPITest.test_disable_and_expired_behavior) ... ok
test_health_endpoint (test_generated.ShortenerAPITest.test_health_endpoint) ... ok
test_idempotent_creation (test_generated.ShortenerAPITest.test_idempotent_creation) ... ok
test_management_requires_auth (test_generated.ShortenerAPITest.test_management_requires_auth) ... ok
test_successful_creation_and_redirect (test_generated.ShortenerAPITest.test_successful_creation_and_redirect) ... ok
test_ttl_expiry (test_generated.ShortenerAPITest.test_ttl_expiry) ... ok
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
Ran 29 tests in 2.153s

OK

```

## Approval evidence

- change_approval: G venkatesh; revision 1; Reviewed live-generated implementation, requirements, architecture, tests, and file scope
- release_approval: G venkatesh; revision 1; Reviewed Docker test results, security checks, documentation, and release risks

## Assumptions, risks and limitations

Local trusted reviewer, no deployment, single coordinator. Fixture output is deterministic replay, not live inference.
Replay approvals are simulated and labelled. Live provider calls and Docker validation are recorded in this report.
Hash-linked local audit is not externally immutable. Source rollback does not restore production databases.
See repository docs/SECURITY.md and docs/TRACEABILITY.md for full limits and acceptance mapping.
