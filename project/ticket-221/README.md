# ticket-221: Defer human and skip operator tickets in Planfile next_ticket and next_tickets

- **Status**: IN_PROGRESS
- **Workstream**: `application`
- **Classification**: `BUG` / `P1` / `health`
- **Agent**: `agy`

## Problem Statement

When Koru's native Planfile SDK fast path calls `Planfile.next_ticket()` or `Planfile.next_tickets()`:
1. Tickets with `executor.kind == "human"` and `execution.queue == "operator"` (such as `PLF-255` in `semcod/tagi` and `PLF-2674` in `semcod/koru`) were not skipped by `Planfile._autonomy_skip` when `queue=None`, stalling the queue in `waiting_input` instead of allowing `idle` discovery.
2. High-priority tickets without a machine executor (`executor=None` or `executor.kind="human"`, such as `PLF-17307` in `semcod/koru`) were returned ahead of machine-runnable tickets (`executor.kind="llm"`, such as `PLF-104..PLF-118`), halting the autonomous queue on `waiting_input` while runnable machine work remained.

## Solution

- Updated `Planfile._autonomy_skip` and `Planfile.runnability_skip_reason` in `planfile/__init__.py` to return `"actor:human"` for `executor.kind == "human"` tickets in the `operator` queue (or carrying the `operator` label) unless `queue == "operator"` is explicitly requested.
- Added `Planfile._is_human_or_missing_executor` and wired it into `Planfile.next_ticket`, `Planfile.next_tickets`, and `Planfile.runnable_report` so machine-runnable tickets (`0`) always precede human or unspecified executor tickets (`1`).

## Acceptance Criteria

- **AC-01**: `Planfile.next_ticket()` and `Planfile.next_tickets()` skip `operator` human tickets during default drain and rank machine-runnable tickets ahead of human/unspecified executor tickets.

## Validation Evidence

- `pytest -q tests/test_next_ticket_autonomy_filter.py tests/test_priority_weighting.py` (`14 passed`)
- `ruff check planfile/__init__.py tests/test_next_ticket_autonomy_filter.py` (`All checks passed!`)
- `./project/governance-check.sh` (`GOV-PASS`)
