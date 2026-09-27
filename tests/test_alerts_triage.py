"""Tests for production alerts triage and automated handling in sprints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from planfile.analysis.alerts_triage import (
    AlertCategory,
    AlertClassifier,
    AlertSeverity,
    AlertTriageResult,
    apply_triage_to_sprint,
    is_alert_ticket,
    triage_sprint_alerts,
)


def sample_alerts() -> dict[str, Any]:
    """Return dictionary of the 6 production alerts from current sprint."""
    return {
        "PLF-038": {
            "id": "PLF-038",
            "title": "Production alert: High memory usage on prod-01",
            "description": "",
            "priority": "critical",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-048": {
            "id": "PLF-048",
            "title": "Database connection timeout",
            "description": "Intermittent timeouts during peak hours (5.2s query)",
            "priority": "critical",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-052": {
            "id": "PLF-052",
            "title": "🚨 CPU Usage: 95 exceeds 90",
            "description": "Metric CPU Usage exceeded threshold",
            "priority": "critical",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-054": {
            "id": "PLF-054",
            "title": "🚨 Disk Usage: 92 exceeds 90",
            "description": "Metric Disk Usage exceeded threshold (/var/log 88% full)",
            "priority": "critical",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-056": {
            "id": "PLF-056",
            "title": "[data-processor] process_data failed: Empty data provided",
            "description": "Function process_data raised ValueError",
            "priority": "high",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-058": {
            "id": "PLF-058",
            "title": "🚨 CPU: 95 exceeds 90",
            "description": "Metric CPU exceeded threshold of 90",
            "priority": "critical",
            "status": "open",
            "acceptance_criteria": [],
            "labels": [],
        },
        "PLF-026": {
            "id": "PLF-026",
            "title": "Test ticket for new feature",
            "description": "Standard business requirement implementation",
            "priority": "normal",
            "status": "open",
            "acceptance_criteria": ["Implement feature"],
            "labels": ["feature"],
        },
    }


def test_classify_subsystems() -> None:
    """Verify that alert categories are accurately identified."""
    assert AlertClassifier.classify_category("High memory usage on prod-01") == AlertCategory.MEMORY
    assert (
        AlertClassifier.classify_category("Database connection timeout") == AlertCategory.DATABASE
    )
    assert AlertClassifier.classify_category("🚨 CPU Usage: 95 exceeds 90") == AlertCategory.CPU
    assert AlertClassifier.classify_category("🚨 Disk Usage: 92 exceeds 90") == AlertCategory.DISK
    assert (
        AlertClassifier.classify_category("[data-processor] process_data failed")
        == AlertCategory.DATA_PROCESSOR
    )
    assert AlertClassifier.classify_category("Unknown service glitch") == AlertCategory.GENERAL


def test_metric_extraction() -> None:
    """Verify metric values and thresholds are extracted from telemetry strings."""
    val, thresh = AlertClassifier.extract_metrics("🚨 CPU Usage: 95 exceeds 90")
    assert val == "95"
    assert thresh == "90"

    val_mem, thresh_mem = AlertClassifier.extract_metrics("RAM usage 94.2% on monag host")
    assert val_mem == "94.2%"
    assert thresh_mem is None

    val_db, thresh_db = AlertClassifier.extract_metrics("connection timeout (5.2s query)")
    assert val_db == "5.2s"
    assert thresh_db is None


def test_is_alert_ticket() -> None:
    """Verify alert discrimination logic."""
    alerts = sample_alerts()
    for tid in ["PLF-038", "PLF-048", "PLF-052", "PLF-054", "PLF-056", "PLF-058"]:
        assert is_alert_ticket(alerts[tid]), f"{tid} should be detected as an alert"

    assert not is_alert_ticket(alerts["PLF-026"]), (
        "Standard ticket should not be classified as alert"
    )


def test_triage_all_six_alerts() -> None:
    """Verify complete triage and root-cause mapping for all 6 target production alerts."""
    alerts = sample_alerts()
    results = {
        tid: AlertClassifier.triage_ticket(tid, alerts[tid]) for tid in alerts if tid != "PLF-026"
    }

    # PLF-038 (RAM)
    r38 = results["PLF-038"]
    assert r38.category == AlertCategory.MEMORY
    assert r38.severity == AlertSeverity.CRITICAL
    assert r38.koru_remediation_task == "KORU-RAM-01"
    assert "cache" in r38.root_cause.lower() or "memory" in r38.root_cause.lower()
    assert r38.recommended_status == "in_progress"

    # PLF-048 (DB)
    r48 = results["PLF-048"]
    assert r48.category == AlertCategory.DATABASE
    assert r48.koru_remediation_task == "KORU-DB-01"
    assert "index" in r48.root_cause.lower()
    assert r48.metric_value == "5.2s"

    # PLF-052 (CPU)
    r52 = results["PLF-052"]
    assert r52.category == AlertCategory.CPU
    assert r52.koru_remediation_task == "KORU-CPU-01"
    assert r52.metric_value == "95"
    assert r52.metric_threshold == "90"

    # PLF-054 (Disk)
    r54 = results["PLF-054"]
    assert r54.category == AlertCategory.DISK
    assert r54.koru_remediation_task == "KORU-DISK-01"
    assert "logrotate" in r54.mitigation.lower()

    # PLF-056 (Data Processor)
    r56 = results["PLF-056"]
    assert r56.category == AlertCategory.DATA_PROCESSOR
    assert r56.koru_remediation_task == "KORU-DP-01"
    assert "guard" in r56.mitigation.lower() or "empty" in r56.root_cause.lower()

    # PLF-058 (CPU duplicate)
    r58 = results["PLF-058"]
    assert r58.category == AlertCategory.CPU
    assert r58.koru_remediation_task == "KORU-CPU-01"

    # Verify dictionary serialization
    dict_repr = r38.to_dict()
    assert dict_repr["ticket_id"] == "PLF-038"
    assert dict_repr["category"] == "memory"
    assert "production-alerts" in dict_repr["recommended_labels"]


def test_apply_triage_to_sprint() -> None:
    """Verify that applying triage updates ticket status, description, and criteria."""
    sprint_data = {"sprint": {"id": "sprint-001", "tickets": sample_alerts()}}

    updated, triaged = apply_triage_to_sprint(sprint_data, in_place=False)
    assert len(triaged) == 6

    tickets = updated["sprint"]["tickets"]

    # All alerts should now be in_progress
    for tid in ["PLF-038", "PLF-048", "PLF-052", "PLF-054", "PLF-056", "PLF-058"]:
        t = tickets[tid]
        assert t["status"] == "in_progress"
        assert "Root Cause Analysis" in t["description"]
        assert "Mitigation Strategy" in t["description"]
        assert "Koru Remediation Link" in t["description"]
        assert "production-alerts" in t["labels"]
        assert len(t["acceptance_criteria"]) >= 1

    # Standard ticket should remain open and unmutated
    assert tickets["PLF-026"]["status"] == "open"
    assert "Root Cause Analysis" not in tickets["PLF-026"]["description"]


def test_triage_against_real_current_sprint_file() -> None:
    """Verify that triage engine correctly identifies the 6 production alerts in the repository sprint file."""
    current_yaml_path = (
        Path(__file__).resolve().parent.parent / ".planfile" / "sprints" / "current.yaml"
    )
    if not current_yaml_path.exists():
        pytest.skip(f"{current_yaml_path} does not exist in checkout")

    with open(current_yaml_path, encoding="utf-8") as f:
        real_data = yaml.safe_load(f)

    results = triage_sprint_alerts(real_data)
    expected_ids = {"PLF-038", "PLF-048", "PLF-052", "PLF-054", "PLF-056", "PLF-058"}

    for tid in expected_ids:
        assert tid in results, f"Expected alert {tid} to be triaged from current.yaml"
        res = results[tid]
        assert isinstance(res, AlertTriageResult)
        assert res.koru_remediation_task is not None
        assert res.recommended_status == "in_progress"
        assert res.root_cause != ""
