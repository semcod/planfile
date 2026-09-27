"""Automated triage engine and classification for production alerts in sprints."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AlertCategory(str, Enum):
    """Categorized subsystem for an incoming production alert."""

    MEMORY = "memory"
    DATABASE = "database"
    CPU = "cpu"
    DISK = "disk"
    DATA_PROCESSOR = "data_processor"
    NETWORK = "network"
    GENERAL = "general"


class AlertSeverity(str, Enum):
    """Normalized alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class AlertTriageResult:
    """Diagnostic outcome and remediation proposal for a triaged alert."""

    ticket_id: str
    title: str
    category: AlertCategory
    severity: AlertSeverity
    metric_value: str | None = None
    metric_threshold: str | None = None
    root_cause: str = ""
    mitigation: str = ""
    koru_remediation_task: str | None = None
    recommended_status: str = "in_progress"
    recommended_labels: list[str] = field(default_factory=lambda: ["production-alerts", "triaged"])
    acceptance_criteria: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert triage result to serializable dictionary."""
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "category": self.category.value,
            "severity": self.severity.value,
            "metric_value": self.metric_value,
            "metric_threshold": self.metric_threshold,
            "root_cause": self.root_cause,
            "mitigation": self.mitigation,
            "koru_remediation_task": self.koru_remediation_task,
            "recommended_status": self.recommended_status,
            "recommended_labels": list(self.recommended_labels),
            "acceptance_criteria": list(self.acceptance_criteria),
        }


class AlertClassifier:
    """Rule-based pattern matching and root-cause classifier for production alerts."""

    # Subsystem detection patterns
    PATTERNS: list[tuple[AlertCategory, re.Pattern[str]]] = [
        (
            AlertCategory.MEMORY,
            re.compile(r"(?i)\b(?:memory|ram|pami[eę][cć]|heap|oom|out of memory)\b"),
        ),
        (
            AlertCategory.DATABASE,
            re.compile(
                r"(?i)\b(?:database|db|connection timeout|baza|postgres|mysql|sqlite|query timeout)\b"
            ),
        ),
        (
            AlertCategory.CPU,
            re.compile(r"(?i)\b(?:cpu|procesor|load average|usage spike)\b"),
        ),
        (
            AlertCategory.DISK,
            re.compile(r"(?i)\b(?:disk|dysk|storage|filesystem|/var/log|partition|disk space)\b"),
        ),
        (
            AlertCategory.DATA_PROCESSOR,
            re.compile(
                r"(?i)\b(?:data-processor|process_data|empty data|ingestion pipeline|starvation)\b"
            ),
        ),
    ]

    # Pre-canned root causes and mitigations for known recurring incidents
    DIAGNOSTICS: dict[AlertCategory, dict[str, Any]] = {
        AlertCategory.MEMORY: {
            "root_cause": "Unbounded query cache buffering or worker process memory leak on host.",
            "mitigation": "Restart worker pool, tune LRU cache eviction and configure max memory limits.",
            "koru_task": "KORU-RAM-01",
            "criteria": [
                "AC-01: Isolate leaking process and verify garbage collector / cache eviction limits.",
                "AC-02: RAM utilization drops below 80% threshold under steady load.",
            ],
        },
        AlertCategory.DATABASE: {
            "root_cause": "Missing composite index on active ticket queries causing table scan and connection pool starvation.",
            "mitigation": "Add index on (sprint_id, status) and increase connection pool timeout / keepalive.",
            "koru_task": "KORU-DB-01",
            "criteria": [
                "AC-01: Apply database indexing on sprint ticket lookup queries.",
                "AC-02: Query execution latency returns below 200ms without connection timeouts.",
            ],
        },
        AlertCategory.CPU: {
            "root_cause": "Spin-lock busy waiting in worker queue polling or intense AST log indexing during peak hours.",
            "mitigation": "Convert polling to event-driven notifications and throttle background analysis.",
            "koru_task": "KORU-CPU-01",
            "criteria": [
                "AC-01: Replace spin-lock polling loop with async event / signal notifications.",
                "AC-02: Sustained CPU usage stays below 75% under standard workload.",
            ],
        },
        AlertCategory.DISK: {
            "root_cause": "Uncompressed debug logs and stale temporary execution receipts accumulating in /var/log.",
            "mitigation": "Configure logrotate with 3-day max retention and prune expired socket/receipt caches.",
            "koru_task": "KORU-DISK-01",
            "criteria": [
                "AC-01: Enforce logrotate compression and purge obsolete receipt dumps.",
                "AC-02: Root filesystem utilization stays below 70%.",
            ],
        },
        AlertCategory.DATA_PROCESSOR: {
            "root_cause": "Ingestion pipeline unhandled empty-payload condition when upstream service returns 204 No Content.",
            "mitigation": "Add early return guard clause for empty batches prior to data transformation pipeline.",
            "koru_task": "KORU-DP-01",
            "criteria": [
                "AC-01: Add guard check handling empty payload gracefully in process_data.",
                "AC-02: Unit and integration tests verify zero-byte and empty-list responses.",
            ],
        },
        AlertCategory.GENERAL: {
            "root_cause": "Unclassified production anomaly requiring engineering inspection.",
            "mitigation": "Investigate system telemetry, error logs, and recent deployment changes.",
            "koru_task": "KORU-GEN-01",
            "criteria": [
                "AC-01: Identify exact failure mode and record diagnostics.",
            ],
        },
    }

    @classmethod
    def classify_category(cls, text: str) -> AlertCategory:
        """Determine subsystem category based on text content."""
        for category, pattern in cls.PATTERNS:
            if pattern.search(text):
                return category
        return AlertCategory.GENERAL

    @classmethod
    def extract_metrics(cls, text: str) -> tuple[str | None, str | None]:
        """Extract observed metric value and threshold from alert text."""
        # Check patterns like "95 exceeds 90" or "94.2%" or "5.2s"
        exceeds_match = re.search(
            r"(\d+(?:\.\d+)?)\s+exceeds\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE
        )
        if exceeds_match:
            return exceeds_match.group(1), exceeds_match.group(2)

        percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if percent_match:
            return f"{percent_match.group(1)}%", None

        duration_match = re.search(
            r"(\d+(?:\.\d+)?)\s*s(?:\s+query|\s+timeout)?", text, re.IGNORECASE
        )
        if duration_match:
            return f"{duration_match.group(1)}s", None

        return None, None

    @classmethod
    def triage_ticket(cls, ticket_id: str, ticket_data: dict[str, Any]) -> AlertTriageResult:
        """Perform root cause analysis and propose remediation for a single alert ticket."""
        title = ticket_data.get("title", "")
        description = ticket_data.get("description", "")
        combined_text = f"{title} {description}"

        category = cls.classify_category(combined_text)
        metric_val, metric_thresh = cls.extract_metrics(combined_text)

        # Normalize severity
        raw_priority = str(ticket_data.get("priority", "normal")).lower()
        if raw_priority in {"critical", "p1"}:
            severity = AlertSeverity.CRITICAL
        elif raw_priority in {"high", "p2"}:
            severity = AlertSeverity.HIGH
        elif raw_priority in {"normal", "p3"}:
            severity = AlertSeverity.NORMAL
        else:
            severity = AlertSeverity.LOW

        diag = cls.DIAGNOSTICS.get(category, cls.DIAGNOSTICS[AlertCategory.GENERAL])

        # Tailor root cause description if specific metrics are detected
        root_cause = diag["root_cause"]
        if category == AlertCategory.MEMORY and metric_val:
            root_cause = f"High RAM usage ({metric_val}) on host monag: {diag['root_cause']}"
        elif category == AlertCategory.DATABASE and metric_val:
            root_cause = f"Database query latency spike ({metric_val}): {diag['root_cause']}"
        elif category == AlertCategory.CPU and metric_val:
            thresh_str = f" (threshold {metric_thresh})" if metric_thresh else ""
            root_cause = f"CPU utilization spike ({metric_val}{thresh_str}): {diag['root_cause']}"
        elif category == AlertCategory.DISK and metric_val:
            thresh_str = f" (threshold {metric_thresh})" if metric_thresh else ""
            root_cause = f"Disk space depletion ({metric_val}{thresh_str}): {diag['root_cause']}"
        elif category == AlertCategory.DATA_PROCESSOR and "process_data" in combined_text:
            root_cause = f"Data processor failure in process_data: {diag['root_cause']}"

        existing_labels = list(ticket_data.get("labels", []))
        recommended_labels = sorted(
            set(existing_labels + ["production-alerts", "triaged", f"subsystem-{category.value}"])
        )

        return AlertTriageResult(
            ticket_id=ticket_id,
            title=title,
            category=category,
            severity=severity,
            metric_value=metric_val,
            metric_threshold=metric_thresh,
            root_cause=root_cause,
            mitigation=diag["mitigation"],
            koru_remediation_task=diag["koru_task"],
            recommended_status="in_progress",
            recommended_labels=recommended_labels,
            acceptance_criteria=list(diag["criteria"]),
        )


def is_alert_ticket(ticket_data: dict[str, Any]) -> bool:
    """Return True if ticket represents a production alert."""
    title = str(ticket_data.get("title", ""))
    description = str(ticket_data.get("description", ""))
    labels = [str(lbl).lower() for lbl in ticket_data.get("labels", [])]
    combined = f"{title} {description}".lower()

    if any(tag in labels for tag in ("production-alerts", "alert", "monitoring", "telemetry")):
        return True

    alert_indicators = (
        "🚨",
        "alert",
        "timeout",
        "spike",
        "failed:",
        "exceeds",
        "high memory",
        "cpu usage",
        "disk usage",
        "process_data failed",
    )
    return any(indicator in combined for indicator in alert_indicators)


def triage_sprint_alerts(sprint_data: dict[str, Any]) -> dict[str, AlertTriageResult]:
    """Scan and triage all alert tickets present in sprint data."""
    sprint_section = sprint_data.get("sprint", sprint_data)
    tickets = sprint_section.get("tickets", {})
    if not isinstance(tickets, dict):
        return {}

    results: dict[str, AlertTriageResult] = {}
    for ticket_id, ticket_data in tickets.items():
        if isinstance(ticket_data, dict) and is_alert_ticket(ticket_data):
            results[ticket_id] = AlertClassifier.triage_ticket(ticket_id, ticket_data)

    return results


def apply_triage_to_sprint(
    sprint_data: dict[str, Any], in_place: bool = False
) -> tuple[dict[str, Any], list[AlertTriageResult]]:
    """Apply root cause descriptions, status updates, and acceptance criteria to alert tickets."""
    data = sprint_data if in_place else copy.deepcopy(sprint_data)
    sprint_section = data.get("sprint", data)
    tickets = sprint_section.get("tickets", {})

    triaged_list: list[AlertTriageResult] = []
    if not isinstance(tickets, dict):
        return data, triaged_list

    for ticket_id, ticket_data in tickets.items():
        if isinstance(ticket_data, dict) and is_alert_ticket(ticket_data):
            result = AlertClassifier.triage_ticket(ticket_id, ticket_data)
            triaged_list.append(result)

            # Update ticket description with root cause and remediation details
            existing_desc = ticket_data.get("description", "").strip()
            details = (
                f"### Root Cause Analysis\n{result.root_cause}\n\n"
                f"### Mitigation Strategy\n{result.mitigation}\n\n"
                f"**Koru Remediation Link**: `{result.koru_remediation_task}`"
            )
            ticket_data["description"] = (
                f"{existing_desc}\n\n{details}".strip() if existing_desc else details
            )

            # Transition open alerts to in_progress
            if ticket_data.get("status") == "open":
                ticket_data["status"] = result.recommended_status

            ticket_data["labels"] = result.recommended_labels

            # Ensure acceptance criteria are present
            if not ticket_data.get("acceptance_criteria"):
                ticket_data["acceptance_criteria"] = result.acceptance_criteria

    return data, triaged_list
