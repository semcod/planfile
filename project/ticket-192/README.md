# Ticket 192: Poll remote changes periodically in explicit inbound-only watch mode

- **ID**: ticket-192
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-05

SESSION_EXECUTION_AUTHORIZATION: continue repairs, tests and protected publication. PLF-112 / GitHub #234 is the bounded inbound-only child of PLF-111 / #233.

## Acceptance criteria

- [x] AC-01: Explicit from watcher observes remote-only closure and new ticket import while local YAML stays unchanged, using existing bounded polling interval.
- [x] AC-02: Preserve startup, failure backoff, provider cooldown, configured integrations, once failure and default outbound-only behavior; retain concurrent local changes.
- [ ] AC-03: Focused/full suite, managed checks, independent exact-head protected publication and installed readback pass.

Parent #233 stays open for safe bidirectional conflict/reopening semantics and observed deployed coverage. No daemon or vendor executor activation is included.

Initial unaccepted XS classification was invalid for the recorded 30-minute estimate; corrected to S before the first successful gate. Confirmed prerequisite PLF-113 / #235: provider reads were swallowed as successful empty imports. AC-02 includes honest failure propagation before periodic polling; three implementation files, no public API or dependency change.

Validation: corrected baseline regression suite: 9 failed / 2 passed against exact accepted-base source; implementation focused adapter/watch suite: 39 passed. Ruff on all three implementation files passed. Full suite and protected publication pending.

Full suite: 1095 passed, 6 skipped, 1 existing PyGithub deprecation warning (129.16s). Managed gate: 0 errors / 0 warnings. Independent protected exact-head review/merge and installed readback remain pending; ticket stays IN_PROGRESS / PUBLICATION.
