# Ticket 095: Utrwalać mapowanie GitHub po aktualizacji istniejącego issue

- **ID**: ticket-095
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: użytkownik polecił kontynuować i naprawić
wykryty defekt synchronizacji Planfile/GitHub. Ten ticket implementuje lokalną
część istniejącego planu `PLF-074`, opublikowanego jako
`semcod/planfile#116`.

## Goal and scope

Po udanej aktualizacji istniejącego issue backendowa mapa może być zapisana w
`.planfile/sync/github.state.yaml`, ale fizyczny rekord ticketu nadal zwraca
`sync: {}`. Utrwal referencję backendu w rekordzie po każdej udanej aktualizacji,
zachowaj bogatsze pola `url`, `key` i `repository`, oraz dodaj regresję dla
mapowania state-only. Zakres obejmuje wyłącznie Planfile sync i testy; nie
zmienia polityki merge ani nie wykonuje masowej migracji historycznych ticketów.

## Acceptance criteria

- [x] AC-01: Zakres jest objęty `SESSION_EXECUTION_AUTHORIZATION` użytkownika.
- [ ] AC-02: Udana aktualizacja istniejącego issue utrwala backend-scoped sync
  reference i nie usuwa istniejących pól mapowania.
- [ ] AC-03: Retry pozostaje idempotentny, a mapping cross-repository nadal jest
  odrzucany fail-closed.
- [ ] AC-04: Test regresyjny state-only oraz pełny suite przechodzą; brak
  sekretów w logach i receiptach.
- [ ] AC-05: Managed governance check przechodzi na exact head.

## Planned validation

- `uv run --no-sync pytest -p no:wellmanifest_governance -q tests/test_sync_scope.py tests/test_sync_routing.py tests/test_sync_failure_status.py`
- `uv run --no-sync ruff check planfile/sync/operations.py tests/test_sync_scope.py`
- `uv run --no-sync pytest -p no:wellmanifest_governance -q`
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent`

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
