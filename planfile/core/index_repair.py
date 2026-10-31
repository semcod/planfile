"""Bounded reconciliation of canonical writes made during an index scan."""

from __future__ import annotations

import time

from planfile.core.fastio import read_yaml_fast

# Never turn finalization into a second archive scan under the writer lock.
MAX_REPAIR_BYTES = 16 * 1024 * 1024
MAX_REPAIR_TICKETS = 1024
MAX_REPAIR_SECONDS = 2.0


class _RepairBudgetExceeded(Exception):
    pass


def reconcile_index(store, index, built_signature: tuple) -> dict | None:
    """Make a scanned projection current using only a small changed-source set.

    A rebuild may have observed either version of any changed source. Refresh
    every ID in those sprints (including IDs no longer present) and every
    changed evidence journal, resolving canonical location precedence again.
    Writers use the same mutation lock, so the final signature and payloads
    describe one state. Unknown locator drift or a large delta stays stale.
    """
    with store.mutation_lock():
        started = time.monotonic()
        target = store._ticket_index_signature()
        if target == built_signature:
            return index.status(target) | {"rebuilt": True}
        if target[2] != built_signature[2]:
            return None

        consumed = 0
        charged = set()
        snapshots = {}

        def check_budget():
            if time.monotonic() - started > MAX_REPAIR_SECONDS:
                raise _RepairBudgetExceeded

        def charge(path):
            nonlocal consumed
            check_budget()
            if path not in charged:
                charged.add(path)
                try:
                    consumed += path.stat().st_size
                except FileNotFoundError:
                    pass
                if consumed > MAX_REPAIR_BYTES:
                    raise _RepairBudgetExceeded

        def tickets(sprint):
            if sprint not in snapshots:
                for path in store._sprint_storage_files(sprint):
                    charge(path)
                if store._uses_sharded_storage():
                    snapshot = store._sharded_storage().load_sprint(sprint)
                else:
                    snapshot = read_yaml_fast(store._sprint_file(sprint)) or {}
                root = snapshot.get("sprint", snapshot)
                snapshots[sprint] = root.get("tickets") or {}
                check_budget()
            return snapshots[sprint]

        def changed_keys(before, after):
            return {key for key in before.keys() | after.keys()
                    if before.get(key) != after.get(key)}

        try:
            before_sources = {(row[0], row[1]): row[2:] for row in built_signature[0]}
            after_sources = {(row[0], row[1]): row[2:] for row in target[0]}
            changed_sprints = {key[0] for key in changed_keys(before_sources, after_sources)}
            before_evidence = {row[0]: row[1:] for row in built_signature[1]}
            after_evidence = {row[0]: row[1:] for row in target[1]}
            ids = {name.removesuffix(".jsonl")
                   for name in changed_keys(before_evidence, after_evidence)}
            for sprint in sorted(changed_sprints):
                ids.update(tickets(sprint))
                # Read identities only, never deserialize historical payloads.
                with index._connection() as connection:
                    rows = connection.execute(
                        "SELECT id FROM tickets WHERE sprint=? LIMIT ?",
                        (sprint, MAX_REPAIR_TICKETS + 1),
                    ).fetchall()
                ids.update(row["id"] for row in rows)
                if len(ids) > MAX_REPAIR_TICKETS:
                    raise _RepairBudgetExceeded
            if len(ids) > MAX_REPAIR_TICKETS:
                raise _RepairBudgetExceeded
            charge(store._history_locations_path)
            locations = store._history_locations()
            all_sprints = store._all_sprint_ids()
            records = []
            deleted = []
            for ticket_id in sorted(ids):
                check_budget()
                candidates = dict.fromkeys(
                    ["current", *([locations[ticket_id]] if ticket_id in locations else []),
                     *all_sprints]
                )
                located = None
                for sprint in candidates:
                    raw = tickets(sprint).get(ticket_id)
                    if raw is not None:
                        located = sprint, raw
                        break
                if located is None:
                    deleted.append(ticket_id)
                    continue
                sprint, raw = located
                charge(store._ticket_evidence_path(ticket_id))
                if isinstance(raw, dict) and "id" not in raw:
                    raw = dict(raw, id=ticket_id)
                model = store._ticket_from_data(raw)
                if model is None:
                    deleted.append(ticket_id)
                else:
                    records.append(store._ticket_index_record(model, sprint))
            check_budget()
            # External file editors may not honor the canonical mutation lock.
            if store._ticket_index_signature() != target:
                return None
            index.apply(upserts=records, deletes=deleted, signature=target)
            if store._ticket_index_signature() != target:
                return None
            return index.status(target) | {"rebuilt": True, "reconciled": len(ids)}
        except _RepairBudgetExceeded:
            return None
