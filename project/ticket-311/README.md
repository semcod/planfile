# Ticket 311: Pilot 600B bounded urtlog decision slice lookup in planfile per wellmanifest/logs and wellmanifest/llm

- **ID**: ticket-311
- **Owner**: agent:antigravity (`SESSION_EXECUTION_AUTHORIZATION`)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

Pilot the merged `wellmanifest/logs` (`wellmanifest.logs/urtlog-bridge-profile/v1`, `45b9672`)
and `wellmanifest/llm` (`limits.maxDecisionSliceBytes: 600`, `25b3c13`) contracts in
`planfile/urtlog_bridge.py` by adding fail-open `fetch_decision_slice()` enforcing
`128..1024` UTF-8 byte bounds (default `600` B), `ticket_id` single-URN isolation
(`urn:planfile:ticket:<ID>`), and B-tree prefix lookup, verified by offline and live tests
in `tests/test_urtlog_bridge.py`.

## Acceptance criteria

- [ ] AC-01: `fetch_decision_slice()` returns `None` when disabled or when `urtlog` is absent,
      and returns a strictly bounded `<= max_bytes` UTF-8 slice (`<= 600` B default) with
      single-URN isolation when `ticket_id` or `urn` is provided.
- [ ] AC-02: `ruff check planfile/urtlog_bridge.py tests/test_urtlog_bridge.py`, offline/live
      `pytest`, and `./project/governance-check.sh --base origin/main` pass cleanly.
