from __future__ import annotations

from pathlib import Path

import yaml

from planfile import Planfile
from planfile.core.schema import SchemaValidator, detect_document_type


def test_schema_validator_detects_legacy_top_level_tasks():
    data = {
        "schema": "planfile.sprint/v1",
        "tasks": [
            {"id": "task_1", "title": "Legacy task 1", "status": "todo"}
        ]
    }
    is_valid, errors = SchemaValidator.validate_sprint(data)
    assert not is_valid
    assert any("Legacy top-level 'tasks' list detected" in e for e in errors)
    assert any("Missing required field: sprint" in e for e in errors)


def test_schema_validator_detects_legacy_sprint_tasks():
    data = {
        "sprint": {
            "id": "current",
            "name": "Current",
            "tasks": [
                {"id": "task_1", "title": "Legacy task 1", "status": "todo"}
            ]
        }
    }
    is_valid, errors = SchemaValidator.validate_sprint(data)
    assert not is_valid
    assert any("Legacy sprint 'tasks' list detected" in e for e in errors)


def test_schema_validator_rejects_non_dict_sprint_and_tickets():
    # Non-dict sprint mapping
    is_valid, errors = SchemaValidator.validate_sprint({"sprint": "not a dict"})
    assert not is_valid
    assert any("Field 'sprint' must be a mapping" in e for e in errors)

    # Non-dict tickets mapping
    is_valid, errors = SchemaValidator.validate_sprint({
        "sprint": {
            "id": "current",
            "name": "Current",
            "tickets": ["ticket1", "ticket2"]
        }
    })
    assert not is_valid
    assert any("Field 'sprint.tickets' must be a mapping" in e for e in errors)

    # Non-dict root
    is_valid, errors = SchemaValidator.validate_sprint(["not", "a", "dict"])
    assert not is_valid
    assert any("Sprint document must be a mapping" in e for e in errors)


def test_detect_document_type_identifies_sprint_with_tasks_or_schema():
    assert detect_document_type({"schema": "planfile.sprint/v1"}) == "sprint"
    assert detect_document_type({"tasks": [{"id": "t1"}]}) == "sprint"
    assert detect_document_type({"sprint": {"id": "current"}}) == "sprint"


def test_migrate_legacy_sprint_tasks_preserves_ids_and_data(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    sprint_file = pf.store._sprint_file("current")
    sprint_file.parent.mkdir(parents=True, exist_ok=True)

    legacy_content = {
        "schema": "planfile.sprint/v1",
        "sprint": {
            "id": "current",
            "name": "Current",
            "status": "active",
            "tickets": {
                "EXISTING-1": {
                    "id": "EXISTING-1",
                    "name": "Existing ticket",
                    "status": "open",
                }
            }
        },
        "tasks": [
            {
                "id": "task_1790352021_1",
                "title": "[maskservice/update] fix(no-license): Repository is missing a LICENSE file.",
                "status": "todo",
                "priority": "medium",
                "created_at": "2026-09-25T15:59:41.360428+00:00",
                "description": "## Context\nNo LICENSE found.",
                "labels": ["monag", "autodiagnosis"],
                "custom_metadata": {"remediation": "add Apache-2.0"},
            },
            {
                "id": "task_1790352021_2",
                "title": "Cancelled task",
                "status": "cancelled",
            }
        ]
    }
    pf.store._write_yaml_atomic(sprint_file, legacy_content, allow_unicode=True)

    # Validate before migration catches legacy tasks
    valid, errors = SchemaValidator.validate_sprint(legacy_content)
    assert not valid
    assert any("Legacy top-level 'tasks' list detected" in e for e in errors)

    # Perform safe migration
    report = pf.store.migrate_legacy_sprint_tasks("current")
    assert report["migrated"] is True
    assert report["count"] == 2
    assert report["total_tickets"] == 3

    # Verify migrated file content
    reloaded_yaml = yaml.safe_load(sprint_file.read_text())
    assert "tasks" not in reloaded_yaml
    assert "tasks" not in reloaded_yaml["sprint"]
    tickets = reloaded_yaml["sprint"]["tickets"]
    assert "EXISTING-1" in tickets
    assert "task_1790352021_1" in tickets
    assert "task_1790352021_2" in tickets

    # Check preserved fields and title -> name mapping
    t1 = tickets["task_1790352021_1"]
    assert t1["name"] == "[maskservice/update] fix(no-license): Repository is missing a LICENSE file."
    assert t1["status"] == "todo"
    assert t1["priority"] == "medium"
    assert t1["labels"] == ["monag", "autodiagnosis"]
    assert t1["custom_metadata"] == {"remediation": "add Apache-2.0"}

    # Check cancelled -> canceled normalization
    t2 = tickets["task_1790352021_2"]
    assert t2["status"] == "canceled"

    # Schema validation now passes cleanly
    valid_after, errors_after = SchemaValidator.validate_sprint(reloaded_yaml)
    assert valid_after, errors_after

    # Idempotent repeated migration
    report2 = pf.store.migrate_legacy_sprint_tasks("current")
    assert report2["migrated"] is False
    assert report2["count"] == 0
    assert report2["reason"] == "no_legacy_tasks"

    # Planfile API can list and get the migrated tickets
    tickets_list = pf.list_tickets(sprint="current")
    ticket_ids = {t.id for t in tickets_list}
    assert ticket_ids == {"EXISTING-1", "task_1790352021_1", "task_1790352021_2"}


def test_malformed_tickets_mapping_does_not_raise_attribute_error(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    sprint_file = pf.store._sprint_file("current")
    sprint_file.parent.mkdir(parents=True, exist_ok=True)

    # tickets is a list instead of a dict
    malformed = {
        "sprint": {
            "id": "current",
            "name": "Current",
            "status": "active",
            "tickets": [
                {"id": "t1", "name": "bad format"}
            ]
        }
    }
    pf.store._write_yaml_atomic(sprint_file, malformed, allow_unicode=True)

    # Does not crash with AttributeError
    records = list(pf.store.ticket_records("current"))
    assert records == []

    tickets = pf.list_tickets(sprint="current")
    assert tickets == []


def test_migrate_to_sharded_yaml_preserves_legacy_tasks(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    sprint_file = pf.store._sprint_file("current")
    sprint_file.parent.mkdir(parents=True, exist_ok=True)

    legacy_content = {
        "schema": "planfile.sprint/v1",
        "sprint": {
            "id": "current",
            "name": "Current",
            "status": "active",
            "tickets": {
                "PLF-001": {"id": "PLF-001", "name": "Existing", "status": "open"}
            }
        },
        "tasks": [
            {
                "id": "task_legacy_shard",
                "title": "Must survive sharded migration",
                "status": "todo",
            }
        ]
    }
    pf.store._write_yaml_atomic(sprint_file, legacy_content, allow_unicode=True)

    # Explicitly migrate legacy tasks first
    report = pf.store.migrate_legacy_sprint_tasks("current")
    assert report["migrated"] is True
    assert report["count"] == 1

    # Sharded migration now migrates and verifies all tickets
    pf.store.migrate_to_sharded_yaml()

    assert pf.store._uses_sharded_storage()
    tickets = {t.id for t in pf.list_tickets(sprint="current")}
    assert "PLF-001" in tickets
    assert "task_legacy_shard" in tickets
