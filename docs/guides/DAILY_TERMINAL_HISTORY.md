# Daily terminal history

Status: implemented

## Intent

Keep the operational Planfile dataset small by moving work that no longer needs
execution out of `current`, without losing auditability, dependency semantics,
or compatibility with existing archives.

## Contract

When a ticket enters `done`, `canceled`, `failed`, or `blocked`, Planfile moves
it to `.planfile/sprints/history-YYYY-MM-DD.yaml`. The UTC date comes from
`execution.finished_at`, then `updated_at`, then `created_at`. By default,
`store.archive.retain_terminal_days: 0` rotates terminal work immediately. A
positive value retains that many UTC calendar dates, including today. Existing
count and byte thresholds remain an additional safety boundary.

Rotation holds the global mutation lock. It writes all history destinations,
then `.planfile/index/history-locations.yaml`, and only then removes records from
`current`. An interrupted write may temporarily duplicate a ticket, but a retry
must repair the duplicate and must never lose the ticket. The locator lets point
lookups, dependency resolution, and stale-snapshot protection read the exact
daily file instead of parsing all history.

The API runs an idempotent sweep on startup and once per UTC date, in addition
to mutation-time rotation. Normal dashboard and watcher reads use
`sprint=current`; callers use `sprint=all` only for an intentional full-history
query. Existing `archive-YYYY-MM.yaml` files remain readable.

## Acceptance requirements

- Planfile MUST keep non-terminal tickets in their active sprint and MUST NOT
  move them during terminal-history maintenance.
- Planfile MUST group terminal tickets by completion date for both single-YAML
  and sharded-YAML backends.
- Rotation MUST preserve ticket IDs, ticket history, evidence, and dependency
  semantics.
- A stale bulk snapshot MUST NOT resurrect a ticket already owned by history.
- An active-ticket lookup MUST read `current` before reading any history file.
- Existing monthly archive files MUST remain readable.
- The startup and daily maintenance task MUST be cancellable during API
  shutdown and MUST report failures without terminating the server.
