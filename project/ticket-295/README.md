# Ticket 295: Bound allocator ticket marker scanning

- **ID**: ticket-295
- **Owner**: agent:codex-forge-boundary
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-18

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION from the ecosystem repair and protected merge
request. Bound the scan for ticket ID markers in the sprint highwater cache.
Planfile #398 exposed the slowdown during its operational listing regression.
The allocator path is shared with its current base.

## Acceptance criteria

- [x] AC-01: Scan each identifier run once while preserving marker recognition.
- [x] AC-02: Verify highwater updates still reserve IDs in long descriptions.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Assessment unavailable: managed ticket storage bridge declined the radar assessment.
Advisory only; no execution or merge approval.
<!-- ticket-radar:end -->
