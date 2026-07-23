#!/usr/bin/env python3
"""Compare Planfile's monolithic and sharded YAML ticket layouts.

The benchmark uses temporary projects and never modifies the current project.
It reports medians as JSON so results can be archived by CI.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from planfile import Planfile


def _median_ms(action, *, repeats: int = 1) -> tuple[float, object]:
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = action()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples), result


def _snapshot(ticket_count: int) -> dict:
    timestamp = datetime.now(UTC).isoformat()
    tickets = {}
    for number in range(1, ticket_count + 1):
        ticket_id = f"PLF-{number:06d}"
        tickets[ticket_id] = {
            "id": ticket_id,
            "name": f"Benchmark ticket {number}",
            "status": "open",
            "priority": "normal",
            "sprint": "current",
            "labels": ["benchmark"],
            "blocked_by": [f"PLF-{number - 1:06d}"] if number > 1 else [],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    return {
        "sprint": {
            "id": "current",
            "name": "Current",
            "status": "active",
            "tickets": tickets,
        }
    }


def _prepare(root: Path, snapshot: dict) -> Planfile:
    pf = Planfile(str(root))
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    config["next_id"] = len(snapshot["sprint"]["tickets"]) + 1
    pf.store._write_config(config)
    pf.store._write_yaml_atomic(
        pf.store._sprint_file("current"),
        snapshot,
        allow_unicode=True,
    )
    return pf


def _measure(root: Path, backend: str, update_id: str) -> dict:
    pf = Planfile(str(root))
    cold_list_ms, tickets = _median_ms(
        lambda: pf.list_tickets(sprint="current"),
    )
    warm_list_ms, _ = _median_ms(
        lambda: pf.list_tickets(sprint="current"),
        repeats=5,
    )
    next_ms, selected = _median_ms(
        lambda: pf.next_ticket(sprint="current"),
        repeats=3,
    )

    written_yaml: list[Path] = []
    original = pf.store._write_yaml_atomic

    def counted(path, data, *, allow_unicode=False):
        result = original(path, data, allow_unicode=allow_unicode)
        if Path(path).suffix == ".yaml":
            written_yaml.append(Path(path))
        return result

    pf.store._write_yaml_atomic = counted
    update_ms, updated = _median_ms(
        lambda: pf.update_ticket(update_id, priority="high"),
    )
    update_writes = list(written_yaml)
    update_bytes = sum(path.stat().st_size for path in update_writes if path.exists())
    written_yaml.clear()
    bulk_ms, created = _median_ms(
        lambda: pf.create_tickets_bulk(
            [{"name": f"Bulk benchmark ticket {number}"} for number in range(50)]
        )
    )
    bulk_writes = [
        path
        for path in written_yaml
        if "sprints" in path.parts
    ]
    return {
        "backend": backend,
        "tickets": len(tickets),
        "cold_list_ms": round(cold_list_ms, 3),
        "warm_list_ms": round(warm_list_ms, 3),
        "next_ms": round(next_ms, 3),
        "next_id": selected.id if selected else None,
        "update_ms": round(update_ms, 3),
        "updated": updated is not None,
        "update_id": update_id,
        "yaml_files_written_by_update": len(update_writes),
        "yaml_bytes_written_by_update": update_bytes,
        "bulk_create_50_ms": round(bulk_ms, 3),
        "bulk_created": len(created),
        "yaml_files_written_by_bulk": len(bulk_writes),
        "yaml_bytes_written_by_bulk": sum(
            path.stat().st_size for path in bulk_writes if path.exists()
        ),
        "storage_files": len(pf.store._sprint_storage_files("current")),
    }


def run(ticket_count: int, shard_sizes: list[int]) -> dict:
    snapshot = _snapshot(ticket_count)
    # Avoid an exact shard boundary so the update measures a populated shard.
    update_number = ticket_count - 1 if ticket_count > 1 else 1
    update_id = f"PLF-{update_number:06d}"
    results = []
    with tempfile.TemporaryDirectory(prefix="planfile-storage-benchmark-") as directory:
        base = Path(directory)
        single_root = base / "single"
        _prepare(single_root, snapshot)
        results.append(_measure(single_root, "single-yaml", update_id))

        for shard_size in shard_sizes:
            root = base / f"sharded-{shard_size}"
            pf = _prepare(root, snapshot)
            migration_ms, report = _median_ms(
                lambda: pf.store.migrate_to_sharded_yaml(shard_size=shard_size)
            )
            measured = _measure(root, f"sharded-yaml-{shard_size}", update_id)
            measured["migration_ms"] = round(migration_ms, 3)
            measured["shards"] = len(
                list((root / ".planfile" / "sprints" / "current.shards").glob("tickets-*.yaml"))
            )
            measured["backup_dir_created"] = Path(report["backup_dir"]).is_dir()
            results.append(measured)
    return {
        "schema": "planfile.storage-benchmark/v1",
        "ticket_count": ticket_count,
        "shard_sizes": shard_sizes,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=int, default=5000)
    parser.add_argument(
        "--shard-size",
        type=int,
        action="append",
        dest="shard_sizes",
        help="May be passed more than once (default: 100 and 500)",
    )
    args = parser.parse_args()
    shard_sizes = args.shard_sizes or [100, 500]
    print(json.dumps(run(max(1, args.tickets), shard_sizes), indent=2))


if __name__ == "__main__":
    main()
