# Ticket 096: Bound auto_discover to repository boundary

- **ID**: ticket-096
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: użytkownik potwierdził kontynuowanie kolejnego
niezależnego bounded ticketu po walidacji i publikacji napraw synchronizacji.

## Goal and scope

`Planfile.auto_discover()` musi respektować granicę bieżącego repozytorium Git.
Gdy zagnieżdżone repozytorium nie ma własnego store, odkrywanie nie może
odziedziczyć `.planfile` z repozytorium nadrzędnego ani zapisać ticketów w
nieprawidłowym projekcie. Zakres obejmuje wyłącznie wrapper discovery i test
regresji; nie zmienia synchronizacji ani istniejących konfiguracji.

## Acceptance criteria

- [x] AC-01: Zakres jest objęty `SESSION_EXECUTION_AUTHORIZATION`.
- [x] AC-02: Discovery zwraca store z bieżącego repozytorium albo inicjalizuje
  je lokalnie, nigdy nie wybiera nadrzędnego repozytorium.
- [x] AC-03: Test z nadrzędnym i zagnieżdżonym repozytorium wykrywa regresję,
  a istniejące testy discovery pozostają zielone.
- [ ] AC-04: Full suite, Ruff i managed governance przechodzą na exact head.

## Planned validation

- `uv run --no-sync pytest -p no:wellmanifest_governance -q tests/test_repository_routing.py tests/test_project_paths.py` — passed.
- `uv run --no-sync ruff check planfile/__init__.py tests/test_repository_routing.py` — passed.
- `uv run --no-sync pytest -p no:wellmanifest_governance -q` — 601 passed, 6 skipped.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent` — GOV-PASS.

## Tracking

Powiązany zakres: `semcod/planfile#92`. Nie wykonuje masowej migracji ani
publikacji bez protected Validatora.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
