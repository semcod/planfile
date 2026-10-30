"""Ordered cross-sprint status reads must not scan the terminal archive."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from planfile.core.sqlite_index import SQLiteTicketIndex


def _records(count=1200):
    for position in range(count):
        status = "blocked" if position % 400 == 399 else "done"
        ticket = {"id": f"PLF-{position + 1}", "status": status,
                  "name": f"Ticket {position}", "history": ["not operational"]}
        yield {"id": ticket["id"], "sprint": f"archive-{position % 10}",
               "status": status, "priority": "high", "source": "local",
               "queue": "default", "created_at": None, "updated_at": None,
               "position": position, "ticket_json": json.dumps(ticket),
               "summary_json": json.dumps(ticket), "blocked_by": []}


def _legacy(index):
    index.rebuild(_records(), signature=("unchanged",))
    with sqlite3.connect(index.path) as connection:
        connection.execute("DROP INDEX tickets_status_position")
        return connection.execute(
            "SELECT id, status, position, ticket_json FROM tickets ORDER BY position"
        ).fetchall()


@pytest.mark.parametrize("legacy", [False, True])
def test_status_page_searches_index_without_sorting_or_archive_scan(tmp_path, legacy):
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    if legacy:
        _legacy(index)
    else:
        index.rebuild(_records(), signature=("unchanged",))
    with index._connection() as connection:
        query = "SELECT position, ticket_json FROM tickets WHERE status=? ORDER BY position LIMIT 1"
        plans = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + query, ("blocked",))]
        assert any("SEARCH tickets USING INDEX tickets_status_position" in plan for plan in plans)
        assert not any("SCAN tickets" in plan or "TEMP B-TREE" in plan for plan in plans)
        # SQLite VM work, rather than wall-clock timing, proves an absent status
        # does not inspect every archived row on a loaded host.
        steps = 0

        def progress():
            nonlocal steps
            steps += 1
            return int(steps > 10)

        connection.set_progress_handler(progress, 100)
        assert connection.execute(query, ("in_progress",)).fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM tickets WHERE status=?",
                                  ("in_progress",)).fetchone()[0] == 0
        connection.set_progress_handler(None, 0)
    body, total, count = index.render_operational_payloads(
        sprint="all", filters={"status": "blocked"}, offset=1, limit=1)
    assert total == 3 and count == 1
    assert json.loads(body) == [{"id": "PLF-800", "status": "blocked", "name": "Ticket 799"}]


def test_existing_database_migrates_once_and_preserves_payloads_and_signature(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    before = _legacy(index)
    assert index.is_current(("unchanged",))
    with index._connection() as connection:
        after = connection.execute(
            "SELECT id, status, position, ticket_json FROM tickets ORDER BY position"
        ).fetchall()
        assert [tuple(row) for row in after] == before
    # Subsequent opens must not perform schema writes or require a writer lock.
    with sqlite3.connect(index.path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        assert index.is_current(("unchanged",))


def test_concurrent_existing_database_opens_share_additive_migration(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    before = _legacy(index)

    def observe(_):
        local = SQLiteTicketIndex(index.path)
        body, total, count = local.render_operational_payloads(
            sprint="all", filters={"status": "blocked"}, offset=0, limit=1)
        return json.loads(body)[0]["id"], total, count

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(observe, range(8))) == [("PLF-400", 3, 1)] * 8
    with index._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == len(before)
        assert len([row for row in connection.execute("PRAGMA index_list(tickets)")
                    if row[1] == "tickets_status_position"]) == 1
