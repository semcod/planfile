"""Regression tests for SQLite connection closing, batched index operations, cached YAML loaders, and wired parameters."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

from planfile.analysis.generator import PlanfileGenerator
from planfile.core import configuration as config_mod
from planfile.core import store as store_mod
from planfile.core.sqlite_index import SQLiteTicketIndex
from planfile.importers.code2llm_importer import import_code2llm
from planfile.integrations import config as integrations_config_mod
from planfile.models import Sprint, Strategy, TaskPattern, TaskType
from planfile.project_paths import _configured_github_repository
from planfile.utils.yaml_cache import _load_yaml_cached as paths_yaml_cache
from planfile.runner import apply_strategy_to_tickets
from planfile.sync import state as sync_state_mod
from planfile.sync.retry import RetryQueue


def _sample_record(ticket_id: str, position: int = 0, blocked_by: list[str] | None = None) -> dict:
    return {
        "id": ticket_id,
        "sprint": "current",
        "status": "todo",
        "priority": "high",
        "source": "local",
        "queue": "default",
        "created_at": "2026-10-17T00:00:00Z",
        "updated_at": "2026-10-17T00:00:00Z",
        "position": position,
        "ticket_json": f'{{"id": "{ticket_id}", "title": "Title {ticket_id}"}}',
        "summary_json": f'{{"id": "{ticket_id}"}}',
        "blocked_by": blocked_by or [],
    }


def test_retry_queue_closes_sqlite_connections(tmp_path: Path) -> None:
    closed_count = 0
    real_connect = sqlite3.connect

    class TrackingConnection(sqlite3.Connection):
        def close(self) -> None:
            nonlocal closed_count
            closed_count += 1
            super().close()

    def connect_wrapper(*args, **kwargs):
        kwargs.setdefault("factory", TrackingConnection)
        return real_connect(*args, **kwargs)

    planfile_dir = tmp_path / ".planfile"
    queue = RetryQueue(planfile_dir)
    with patch("planfile.sync.retry.sqlite3.connect", side_effect=connect_wrapper):
        rev = queue.enqueue("owner/repo", "PLF-1", {"id": "PLF-1", "title": "Test"}, now=100.0)
        assert rev == 1
        entries = queue.entries("PLF-1")
        assert len(entries) == 1
        queue.pause("owner/repo", delay=10.0, now=100.0)
        cooldowns = queue.cooldowns()
        assert "owner/repo" in cooldowns

    assert closed_count == 4


def test_sqlite_ticket_index_rebuild_and_apply_batched(tmp_path: Path) -> None:
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    records = [
        _sample_record("PLF-1", position=0, blocked_by=["PLF-2"]),
        _sample_record("PLF-2", position=1, blocked_by=[]),
    ]
    count = index.rebuild(records, signature=("sig-1",), batch_size=1)
    assert count == 2
    assert index.is_current(("sig-1",))

    updated_first = _sample_record("PLF-1", position=99, blocked_by=[])
    updated_first["status"] = "done"
    new_third = _sample_record("PLF-3", position=0, blocked_by=["PLF-2"])

    index.apply(
        upserts=[updated_first, new_third],
        deletes=[],
        signature=("sig-2",),
    )
    assert index.is_current(("sig-2",))
    with index._connect() as conn:
        rows = conn.execute("SELECT id, status, position FROM tickets ORDER BY position").fetchall()
        assert [(r["id"], r["status"], r["position"]) for r in rows] == [
            ("PLF-1", "done", 0),
            ("PLF-2", "todo", 1),
            ("PLF-3", "todo", 2),
        ]
        deps = conn.execute("SELECT ticket_id, blocked_by FROM dependencies").fetchall()
        assert [(d["ticket_id"], d["blocked_by"]) for d in deps] == [("PLF-3", "PLF-2")]


def test_yaml_lru_caches_respect_mtime(tmp_path: Path) -> None:
    cfg = tmp_path / "github.planfile.yaml"
    cfg.write_text("integrations:\n  github:\n    repo: owner/one\n", encoding="utf-8")
    paths_yaml_cache.cache_clear()
    assert _configured_github_repository(tmp_path) == "owner/one"
    assert _configured_github_repository(tmp_path) == "owner/one"
    assert paths_yaml_cache.cache_info().hits >= 1

    # Advance mtime and verify cache invalidation
    stat = cfg.stat()
    cfg.write_text("integrations:\n  github:\n    repo: owner/two\n", encoding="utf-8")
    os.utime(cfg, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert _configured_github_repository(tmp_path) == "owner/two"

    # Also exercise store, configuration, integrations.config, and sync.state cached helpers
    assert isinstance(config_mod._read_yaml_file(cfg), dict)
    assert isinstance(store_mod._read_yaml_file(cfg), dict)
    assert isinstance(integrations_config_mod._read_yaml_file(cfg), dict)
    assert isinstance(sync_state_mod._read_yaml_file(cfg), dict)


def test_wired_parameters_compact_sprint_and_backend(tmp_path: Path) -> None:
    toon_file = tmp_path / "evolution.toon"
    toon_file.write_text(
        "NEXT[1]:\n"
        "  [1] ! REFACTOR foo.py\n"
        "      WHY: simplify logic\n"
        "      EFFORT: 2h\n"
        "      IMPACT: 1500\n",
        encoding="utf-8",
    )
    imported = import_code2llm(str(toon_file), sprint="sprint-9")
    assert len(imported) == 1
    assert imported[0]["sprint"] == "sprint-9"

    gen = PlanfileGenerator()
    analysis_result = {
        "analyzed_files": [],
        "issues": [],
        "metrics": [],
        "summary": {
            "total_issues": 0,
            "priority_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "category_breakdown": {},
            "total_metrics": 0,
            "critical_metrics": 0,
            "total_tasks": 0,
        },
    }
    strategy = gen.generate_from_analysis(
        str(tmp_path),
        project_name="demo",
        external_metrics={"high_cc_functions": [{"name": "fn", "cc": 25}], "average_cc": 5.0},
        compact=True,
        analysis_result=analysis_result,
    )
    metrics_block = strategy.metrics if hasattr(strategy, "metrics") else strategy["metrics"]
    assert "high_cc_functions" not in metrics_block.get("current", {})

    strategy_with_task = Strategy(
        name="Demo Strategy",
        project_name="demo",
        project_type="improvement",
        domain="software",
        goal="Improve quality",
        sprints=[Sprint(id=1, name="Sprint 1", duration="1w", goals=["g"], tasks=["t1"])],
        task_patterns=[
            TaskPattern(
                id="t1",
                name="t1",
                type=next(iter(TaskType)),
                priority="high",
                effort_estimate="2h",
                description="desc",
            )
        ],
    )
    res = apply_strategy_to_tickets(strategy_with_task, str(tmp_path), backend="gitlab", dry_run=True)
    assert res["backend"] == "gitlab"
    assert res["created"][0]["backend"] == "gitlab"
