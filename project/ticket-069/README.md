# ticket-069: Declare Planfile package ownership

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: integration
- **Created**: 2026-09-13

SESSION_EXECUTION_AUTHORIZATION: The user requested autonomous repairs, publication and standards updates. GitHub intake: https://github.com/semcod/planfile/issues/71; repository-scoped Planfile intake PLF-001.

The adopted manifest omits the existing planfile/** package from all workstreams. Declare its application ownership as a prerequisite before changing MCP code. This integration ticket changes only the target-owned manifest; the application repair follows after protected merge.

## Acceptance criteria

- AC-01: The application workstream owns planfile/** alongside its existing paths.
- AC-02: Managed base, pinned hashes, concurrency limits, other tickets and protected publication policy remain intact.
- AC-03: Governance validation and independent protected publication succeed.

Allocation used project/new-ticket.sh with the shared clone lock and high-water mark before branching. The earlier generated 068 collision was preserved externally and never used to create a branch.
