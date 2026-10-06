# Ticket 193: Validate and repair GitHub issues sync deduplication and projection

- **ID**: ticket-193
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

SESSION_EXECUTION_AUTHORIZATION: użytkownik polecił kontynuować, badać i scalać
zadania w środowisku ~/github/**. Ten ticket realizuje semcod/planfile#87
(walidacja synchronizacji GitHub Issues, deduplikacja alokacji i projekcja mapowania).

## Goal and scope

1. Zabezpieczyć lokalny alokator ID (`_known_ticket_highwater`) przed ponownym
   przydzieleniem opublikowanego markera (np. PLF-066 należącego do semcod/planfile#86),
   uwzględniając mapowania w `.planfile/sync/*.state.yaml`, receipty w
   `.planfile/sync/*.receipts.jsonl` oraz markery deduplikacji w opisach i etykietach.
2. Zapewnić, że rekordy w legacy `backlog.yaml` oraz importowane przez
   `sync github --direction from` zawsze posiadają kanoniczne pole `id`,
   dzięki czemu `store.get_ticket` oraz CLI `ticket list/show` poprawnie je zwracają.
3. Wzbogacić projekcję ticketu o mapowanie z `sync/*.state.yaml` (np. STARTER-601 -> 174),
   aby `ticket show` nie zwracał `sync: {}` przy zapisanym stanie synchronizacji.
4. Zapewnić odporność na ponowną synchronizację: dopasowanie istniejącego ticketu
   po markerze deduplikacji i identyfikatorze bez tworzenia duplikatów.

## Acceptance criteria

- [ ] AC-01: Lokalny alokator ID uwzględnia mapy w `sync/*.state.yaml`, receipty i markery deduplikacji, zapobiegając kolizjom z opublikowanymi numerami.
- [ ] AC-02: Import oraz odczyt legacy rekordów z `backlog.yaml` gwarantuje obecność pola `id`, umożliwiając odczyt przez CLI `ticket list/show`.
- [ ] AC-03: Projekcja ticketu odczytuje mapę z `sync/*.state.yaml`, gdy rekord na dysku nie posiada jeszcze sekcji sync.
- [ ] AC-04: Ponowiona synchronizacja (retry) dopasowuje rekord po markerze i identyfikatorze bez tworzenia duplikatów.
- [ ] AC-05: Testy jednostkowe, pełny zestaw pytest oraz `./project/governance-check.sh` przechodzą na exact head.

## Tracking boundary

This directory contains the reviewed intent and delivery evidence. Optional
participant prose and raw command logs are not required delivery output.
