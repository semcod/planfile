# Ticket storage and delivery scaling plan

## Objective

Keep Planfile's human-readable, version-control-friendly ticket contract while
making reads and mutations predictable for projects with 1,000-100,000 tickets.
Storage is an implementation detail: Python, CLI, REST, WebSocket, MCP and DSL
clients must continue to observe the same `Ticket` contract.

## Current delivery methods

Planfile currently exposes tickets through:

| Method | Contract | Best use |
|---|---|---|
| Python `Planfile` API | Pydantic `Ticket` objects | In-process automation |
| CLI | Rich table, JSON or YAML | Humans, shell scripts and CI |
| REST API | JSON, full/operational/summary views | Services and dashboards |
| WebSocket | JSON lifecycle events | Live dashboards and controllers |
| MCP server | Structured tool results | Agent/tool integrations |
| DSL | Structured result or JSON/YAML export | Portable automation commands |
| Sync backends | GitHub, GitLab, Jira, OneDev, Markdown | External issue trackers |
| Direct `.planfile` files | YAML snapshots, JSONL journals | Git review, backup and recovery |

The storage backend must not leak into these contracts. In particular, clients
must not need to know which shard or database row contains a ticket.

## Format policy

Use formats according to their role:

- **YAML** for reviewed configuration and durable, human-readable snapshots.
- **JSON** for REST/MCP/WebSocket payloads and rebuildable manifests/caches.
- **JSONL** for append-only operational and evidence journals.
- **SQLite** for an optional indexed operational store or materialized index.
- **Pydantic/JSON Schema** as the canonical ticket validation contract.

CSV is suitable only for import/export. It cannot preserve nested execution,
evidence, history and dependency structures. A binary format such as MessagePack
may be considered for a disposable cache, but not as the only durable source.

## Storage alternatives

| Layout | Point update | Full list | Human review | Operational complexity | Recommendation |
|---|---:|---:|---:|---:|---|
| One YAML per sprint | O(all sprint bytes) | Good with mirror | Excellent | Low | Default compatibility mode |
| One YAML per ticket | Small | Many filesystem operations | Noisy in Git | Medium | Do not use as default |
| Fixed ID-range YAML shards | O(shard bytes) | Good with manifest/cache | Good | Medium | Recommended file backend |
| Creation-day files | O(day bytes) | Requires date index | Good | Medium | Events/archive only |
| Hash/modulo shards | O(shard bytes) | Good | Harder to navigate | Medium | Custom/non-numeric IDs |
| SQLite index + YAML snapshots | Indexed | Indexed | Snapshot remains readable | Medium | Recommended next phase |
| SQLite as primary store | Indexed | Indexed | Requires export | Medium | High-volume local/server mode |
| PostgreSQL/external DB | Indexed/networked | Indexed | Requires export | High | Multi-node service mode |

Mutable fields such as status, priority, queue or assignee must not determine a
ticket's physical location: every lifecycle transition would otherwise require
a two-file move. Numeric ID ranges are stable. IDs without a numeric suffix use
a stable hash bucket.

## Sharded YAML v1

Opt-in configuration:

```yaml
storage:
  backend: sharded-yaml
  shard_size: 100
  custom_shards: 16
```

Layout:

```text
.planfile/sprints/
  current.shards/
    metadata.yaml
    manifest.json
    tickets-000000-000099.yaml
    tickets-000100-000199.yaml
  backlog.shards/
    metadata.yaml
    manifest.json
```

`metadata.yaml` contains sprint fields except `tickets`. Ticket shard files
contain a top-level `tickets` mapping. Each YAML file keeps its self-healing
`.fast.json` mirror. `manifest.json` is written last and contains the generation,
ticket count and shard inventory. A missing or stale manifest is rebuildable
from YAML.

The initial default is 100 tickets per shard. Benchmarks must also cover 250,
500 and 1,000 because larger ticket payloads can make a smaller shard preferable.

## Consistency and migration

All migrations and mutations initially use the existing global store lock.
Writes are atomic per file, and the manifest is committed last. Readers validate
file mtimes independently, so a crash can leave an old manifest but cannot leave
a torn YAML file.

Migration to sharded YAML:

1. Acquire the store lock.
2. Parse and validate all legacy sprint files.
3. Write sharded directories and manifests.
4. Read the shards back and compare ticket IDs and canonical payloads.
5. Atomically switch `storage.backend` in `config.yaml`.
6. Move legacy files and mirrors into a timestamped backup directory.

Migration is refused when target shard directories are non-empty. The current
implementation retains recovery backups but deliberately rejects reverse
migration until a verified reconstruction operation is implemented.

## Daily terminal history

Terminal-ticket rotation is implemented as an active-only operational view with
daily history files and a bounded lookup locator. See
[Daily terminal history](DAILY_TERMINAL_HISTORY.md) for the normative contract,
crash-ordering rules, configuration, and acceptance invariants.

## SQLite options

Two SQLite modes should be evaluated after sharded YAML:

### Materialized index

YAML and JSONL remain durable sources. SQLite stores:

- `ticket_id -> sprint/shard`;
- summary fields used by filters and queues;
- dependency edges;
- file signatures and projection revisions.

The database may be deleted and rebuilt. This preserves direct YAML editing and
substantially accelerates `get`, filtering, dependency resolution and counts.

### Primary operational store

SQLite becomes authoritative for ticket rows, dependencies, history and
evidence. YAML is generated as a snapshot/export. Use WAL mode, transactions,
foreign keys and a schema version. This is preferable above roughly 10,000
frequently mutated tickets or when several local processes write concurrently.

PostgreSQL should be a separate backend for multi-host writers. It should not be
a required dependency for local Planfile use.

## Delivery improvements independent of storage

1. Resolve dependencies from one `ticket_id -> status` map per scheduling pass.
2. Use `min(key=...)` for `next_ticket` instead of sorting all runnable tickets.
3. Apply summary projection, filtering and pagination before full model creation.
4. Return cursor-based REST pages and server-side aggregate counts.
5. Send WebSocket ticket deltas instead of refreshing the entire dashboard.
6. Virtualize the dashboard list.
7. Batch create/update/delete under one transaction and one write per shard.
8. Tail or rotate JSONL journals instead of reading the entire file.

## Implementation phases

### Phase 0: reproducible baseline

- Generate 100, 1,000, 10,000 and 100,000-ticket fixtures.
- Measure cold/warm list, get, next, update, move, bulk create, API summary page,
  process RSS and bytes written.
- Include 24 archives, dependencies, evidence and custom IDs.

### Phase 1: sharded YAML

- Add the sharded YAML engine and manifest.
- Add opt-in migration and rollback APIs.
- Integrate CRUD, sprint load/save, archive and cache signatures.
- Preserve the monolithic default and all public contracts.

### Phase 2: query and batch paths

- Add an ID locator and summary/dependency index.
- Implement real bulk mutations.
- Move pagination/projection ahead of full Pydantic construction.
- Optimize `next_ticket`.

### Phase 3: SQLite materialized index

- Rebuild from YAML/JSONL.
- Compare warm/cold behavior and crash recovery with the file-only index.
- Make it opt-in, then consider enabling it automatically for large stores.

Implemented as an opt-in projection in `.planfile/index/tickets.sqlite3`.
It indexes sprint, status, priority, source, queue, list position and dependency
edges, while retaining complete and summary JSON projections. Source signatures
cover sprint files and evidence journals. Manual edits mark the index stale;
normal point mutations update it incrementally, and corruption triggers a
disposable rebuild.

Management commands:

```bash
planfile storage index-enable
planfile storage index-status
planfile storage index-rebuild
planfile storage index-disable
```

The same operations are exposed through the safe OQL configuration profile:

```bash
planfile dsl run \
  "set config store.storage.backend=sharded-yaml store.storage.shard_size=100"
planfile dsl run "set config store.storage.index=sqlite"
```

See [OQL_CONFIGURATION.md](OQL_CONFIGURATION.md) for transaction rules and the
full configuration coverage matrix.

### Phase 4: SQLite primary and external database SPI

- Define a `TicketRepository` protocol and conformance suite.
- Implement SQLite primary storage.
- Add PostgreSQL only when multi-node operation is required.

## Acceptance targets

Initial targets on a typical developer SSD:

| Operation | 10,000 tickets target |
|---|---:|
| Get by ID, warm | < 10 ms |
| Summary page of 100 | < 100 ms |
| Next runnable ticket | < 200 ms |
| Update one ticket | < 100 ms for 100-ticket shards |
| Bulk create 100 | < 500 ms |

Performance tests should primarily assert structural work (files read, bytes
serialized and number of writes). Wall-clock thresholds belong in a separate
benchmark job to avoid flaky unit tests.

## Initial implementation benchmark

The Phase 1 implementation was measured locally with 5,000 tickets, populated
dependency fields and automatic archive mutations disabled. Run it again with:

```bash
python scripts/benchmark_ticket_storage.py \
  --tickets 5000 \
  --shard-size 100 \
  --shard-size 500
```

One representative run:

| Operation | Single YAML | Shards of 100 | Shards of 500 |
|---|---:|---:|---:|
| Cold full list | 181 ms | 176 ms | 281 ms |
| Warm full list | 55 ms | 71 ms | 63 ms |
| Update populated shard | 400 ms | 23 ms | 50 ms |
| YAML bytes rewritten by update | 1,549,834 | 29,478 | 143,878 |
| Bulk create 50 | 491 ms | 105 ms | 49 ms |
| One-time migration | — | 450 ms | 623 ms |

The result confirms that sharding is a write optimization: a 100-ticket shard
made the measured point update about 17 times faster and wrote about 52 times
fewer YAML bytes. It does not materially improve a full list and can add file
metadata overhead. The next read-focused step should therefore be the SQLite
materialized ID/summary/dependency index, not further reducing shard size.

SQLite index benchmark on the same 5,000-ticket fixture:

```bash
python scripts/benchmark_ticket_index.py --tickets 5000 --shard-size 100
```

| Operation | Without index | SQLite + single YAML | SQLite + shards of 100 |
|---|---:|---:|---:|
| Summary page of 50 | 164-170 ms | 5.1 ms | 8.1 ms |
| Get by ID | — | 5.5 ms | 8.6 ms |
| Point update with current index | — | 414 ms | 32 ms |
| First get after point update | — | 5.7 ms | 8.9 ms |
| One-time index build | — | 338 ms | 351 ms |

The approximately 5 MB database made the measured summary query 20-32 times
faster. Incremental index maintenance avoids the previous full rebuild on the
first read after every mutation. Sharded YAML plus SQLite therefore combines
bounded write amplification with indexed reads.
