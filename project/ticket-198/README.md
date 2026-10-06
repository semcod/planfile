# Ticket 198: Safe scalar sprint and legacy tasks ticket extraction

- **ID**: ticket-198
- **Owner**: Tom Softreck
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Safely interpret sprint documents with scalar sprints and top-level tasks lists, avoiding AttributeError (`'str' object has no attribute 'get'`) and silent record loss during CLI and API ticket operations.

## Acceptance criteria

- [x] AC-01: Handle scalar sprint plus tasks-list input without AttributeError or silent record loss.
- [x] AC-02: Fallback to top-level tasks list in `_tickets_from_sprint_data` and `_tickets_from_sprint_file` when tickets mapping is absent or empty.
- [x] AC-03: Guard sprint roots in `Store.list_tickets`, `Store.ticket_records`, `Store.delete_tickets_bulk`, and `Store.migrate_to_sharded_yaml` against scalar or non-dict sprint fields.
- [x] AC-04: Comprehensive regression tests pass and governance check exits 0.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
