# Ticket 285: Prevent healthcheck threadpool starvation and coalesce background SQLite index rebuilds

- **ID**: ticket-285
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-16

SESSION_EXECUTION_AUTHORIZATION: Authorized autonomous diagnosis, implementation, validation, and independent Validator publication (`kontynuuj,scalaj,testuj`) inside canonical worktree `.worktrees/ticket-285--prevent-healthcheck-starvation`, preserving foreign untracked `project/ticket-280/` untouched on primary checkout.

## Goal and scope

1. Serve `GET /health` (`planfile/api/server.py`) directly on the asyncio event loop (`async def health`) so container liveness probes cannot time out when AnyIO's worker threadpool is saturated by concurrent API reads or SQLite index maintenance.
2. Acquire `.rebuild.lock` non-blockingly (`timeout_seconds=0.0`) inside `_repair_ticket_index()`, returning `{"rebuilt": False, "coalesced": True}` on contention, and coalesce `(StoreLockTimeoutError, TicketIndexContentionError)` in `_maintain_ticket_index()` so secondary `--workers` processes and overlapping ticks yield immediately without holding threadpool workers for 10 seconds or emitting false-positive `planfile_store_lock_timeout` warnings.
3. Bound disposable SQLite WAL file retention in `planfile/core/sqlite_index.py` by running non-blocking (`PRAGMA busy_timeout=0`) `PRAGMA journal_size_limit=67108864` and `PRAGMA wal_checkpoint(TRUNCATE)` immediately after `rebuild()` commits (without acquiring write locks inside `_connect()` on reader probes), so full archive rebuilds truncate multi-hundred-megabyte `-wal` files on disk without stalling concurrent readers or writers.

## Acceptance criteria

- [x] AC-01: `GET /health` is an `async def` coroutine handler that responds on the event loop even when the default AnyIO worker threadpool is exhausted.
- [x] AC-02: `_repair_ticket_index()` / `_maintain_ticket_index()` probe `.rebuild.lock` with `timeout_seconds=0.0` and coalesce active rebuilders without blocking for `LOCK_TIMEOUT_SECONDS` or logging spurious lock-timeout warnings.
- [x] AC-03: `SQLiteTicketIndex.rebuild()` enforces a 64 MiB `journal_size_limit` and runs a non-blocking `TRUNCATE` WAL checkpoint post-commit without reader lock contention, covered by regression tests, Ruff, and `./project/governance-check.sh`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
