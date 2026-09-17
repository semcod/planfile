from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_sync_todo_checkboxes_from_planfile_enabled_via_sync_todo_key(tmp_path: Path):
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "integrations": {
                    "markdown": {
                        "sync_todo": True,
                        "todo_file": "TODO.md",
                    }
                },
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "done"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is True
    assert report["updated"] == 1
    assert "- [x] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_enabled_override_true(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path, enabled=True)

    assert report["enabled"] is True
    assert report["updated"] == 1
    assert "- [x] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_enabled_override_false(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path, enabled=False)

    assert report["enabled"] is False
    assert report["updated"] == 0
    assert "- [ ] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_missing_todo_file(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is True
    assert report["updated"] == 0
    assert not (tmp_path / "TODO.md").exists()


def test_sync_todo_checkboxes_from_planfile_absolute_todo_file(tmp_path: Path):
    todo_path = tmp_path / "docs" / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "integrations": {
                    "markdown": {
                        "sync_on_plan_run": True,
                        "todo_file": str(todo_path),
                    }
                },
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    assert "- [x] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_strategy_relative_todo_fallback(tmp_path: Path):
    strategy_dir = tmp_path / "strategy"
    strategy_dir.mkdir()
    strategy_path = strategy_dir / "planfile.yaml"
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = strategy_dir / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    assert "- [x] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_skips_already_checked_boxes(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(
        todo_path,
        "- [x] Q01 - Fix auth\n"
        "- [X] Q01 - Fix auth\n"
        "- [ ] Q01 - Fix auth\n",
    )

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    content = todo_path.read_text(encoding="utf-8")
    assert content.count("- [x] Q01 - Fix auth") == 2
    assert "- [X] Q01 - Fix auth" in content


def test_sync_todo_checkboxes_from_planfile_preserves_non_checkbox_lines(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(
        todo_path,
        "# TODO\n"
        "\n"
        "Some prose without a checkbox\n"
        "- [ ] Q01 - Fix auth\n",
    )

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    content = todo_path.read_text(encoding="utf-8")
    assert "# TODO" in content
    assert "Some prose without a checkbox" in content
    assert "- [x] Q01 - Fix auth" in content


def test_sync_todo_checkboxes_from_planfile_case_insensitive_match(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Fix auth", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    assert "- [x] fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_matches_substring_marker(tmp_path: Path):
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
                "tasks": [{"id": "Q01", "title": "Add cache", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Add cache to the API layer\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    assert "- [x] Add cache to the API layer" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_ignores_short_markers(tmp_path: Path):
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
                "tasks": [{"id": "Q1", "title": "Fix", "status": "success"}],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q1 - Fix\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 0
    assert "- [ ] Q1 - Fix" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_object_results(tmp_path: Path):
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
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q10 - Add cache\n")

    results = [SimpleNamespace(ticket_id="Q10", task_name="Add cache", status="done")]
    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path, results=results)

    assert report["updated"] == 1
    assert "- [x] Q10 - Add cache" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_ignores_non_done_results(tmp_path: Path):
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
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q10 - Add cache\n")

    results = [{"ticket_id": "Q10", "task_name": "Add cache", "status": "todo"}]
    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path, results=results)

    assert report["updated"] == 0
    assert "- [ ] Q10 - Add cache" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_sprint_task_patterns(tmp_path: Path):
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
                "sprints": [
                    {
                        "task_patterns": [
                            {"id": "S01", "title": "Build widget", "status": "done"},
                        ],
                    },
                ],
            },
            sort_keys=False,
        ),
    )

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] S01 - Build widget\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["updated"] == 1
    assert "- [x] S01 - Build widget" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_missing_strategy_file(tmp_path: Path):
    strategy_path = tmp_path / "missing.yaml"

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is False
    assert report["updated"] == 0
    assert "- [ ] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")


def test_sync_todo_checkboxes_from_planfile_invalid_yaml_disabled(tmp_path: Path):
    strategy_path = tmp_path / "planfile.yaml"
    _write(strategy_path, "tasks: [PRIVATE_CONTENT")

    todo_path = tmp_path / "TODO.md"
    _write(todo_path, "- [ ] Q01 - Fix auth\n")

    report = sync_todo_checkboxes_from_planfile(strategy_path, tmp_path)

    assert report["enabled"] is False
    assert report["updated"] == 0
    assert "- [ ] Q01 - Fix auth" in todo_path.read_text(encoding="utf-8")
