from __future__ import annotations

from pathlib import Path

import yaml

from planfile.ticket_validation import validate_planfile_tickets


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validate_planfile_tickets_rule_based_current_and_stale(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "name": "Fix unused imports",
                        "rule_id": "unused-imports",
                        "files": ["src/a.py"],
                    },
                    {
                        "id": "T2",
                        "name": "Fix wildcard imports",
                        "rule_id": "wildcard-imports",
                        "files": ["src/a.py"],
                    },
                ]
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "src/a.py", "import os\nprint('ok')\n")

    report = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[
            {"rule": "unused-imports", "file": "src/a.py", "line": 1},
        ],
    )

    assert report["scan_available"] is True
    assert report["total"] == 2
    assert report["current"] == 1
    assert report["stale"] == 1
    assert report["unknown"] == 0
    assert report["confirmed_current_ticket_ids"] == ["T1"]
    assert report["stale_ticket_ids"] == ["T2"]


def test_validate_planfile_tickets_line_based_without_scan(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {"id": "L1", "name": "Investigate", "file": "src/b.py", "line": 2},
                    {"id": "L2", "name": "Out of range", "file": "src/b.py", "line": 99},
                    {"id": "L3", "name": "Missing file", "file": "src/missing.py", "line": 1},
                ]
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "src/b.py", "line1\nline2\n")

    report = validate_planfile_tickets(strategy_path=strategy_path, project_path=tmp_path)

    assert report["scan_available"] is False
    assert report["total"] == 3
    assert report["current"] == 0
    assert report["stale"] == 2
    assert report["unknown"] == 1
    assert report["stale_ticket_ids"] == ["L2", "L3"]
    assert report["review_needed_ticket_ids"] == ["L1"]


def test_validate_planfile_tickets_collects_backlog_and_sprint_sections(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "backlog": [
                    {
                        "id": "B1",
                        "name": "Backlog issue",
                        "rule_id": "unused-imports",
                        "files": ["pkg/mod.py"],
                    }
                ],
                "sprints": [
                    {
                        "id": 1,
                        "name": "Sprint 1",
                        "task_patterns": [
                            {"id": "S1", "name": "Manual review"},
                        ],
                        "tickets": {
                            "S2": {"id": "S2", "name": "Ghost file", "files": ["ghost.py"]},
                        },
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "pkg/mod.py", "import os\n")

    report = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[{"rule_id": "unused-imports", "file": "pkg/mod.py", "line": 1}],
    )

    assert report["total"] == 3
    assert report["confirmed_current_ticket_ids"] == ["B1"]
    assert report["stale_ticket_ids"] == ["S2"]
    assert report["review_needed_ticket_ids"] == ["S1"]


def test_validate_planfile_tickets_filters_specific_ticket_ids(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {
                        "id": "Q01",
                        "name": "Existing rule",
                        "rule_id": "unused-imports",
                        "files": ["src/c.py"],
                    },
                    {
                        "id": "Q02",
                        "name": "Missing rule",
                        "rule_id": "wildcard-imports",
                        "files": ["src/c.py"],
                    },
                ]
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "src/c.py", "import os\n")

    report = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[{"rule_id": "unused-imports", "file": "src/c.py", "line": 1}],
        ticket_ids=["Q02"],
    )

    assert report["filtered_ticket_ids"] == ["Q02"]
    assert report["total"] == 1
    assert report["current"] == 0
    assert report["stale"] == 1
    assert report["review_needed_ticket_ids"] == []
    assert report["stale_ticket_ids"] == ["Q02"]


def test_validate_planfile_tickets_empty_ticket_ids_returns_all(tmp_path: Path) -> None:
    """Empty ticket_ids list should be treated as no filter."""
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {
                        "id": "Q01",
                        "name": "Existing rule",
                        "rule_id": "unused-imports",
                        "files": ["src/a.py"],
                    },
                ]
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "src/a.py", "import os\n")

    report_none = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[{"rule_id": "unused-imports", "file": "src/a.py", "line": 1}],
        ticket_ids=None,
    )
    report_empty = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[{"rule_id": "unused-imports", "file": "src/a.py", "line": 1}],
        ticket_ids=[],
    )

    assert report_none["total"] == report_empty["total"] == 1
    assert report_none["current"] == report_empty["current"] == 1


def test_validate_planfile_tickets_nonexistent_ids_returns_empty(tmp_path: Path) -> None:
    """Filtering by IDs that don't exist in strategy should yield empty results."""
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {
                        "id": "Q01",
                        "name": "Existing rule",
                        "rule_id": "unused-imports",
                        "files": ["src/a.py"],
                    },
                ]
            },
            sort_keys=False,
        ),
    )
    _write(tmp_path / "src/a.py", "import os\n")

    report = validate_planfile_tickets(
        strategy_path=strategy_path,
        project_path=tmp_path,
        issue_records=[{"rule_id": "unused-imports", "file": "src/a.py", "line": 1}],
        ticket_ids=["Z99"],
    )

    assert report["total"] == 0
    assert report["current"] == 0
    assert report["stale"] == 0
    assert report["tickets"] == []
