from __future__ import annotations

from pathlib import Path

import yaml

from planfile.todo_sync import sync_todo_checkboxes_from_planfile


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_uses_strategy_statuses(tmp_path: Path):
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "integrations": {
                    "markdown": {
                        "sync_on_plan_run": True,
                        "todo_file": "TODO.md",
                    }
                },
                "tasks": [
                    {"id": "Q01", "title": "Fix auth", "status": "success"},
                    {"id": "Q02", "title": "Refactor api", "status": "todo"},
                ],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(
        todo_path,
        "# TODO\n\n"
        "- [ ] Q01 - Fix auth\n"
        "- [ ] Q02 - Refactor api\n",
    )

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is True
    assert report["updated"] == 1
    todo = todo_path.read_text(encoding="utf-8")
    assert "- [x] Q01 - Fix auth" in todo
    assert "- [ ] Q02 - Refactor api" in todo


def test_sync_todo_checkboxes_from_planfile_uses_results_markers(tmp_path: Path):
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "integrations": {
                    "markdown": {
                        "sync_on_plan_run": True,
                        "todo_file": "TODO.md",
                    }
                },
                "tasks": [{"id": "Q10", "title": "Add cache", "status": "todo"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q10 - Add cache\n")

    results = [{"ticket_id": "Q10", "task_name": "Add cache", "status": "success"}]
    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path, results=results)

    assert report["updated"] == 1
    assert "- [x] Q10 - Add cache" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_respects_disabled_setting(tmp_path: Path):
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "integrations": {
                    "markdown": {
                        "sync_on_plan_run": False,
                        "todo_file": "TODO.md",
                    }
                },
                "tasks": [{"id": "Q99", "title": "Should stay unchecked", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q99 - Should stay unchecked\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is False
    assert report["updated"] == 0
    assert "- [ ] Q99 - Should stay unchecked" in todo_path.read_text(encoding="utf-8")
