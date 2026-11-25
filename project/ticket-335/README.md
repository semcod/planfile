# Ticket 335: Defer archived report-only VALLM records during bulk GitHub sync

- **ID**: ticket-335
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-25

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers the requested fix, regression testing and protected publication. Prefact issues #499, #501 and #503 were created during bulk GitHub synchronization of archived Koru VALLM records that have no finding evidence. Keep these report-only records available locally and prevent bulk creation of new issues for them.

## Acceptance criteria

- [x] AC-01. Bulk GitHub synchronization withholds an archived blocked VALLM report-only ticket when it has no existing issue or publication receipt.
- [x] AC-02. Preserve mapped updates, active records, evidence-backed findings and explicit ticket or sprint selection. The dry preview uses the same decision.
- [ ] AC-03. Verify against the native GitHub sync tests and submit the exact commit for protected review.
