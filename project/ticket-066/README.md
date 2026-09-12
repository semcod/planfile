# Ticket 066: Cheaper global evidence revision

- **Status**: DONE
- **Workflow state**: DONE

SESSION_EXECUTION_AUTHORIZATION: optimize, test, push and protected merge, requested by the owner on 2026-09-11.

Scope: `PlanfileStore._evidence_revision()` runs on every ticket list response signature and every SQLite index freshness check. On the local Subactor workspace (4,454 per-ticket evidence files) `Path.glob` plus `Path.stat` took ~125 ms per call; a single `os.scandir` pass returns the identical tuple in ~32 ms (measured inside the running planfile 0.1.124 container, 10-call average). No change to what the signature contains, its ordering, or cache invalidation semantics.

Acceptance: a regression test proves the new listing equals the previous `sorted(glob("*.jsonl"))` + `stat()` result, including hidden files, a directory named `*.jsonl`, a dangling symlink, other extensions and a missing directory, and that an append changes the revision. Full test suite passes.
