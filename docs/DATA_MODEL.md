# Data model and API behaviour

## Business store

| Table | Primary key | Important fields | Purpose |
|---|---|---|---|
| urls | code | url, created_at, expires_at, disabled, clicks | Link identity and aggregate count |
| idempotency | key | fingerprint, code (FK) | Safe replay of an identical create request |
| daily_clicks | code + day | clicks | UTC daily aggregates, no visitor profiles |
| rate_limits | bucket | started, count | Fixed 60-second request windows, stale rows deleted |

DDL is executed in `Store.__init__`; schema construction is idempotent. SQLite
foreign keys and WAL are enabled. Every redirect uses a write transaction for
read/check/increment and daily aggregation, preventing lost updates. Every create
uses a transaction covering alias allocation and idempotency. Five random-code
collision attempts are allowed before a 503. Reusing an idempotency key with a
different body gives 409. Duplicate destination URLs without an idempotency key
intentionally create independent links.

Expiration is stored as UTC epoch seconds. `ttl_seconds` accepts positive integer
values through one year. Final policy: `now >= expires_at` is expired. Disabled
or expired links return 410 and do not increment analytics. DELETE is idempotent
soft disable; it is not data erasure. Real retention/erasure requires another
approved design. Analytics counts successful redirect requests, not verified
human visits or unique users. All management APIs use one configured bearer key;
there is no tenant separation in this local prototype.

## Engineering store

`runs(id, state)` holds the latest JSON checkpoint. `events(seq, run_id, payload,
previous, hash)` holds the ordered journal. Checkpoint and journal append commit
in one SQLite transaction. The event includes the full checkpoint hash. Loading
a run checks the journal chain and the latest state hash. Artifacts retain their
content in checkpoint outputs as well as versioned JSON files. Approvals include
revision, stage, content binding, actor, note and timestamp.

No migration is necessary for the supplied brownfield boundary fix. Introducing
a schema change would require an additional explicit policy scope, approved
migration and tested rollback; the model cannot silently expand file permissions.
