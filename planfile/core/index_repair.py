"""Bounded reconciliation of canonical writes made during an index scan."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from yaml import YAMLError

from planfile.core.fastio import load_yaml_text, read_yaml_fast

# Never turn finalization into a second archive scan under the writer lock.
MAX_REPAIR_BYTES = 32 * 1024 * 1024
MAX_REPAIR_TICKETS = 2048
MAX_REPAIR_SECONDS = 8.0
MAX_STORED_CHANGED_SPRINTS = 4


class _RepairBudgetExceeded(Exception):
    pass


@dataclass(frozen=True)
class _LocatorSnapshot:
    path: Path
    signature: tuple | None
    locations: dict[str, str]
    byte_count: int

    def matches(self, store, signature: tuple) -> bool:
        return self.path == store._history_locations_path and self.signature == signature[2]


def capture_locator_snapshot(store, built_signature: tuple) -> _LocatorSnapshot | None:
    """Retain bounded locator metadata matching the generation before a scan.

    Read directly with a size cap: a cached/mirrored map or a stat-only size
    check must not qualify a different file version during an atomic replace.
    This preparation runs outside the writer lock; finalization rechecks it.
    """
    started = time.monotonic()
    expected = built_signature[2]
    if store._history_locations_signature() != expected:
        return None
    try:
        try:
            with store._history_locations_path.open("rb") as stream:
                raw = stream.read(MAX_REPAIR_BYTES + 1)
        except FileNotFoundError:
            raw = b""
        if len(raw) > MAX_REPAIR_BYTES:
            return None
        data = load_yaml_text(raw.decode("utf-8")) or {}
        locations = data.get("tickets", {}) if isinstance(data, dict) else None
        if not isinstance(locations, dict) or any(
            not isinstance(key, str) or not key or not isinstance(value, str)
            or not store.SPRINT_ID_PATTERN.fullmatch(value)
            for key, value in locations.items()
        ):
            return None
        if (store._history_locations_signature() != expected
                or time.monotonic() - started > MAX_REPAIR_SECONDS):
            return None
        return _LocatorSnapshot(store._history_locations_path, expected, dict(locations), len(raw))
    except (OSError, UnicodeError, YAMLError):
        return None


def _valid_locator_stamp(value) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(type(n) is int and n >= 0 for n in value)
    ):
        return (value[0], value[1])
    return None


def _changed_sprint_ids(before_rows: tuple, after_rows: tuple) -> set[str]:
    before = {(row[0], row[1]): row[2:] for row in before_rows}
    after = {(row[0], row[1]): row[2:] for row in after_rows}
    return {
        key[0]
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    }


def _has_other_tickets(connection: sqlite3.Connection, changed: set[str]) -> bool:
    if not changed:
        return True
    placeholders = ", ".join("?" for _ in changed)
    return bool(
        connection.execute(
            f"SELECT EXISTS(SELECT 1 FROM tickets WHERE sprint NOT IN ({placeholders}))",
            tuple(sorted(changed)),
        ).fetchone()[0]
    )


def _indexed_ticket_sprints(index) -> dict[str, str] | None:
    """Read (id, sprint) from the committed projection without scanning full payloads."""
    try:
        with closing(index._connect_routing()) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
            op_ready = connection.execute(
                "SELECT 1 FROM meta WHERE key='operational_version' AND value='1'"
            ).fetchone()
            table = "ticket_operational" if op_ready else "tickets"
            rows = connection.execute(f"SELECT id, sprint FROM {table}").fetchall()
            return {row["id"]: row["sprint"] for row in rows}
    except sqlite3.DatabaseError:
        return None


def _removed_current_shards_are_archived(
    store, removed_sources, changed_sprints, indexed_sprints, locations, tickets,
) -> bool:
    """Prove every ticket indexed in a missing current shard reached daily history."""
    if not store._uses_sharded_storage():
        return False
    storage = store._sharded_storage()
    current_tickets = tickets("current")
    terminal_statuses = store._archive_config()["terminal_statuses"]
    verified_sources = set()
    for ticket_id, previous in indexed_sprints.items():
        if previous != "current":
            continue
        source = (previous, str(storage.shard_path(previous, ticket_id)))
        if source not in removed_sources:
            continue
        destination = locations.get(ticket_id)
        if (destination is None or destination not in changed_sprints
                or not re.fullmatch(r"history-[0-9]{4}-[0-9]{2}-[0-9]{2}", destination)
                or ticket_id in current_tickets):
            return False
        archived = tickets(destination).get(ticket_id)
        if (not isinstance(archived, dict) or archived.get("sprint") != destination
                or str(archived.get("status", "")).lower() not in terminal_statuses):
            return False
        verified_sources.add(source)
    return verified_sources == removed_sources


def _has_unmapped_earlier_copy(indexed_sprints, locations, affected, sprint_order, tickets) -> bool:
    """Check whether an unproven locator removal can change canonical precedence."""
    unmapped = {}
    for ticket_id, sprint in indexed_sprints.items():
        if sprint != "current" and ticket_id not in locations and ticket_id not in affected:
            unmapped.setdefault(sprint, set()).add(ticket_id)
    later_ids = set()
    for sprint in reversed(sprint_order):
        if later_ids and not later_ids.isdisjoint(tickets(sprint)):
            return True
        later_ids.update(unmapped.get(sprint, ()))
    return False


def _stored_baseline(index, target: tuple) -> tuple[tuple, int] | None:
    """Recover stamps for known sources from an existing, committed projection.

    Recover deferred writes from their contention token, or bounded sprint/archive
    rotations (including newly created daily history files and matching
    history-locations updates) when a full rebuild would also scan other tickets.
    """
    from planfile.core.sqlite_index import _SCHEMA_VERSION, RoutingSnapshotUnavailableError

    current_token = target[3]
    if current_token is not None and (not isinstance(current_token, str)
                                      or not re.fullmatch("[0-9a-f]{32}", current_token)):
        return None
    try:
        with closing(index._connect_routing()) as connection:
            row = connection.execute(
                "SELECT value, length(CAST(value AS BLOB)) FROM meta WHERE key='source_signature' "
                "AND typeof(value)='text' AND length(CAST(value AS BLOB)) BETWEEN 1 AND ? "
                "AND EXISTS (SELECT 1 FROM meta WHERE key='schema_version' AND value=?)",
                (MAX_REPAIR_BYTES, str(_SCHEMA_VERSION)),
            ).fetchone()
        if row is None:
            return None
        saved = json.loads(row[0])
        if not isinstance(saved, list) or len(saved) != len(target):
            return None
        sprints, journals, locator, token, revision = saved
        if revision != target[4]:
            return None
        if locator is None:
            saved_locator = None
        else:
            saved_locator = _valid_locator_stamp(locator)
            if saved_locator is None:
                return None
        locator_changed = saved_locator != target[2]
        if locator_changed and target[2] is None:
            return None
        if current_token is None and token is not None:
            return None
        if token is not None and (not isinstance(token, str) or not re.fullmatch("[0-9a-f]{32}", token)):
            return None
        if not isinstance(sprints, list) or not isinstance(journals, list):
            return None

        def valid_stamps(row, width):
            return (isinstance(row, list) and len(row) == width
                    and all(type(n) is int and n >= -1 for n in row[-2:]))

        target_sprint_keys = {(row[0], row[1]) for row in target[0]}
        seen_sprint_keys = set()
        for old in sprints:
            if not valid_stamps(old, 4) or not isinstance(old[0], str) or not isinstance(old[1], str):
                return None
            key = (old[0], old[1])
            if key in seen_sprint_keys:
                return None
            # An archive rotation can remove a current shard's last ticket.
            # Reconciliation must prove where its indexed tickets went.
            if key not in target_sprint_keys and not (locator_changed and key[0] == "current"):
                return None
            seen_sprint_keys.add(key)

        current_names = {row[0] for row in target[1]}
        if any(not valid_stamps(old, 3) or not isinstance(old[0], str)
               or old[0] not in current_names for old in journals):
            return None
        names = [row[0] for row in journals]
        if names != sorted(set(names)):
            return None
        baseline = (
            tuple(map(tuple, sprints)),
            tuple(map(tuple, journals)),
            saved_locator,
            token,
            revision,
        )
        if baseline[:2] == target[:2]:
            return None
        changed = _changed_sprint_ids(baseline[0], target[0])
        if locator_changed and (
            not changed or len(changed) > MAX_STORED_CHANGED_SPRINTS
        ):
            return None
        if locator_changed and saved_locator is not None and target[2][1] < saved_locator[1]:
            if not any(s not in ("current", "backlog") for s in changed):
                return None
        # Verify the routing generation and its required objects on a
        # read-only connection. Never initialize metadata to qualify a delta.
        with index._routing_connection(baseline) as connection:
            if token == current_token:
                if not changed or len(changed) > MAX_STORED_CHANGED_SPRINTS:
                    return None
                if not _has_other_tickets(connection, changed):
                    return None
            elif locator_changed and not _has_other_tickets(connection, changed):
                return None
            return baseline, row[1]
    except (ValueError, RecursionError, sqlite3.DatabaseError, RoutingSnapshotUnavailableError):
        return None


def reconcile_index(store, index, built_signature: tuple | None = None, *,
                    locator_snapshot: _LocatorSnapshot | None = None) -> dict | None:
    """Make a scanned projection current using only a small changed-source set.

    A rebuild may have observed either version of any changed source. Refresh
    every ID in those sprints (including IDs no longer present) and every
    changed evidence journal, resolving canonical location precedence again.
    Writers use the same mutation lock, so the final signature and payloads
    describe one state. Locator changes require a matching captured baseline
    (or, for stored-baseline recovery, verification that every locator delta
    belongs to the bounded changed-sprint set); an unknown baseline or a large
    delta stays stale.
    """
    with store.mutation_lock():
        started = time.monotonic()
        target = store._ticket_index_signature()
        stored_bytes = 0
        from_stored_baseline = built_signature is None
        if from_stored_baseline:
            prior = _stored_baseline(index, target)
            if prior is None:
                return None
            built_signature, stored_bytes = prior
        if target == built_signature:
            return index.status(target) | {"rebuilt": True}
        locator_changed = target[2] != built_signature[2]
        if locator_snapshot is not None and (
            not locator_changed or not locator_snapshot.matches(store, built_signature)
        ):
            locator_snapshot = None
        if locator_changed and not from_stored_baseline and locator_snapshot is None:
            return None

        consumed = stored_bytes + (locator_snapshot.byte_count if locator_snapshot is not None else 0)
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
            if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", ticket_id) for ticket_id in ids):
                return None
            charge(store._history_locations_path)
            indexed_sprints = None
            if locator_changed:
                latest = capture_locator_snapshot(store, target)
                if latest is None:
                    return None
                locations = latest.locations
                if locator_snapshot is not None and not from_stored_baseline:
                    ids.update(changed_keys(locator_snapshot.locations, locations))
                else:
                    indexed_sprints = _indexed_ticket_sprints(index)
                    check_budget()
                    if indexed_sprints is None:
                        return None
                    mismatched = [
                        (tid, loc_sprint)
                        for tid, loc_sprint in locations.items()
                        if indexed_sprints.get(tid) != loc_sprint
                    ]
                    if any(
                        loc_sprint not in changed_sprints
                        and indexed_sprints.get(tid) not in changed_sprints
                        for tid, loc_sprint in mismatched
                    ):
                        return None
                    removed_sources = before_sources.keys() - after_sources.keys()
                    if removed_sources and not _removed_current_shards_are_archived(
                        store, removed_sources, changed_sprints, indexed_sprints, locations, tickets,
                    ):
                        return None
                    ids.update(tid for tid, _ in mismatched)
            else:
                locations = store._history_locations()
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
            all_sprints = store._all_sprint_ids()
            if indexed_sprints is not None and built_signature[2] is not None:
                if locator_snapshot is None:
                    if _has_unmapped_earlier_copy(indexed_sprints, locations, ids, all_sprints, tickets):
                        return None
                elif locator_snapshot.locations.keys() - locations.keys() - ids:
                    return None
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
