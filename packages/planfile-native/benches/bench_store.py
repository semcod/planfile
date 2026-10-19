"""Representative planfile storage workload for baseline/candidate comparison.

    PLANFILE_NATIVE=off  python benches/bench_store.py 3000 > baseline.json
    PLANFILE_NATIVE=auto python benches/bench_store.py 3000 > candidate.json

Both runs build the same store (N tickets in ``current``) in a fresh temporary directory and
time the same operations; every operation is sampled ``--samples`` times (default 7) and the
raw samples are printed as JSON so they can be attached as digest-bound evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

from planfile.core import native
from planfile.core.models import Ticket
from planfile.core.store import Store


def sample(fn, samples: int) -> list[float]:
    fn()  # warm-up, discarded
    out = []
    for _ in range(samples):
        start = time.perf_counter()
        fn()
        out.append((time.perf_counter() - start) * 1000.0)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickets", nargs="?", type=int, default=3000)
    parser.add_argument("--samples", type=int, default=7)
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="pfbench-"))
    os.chdir(root)
    store = Store(root)
    store.init()
    body = "d " * 200
    tickets = [
        Ticket(id=f"PLF-{i:05d}", name=f"Ticket {i} " + "lorem ipsum " * 8, description=body, priority="normal")
        for i in range(args.tickets)
    ]
    start = time.perf_counter()
    store.create_tickets_bulk(tickets)
    bulk_ms = (time.perf_counter() - start) * 1000.0

    counter = [args.tickets]

    def create_one() -> None:
        counter[0] += 1
        store.create_ticket(Ticket(id=f"PLF-{counter[0]:05d}", name="new", priority="low"))

    def cold_list() -> None:
        for mirror in (root / ".planfile").rglob("*.fast.json"):
            mirror.unlink()
        store.list_tickets("current")

    clock = [0]

    def update_one() -> None:
        clock[0] += 1
        store.update_ticket("PLF-00042", name=f"renamed {clock[0]}")

    results = {
        "update_ticket": sample(update_one, args.samples),
        "create_ticket": sample(create_one, args.samples),
        "list_tickets_warm": sample(lambda: store.list_tickets("current"), args.samples),
        "get_ticket_warm": sample(lambda: store.get_ticket("PLF-00042"), args.samples),
        "list_tickets_cold_no_mirror": sample(cold_list, max(3, args.samples // 2)),
    }
    report = {
        "workload": {"tickets": args.tickets, "sprint_file_bytes": (root / ".planfile/sprints/current.yaml").stat().st_size},
        "native": {"mode": native.mode(), "available": native.available(), "enabled": native.enabled()},
        "platform": f"{platform.system()} {platform.machine()} python {platform.python_version()}",
        "bulk_create_ms": bulk_ms,
        "samples_ms": results,
        "median_ms": {name: statistics.median(values) for name, values in results.items()},
    }
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
