# Agent plan — ticket-095

Implementacja pozostaje ograniczona do `planfile/sync/operations.py` i
`tests/test_sync_scope.py`. Po pomyślnym `backend.update_ticket` zapisuję
referencję `{id: external_id}` przez istniejący helper, aby naprawić rekord
lokalny także wtedy, gdy identyfikator pochodzi wyłącznie ze state file.
Helper zachowuje istniejące `url`, `key` i `repository`. Nie zmieniam backendu,
kontraktu CLI, zależności ani danych zewnętrznych.

Powiązania: lokalny ticket `PLF-074`, GitHub `semcod/planfile#116`.
