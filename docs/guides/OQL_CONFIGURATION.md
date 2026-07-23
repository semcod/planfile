# OQL configuration profile

## Scope

Planfile now has one typed configuration contract shared by Python, the CLI,
REST, WebSocket, MCP and the natural-language DSL. A successful write records a
canonical `SODL/1` operational event whose `oql` field is `config.set`.

The two concepts are related but distinct:

- the user-facing command is a DSL/OQL operation such as
  `set config store.archive.enabled=false`;
- `SODL/1` is the append-only, canonical audit representation written to
  `.planfile/events/operations.jsonl`.

All entry points call `ConfigurationManager`; none of them writes a storage flag
directly. This matters for settings which require work, such as a verified
storage migration or rebuilding the SQLite index.

## Entry points

### Dedicated CLI

```bash
planfile config list --json
planfile config show store.storage.backend
planfile config set store.archive.max_current_tickets 500
planfile config set runtime.enabled.topology false
planfile config set store.storage.index sqlite --dry-run
planfile config set integrations.github.repo owner/project
```

CLI values are parsed as YAML scalars or collections. Use `--dry-run` to run all
validation without writing configuration, migrating data or appending an event.
Every listing returns a `cfg_...` revision. Use
`--if-revision cfg_...` to prevent overwriting a concurrent change.

### Portable DSL/OQL

```bash
planfile dsl run "list config" --format json
planfile dsl run "show config store.archive.enabled"
planfile dsl run \
  "set config store.archive.enabled=true store.archive.max_current_tickets=500"
planfile dsl run \
  "set config store.storage.backend=sharded-yaml store.storage.shard_size=100"
planfile dsl run "set config store.storage.index=sqlite mode=dry-run"
planfile dsl run \
  "set config integrations.github.sync.create_issues=false if_revision=cfg_..."
```

The same command string can be sent to:

- `POST /dsl`;
- `ws://HOST/ws?project_path=...`;
- the MCP `planfile_dsl` tool;
- `DSLExecutor(project_path).run(...)`.

### REST configuration API

```bash
curl http://localhost:8000/api/config
curl http://localhost:8000/api/config/value/store.storage.backend
curl -X PATCH http://localhost:8000/api/config \
  -H 'Content-Type: application/json' \
  -H 'If-Match: "cfg_..."' \
  -d '{
    "changes": {"store.archive.max_current_tickets": 500},
    "mode": "apply",
    "actor": "deployment",
    "reason": "large queue"
  }'
```

The Python facade is available as `Planfile(".").configuration`, with `list()`,
`show(path)`, `revision()` and
`set_many(changes, expected_revision=..., mode=..., actor=..., reason=...)`.
REST `GET` responses include the same revision as an `ETag`; a stale
`If-Match` write returns HTTP 409.

## Coverage matrix

| Configuration area | Read | Write through OQL | Storage/source | Policy |
|---|---:|---:|---|---|
| Project display name | Yes | Yes | `.planfile/config.yaml` | Non-empty text |
| New ticket ID prefix | Yes | Yes | `.planfile/config.yaml` | Validated, affects only future allocations |
| `next_id` allocator | Reason only | No | `.planfile/config.yaml` | Allocator-owned; direct writes can duplicate IDs |
| Archive switch and limits | Yes | Yes | `.planfile/config.yaml` | Typed and atomically batched |
| Archive terminal statuses | Yes | Yes | `.planfile/config.yaml` | Closed terminal-status set |
| YAML backend | Yes | Yes | `.planfile/config.yaml` + sprint data | `single-yaml → sharded-yaml` invokes verified migration |
| Shard size and custom buckets | Yes | Yes before migration | `.planfile/config.yaml` | Existing shards require a future reshard operation |
| SQLite materialized index | Yes | Yes | config + `.planfile/index/tickets.sqlite3` | Enable builds; DB remains disposable |
| Runtime-context feature switches | Yes | Yes | `.koru/runtime-context.json` | Fixed boolean allowlist |
| Runtime-context overrides | Yes | Yes | `.koru/runtime-context.json` | JSON values; secret-like paths rejected |
| Integration endpoints/projects | Redacted | Yes | `.planfile/integrations.oql.planfile.yaml` | Typed non-secret allowlist |
| Integration sync policy/maps | Redacted | Yes | `.planfile/integrations.oql.planfile.yaml` | GitHub/GitLab/Jira `sync.*`, secret-like paths rejected |
| Integration credentials | Redacted | No | existing files/environment | Never persisted through OQL |
| Environment configuration | Policy only | No | process environment | Deployment/process owned |
| Sync checkpoints | No | No | `.planfile/sync/*` | Runtime state, not configuration |
| Leases and evidence | No | No | coordination/journal files | State or append-only evidence |
| Root strategy `planfile.yaml` | Separate API | No | `planfile.yaml` | Domain plan, not system configuration |

`list config` never expands `.env` variables and redacts secret-like integration
keys. OQL writes integration values to one deterministic overlay,
`.planfile/integrations.oql.planfile.yaml`, loaded after legacy and ticket
configuration. Existing source files are left byte-identical; the result lists
which earlier definitions are shadowed by the overlay. A request to set
`password`, `token`, `secret`, `api_key`, credentials, usernames or private-key
overrides is rejected. Secrets should be injected through the process
environment or a dedicated secret manager.

## Transaction and migration rules

- Multiple ordinary settings in the same `store` or `runtime` scope are
  validated first and then written atomically.
- A batch cannot mix `store.*`, `runtime.*` and `integrations.*`; use separate
  commands so failure cannot leave a cross-file half-commit.
- Every apply path rechecks the expected revision while holding the store lock.
  Ticket ID allocation and operational events do not alter the configuration
  revision.
- An index transition is isolated because enabling it also builds the database.
- A backend transition may include `shard_size` and `custom_shards`, but no
  unrelated settings.
- Migration writes and reads back every shard before switching the backend.
  Legacy YAML and fast mirrors move to a timestamped recovery directory.
- Reverse migration and in-place resharding are deliberately rejected until
  dedicated, verified operations exist.
- Applied changes append a non-replayable `config.set` operational event.
  Dry runs and no-op writes append nothing.

## Storage and format recommendation

For most repositories:

1. Keep YAML as the durable, reviewable source.
2. Use 100-ticket fixed ID-range shards when point writes to a large sprint
   dominate. Test 250 and 500 for unusually small tickets.
3. Enable SQLite when ID lookup, filtering, dependency checks or paged summaries
   dominate. It is a rebuildable projection, not the only copy.
4. Keep JSON for API payloads and manifests, JSONL for append-only operations and
   evidence, and Pydantic/JSON Schema for validation.
5. Use a SQLite primary store only for a future high-write local/server mode.
   Use PostgreSQL only when multi-host writers and server transactions justify
   its operational cost.

Do not partition mutable tickets by status, priority or assignee. Numeric ID
ranges are stable; creation-day files are better suited to immutable events and
monthly archives than to active ticket state.

## Next implementation candidates

The following additions remain useful:

1. Authorization policy separating configuration readers, ordinary writers and
   storage-migration operators.
2. Dedicated reset/removal, `reshard` and `sharded-yaml → single-yaml`
   recovery operations.
3. A versioned `TicketRepository` SPI and conformance suite before SQLite
   primary or PostgreSQL backends are introduced.

## Verification

`tests/test_oql_configuration.py` covers parsing, redaction, excluded allocator
state, atomic rejection, dry run, runtime persistence, secret rejection,
configuration revisions, REST ETags, deterministic integration overlays,
SQLite build/disable, verified sharded migration, MCP, CLI and REST. Storage
conformance and performance coverage remains in:

- `tests/test_sharded_yaml_storage.py`;
- `tests/test_sqlite_ticket_index.py`;
- `scripts/benchmark_ticket_storage.py`;
- `scripts/benchmark_ticket_index.py`.
