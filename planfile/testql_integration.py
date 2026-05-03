"""TestQL integration helpers for validation, ticket generation, and sync."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from planfile.integrations.config import IntegrationConfig


def _normalize_ref_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_ref_url(value: Any) -> str:
    return _normalize_ref_text(value).rstrip("/")


def _iter_external_refs(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    raw = ticket.get("external_refs")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _collect_ticket_identity_keys(
    ticket: dict[str, Any],
    *,
    integration: str | None = None,
) -> set[str]:
    keys: set[str] = set()

    def add(key: str, value: Any, *, url: bool = False) -> None:
        normalized = _normalize_ref_url(value) if url else _normalize_ref_text(value)
        if normalized:
            keys.add(f"{key}:{normalized}")

    add("local_id", ticket.get("id") or ticket.get("ticket_id"))
    add("external_id", ticket.get("external_id"))
    add("external_key", ticket.get("external_key") or ticket.get("key"))
    add(
        "external_url",
        ticket.get("external_url")
        or ticket.get("url")
        or ticket.get("issue_url")
        or ticket.get("ticket_url"),
        url=True,
    )

    for name in ("github", "gitlab", "jira", "markdown"):
        add(f"{name}_id", ticket.get(f"{name}_id"))
        add(f"{name}_key", ticket.get(f"{name}_key"))
        add(f"{name}_url", ticket.get(f"{name}_url"), url=True)

    source = ticket.get("source")
    if isinstance(source, dict):
        source_integration = _normalize_ref_text(source.get("integration")).lower()
        add("source_id", source.get("id"))
        add("source_key", source.get("key"))
        add("source_url", source.get("url"), url=True)
        if source_integration:
            add(f"{source_integration}_id", source.get("id"))
            add(f"{source_integration}_key", source.get("key"))
            add(f"{source_integration}_url", source.get("url"), url=True)

    for ref in _iter_external_refs(ticket):
        ref_integration = _normalize_ref_text(ref.get("integration")).lower()
        add("external_id", ref.get("id"))
        add("external_key", ref.get("key"))
        add("external_url", ref.get("url"), url=True)
        if ref_integration:
            add(f"{ref_integration}_id", ref.get("id"))
            add(f"{ref_integration}_key", ref.get("key"))
            add(f"{ref_integration}_url", ref.get("url"), url=True)

    if not integration:
        return keys

    prefixes = (
        "external_id:",
        "external_key:",
        "external_url:",
        f"{integration}_id:",
        f"{integration}_key:",
        f"{integration}_url:",
    )
    return {item for item in keys if item.startswith(prefixes)}


def _collect_external_ref_candidates(ticket: dict[str, Any], integration: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_candidate(ref_id: Any = None, ref_key: Any = None, ref_url: Any = None) -> None:
        normalized = {
            "id": _normalize_ref_text(ref_id),
            "key": _normalize_ref_text(ref_key),
            "url": _normalize_ref_url(ref_url),
        }
        signature = (normalized["id"], normalized["key"], normalized["url"])
        if signature == ("", "", "") or signature in seen:
            return
        seen.add(signature)
        candidates.append(normalized)

    integration_name = _normalize_ref_text(ticket.get("integration")).lower()
    for ref in _iter_external_refs(ticket):
        ref_integration = _normalize_ref_text(ref.get("integration")).lower()
        if ref_integration and ref_integration != integration:
            continue
        add_candidate(ref.get("id"), ref.get("key"), ref.get("url"))

    add_candidate(
        ticket.get(f"{integration}_id"),
        ticket.get(f"{integration}_key"),
        ticket.get(f"{integration}_url"),
    )

    if integration_name in {"", integration}:
        add_candidate(
            ticket.get("external_id"),
            ticket.get("external_key") or ticket.get("key"),
            ticket.get("external_url")
            or ticket.get("url")
            or ticket.get("issue_url")
            or ticket.get("ticket_url"),
        )

    return candidates


def _extract_result_field(result: Any, field: str) -> str:
    if hasattr(result, field):
        return _normalize_ref_text(getattr(result, field))
    if isinstance(result, dict):
        return _normalize_ref_text(result.get(field))
    return ""


def _extract_created_ticket_ref(result: Any) -> dict[str, str]:
    return {
        "id": _extract_result_field(result, "id"),
        "key": _extract_result_field(result, "key"),
        "url": _normalize_ref_url(_extract_result_field(result, "url")),
    }


def _extract_search_ticket_id(item: Any) -> str:
    if hasattr(item, "id"):
        return _normalize_ref_text(item.id)
    if isinstance(item, dict):
        return _normalize_ref_text(item.get("id"))
    return ""


def _looks_not_found_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "404" in text or "not found" in text


def _looks_already_exists_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "already exists" in text or "already exist" in text


def _update_existing_ref_entry(
    refs: list[dict[str, Any]], integration: str, ref_id: str, ref_key: str, ref_url: str
) -> bool:
    for item in refs:
        if _normalize_ref_text(item.get("integration")).lower() != integration:
            continue
        if ref_id:
            item["id"] = ref_id
        if ref_key:
            item["key"] = ref_key
        if ref_url:
            item["url"] = ref_url
        return True
    return False


def _append_ref_entry(
    refs: list[dict[str, Any]], integration: str, ref_id: str, ref_key: str, ref_url: str
) -> None:
    entry: dict[str, str] = {"integration": integration}
    if ref_id:
        entry["id"] = ref_id
    if ref_key:
        entry["key"] = ref_key
    if ref_url:
        entry["url"] = ref_url
    refs.append(entry)


def _update_ticket_integration_fields(
    ticket: dict[str, Any], integration: str, ref_id: str, ref_key: str, ref_url: str
) -> None:
    if ref_id:
        ticket[f"{integration}_id"] = ref_id
        ticket.setdefault("external_id", ref_id)
    if ref_key:
        ticket[f"{integration}_key"] = ref_key
    if ref_url:
        ticket[f"{integration}_url"] = ref_url
        ticket.setdefault("external_url", ref_url)


def _attach_external_ref(ticket: dict[str, Any], integration: str, ref: dict[str, str]) -> None:
    ref_id = _normalize_ref_text(ref.get("id"))
    ref_key = _normalize_ref_text(ref.get("key"))
    ref_url = _normalize_ref_url(ref.get("url"))
    if not (ref_id or ref_key or ref_url):
        return

    refs = _iter_external_refs(ticket)
    if not _update_existing_ref_entry(refs, integration, ref_id, ref_key, ref_url):
        _append_ref_entry(refs, integration, ref_id, ref_key, ref_url)

    ticket["external_refs"] = refs
    _update_ticket_integration_fields(ticket, integration, ref_id, ref_key, ref_url)


def _resolve_update_reference(backend: Any, ticket: dict[str, Any], integration: str) -> dict[str, str]:
    for candidate in _collect_external_ref_candidates(ticket, integration):
        if candidate["id"]:
            return candidate

        query = candidate["url"] or candidate["key"]
        if not query:
            continue

        try:
            matches = backend.search_tickets(query)
        except Exception:
            continue

        if not isinstance(matches, list) or not matches:
            continue

        match_id = _extract_search_ticket_id(matches[0])
        if match_id:
            return {
                "id": match_id,
                "key": candidate["key"],
                "url": candidate["url"],
            }

    return {}


def _extract_json_payload(text: str) -> dict[str, Any]:
    """Extract first valid JSON object from command output."""
    content = str(text or "").strip()
    if not content:
        return {}

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(content[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return {}


def _resolve_scenario_path(scenario_path: str | Path, project_root: Path) -> Path:
    scenario = Path(scenario_path)
    if scenario.is_absolute():
        return scenario
    return (project_root / scenario).resolve()


def _resolve_testql_executable(testql_bin: str, testql_repo_path: str | Path) -> str:
    """Resolve TestQL executable, preferring explicit binary then local repo checkout."""
    explicit = Path(testql_bin)
    if explicit.is_absolute() and explicit.exists():
        return str(explicit)

    if shutil.which(testql_bin):
        return testql_bin

    repo = Path(testql_repo_path)
    repo_candidates = [
        repo / ".venv" / "bin" / "testql",
        repo / "venv" / "bin" / "testql",
        repo / "bin" / "testql",
    ]
    for candidate in repo_candidates:
        if candidate.exists():
            return str(candidate)

    return testql_bin


def run_testql_validation(
    scenario_path: str | Path,
    project_path: str | Path = ".",
    *,
    url: str = "http://localhost:8101",
    dry_run: bool = False,
    quiet: bool = True,
    testql_bin: str = "testql",
    testql_repo_path: str | Path = "/home/tom/github/oqlos/testql",
) -> dict[str, Any]:
    """Run TestQL scenario and return normalized validation report."""
    project_root = Path(project_path).resolve()
    scenario = _resolve_scenario_path(scenario_path, project_root)

    resolved_testql = _resolve_testql_executable(testql_bin, testql_repo_path)

    cmd = [
        resolved_testql,
        "run",
        str(scenario),
        "--url",
        url,
        "--output",
        "json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    if quiet:
        cmd.append("--quiet")

    proc = subprocess.run(
        cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    report = _extract_json_payload(proc.stdout)
    if not report:
        report = {
            "source": str(scenario),
            "ok": proc.returncode == 0,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "errors": [line for line in [proc.stderr.strip(), proc.stdout.strip()] if line],
            "warnings": [],
        }

    report.setdefault("source", str(scenario))
    report.setdefault("ok", proc.returncode == 0)
    report.setdefault("passed", 0)
    report.setdefault("failed", 0)
    report.setdefault("total", 0)
    report.setdefault("errors", [])
    report.setdefault("warnings", [])

    report["exit_code"] = proc.returncode
    report["command"] = " ".join(cmd)
    report["testql_executable"] = resolved_testql
    report["stdout"] = proc.stdout
    report["stderr"] = proc.stderr
    report["scenario"] = str(scenario)
    report["project_path"] = str(project_root)
    return report


def _collect_step_messages(steps_raw: Any) -> list[str]:
    messages: list[str] = []
    if not isinstance(steps_raw, list):
        return messages
    for step in steps_raw:
        if not isinstance(step, dict):
            continue
        if str(step.get("status") or "").lower() not in {"failed", "error"}:
            continue
        name = str(step.get("name") or "step")
        message = str(step.get("message") or "failed")
        messages.append(f"{name}: {message}")
    return messages


def _collect_error_messages(errors_raw: Any) -> list[str]:
    if isinstance(errors_raw, list):
        values = errors_raw
    elif errors_raw is None:
        values = []
    else:
        values = [errors_raw]
    return [str(err or "").strip() for err in values if str(err or "").strip()]


def _dedupe_messages(messages: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for message in messages:
        if message not in seen:
            unique.append(message)
            seen.add(message)
    return unique


def _collect_failure_messages(report: dict[str, Any]) -> list[str]:
    """Collect normalized failure messages from TestQL report."""
    messages = _collect_step_messages(report.get("steps", []))
    messages += _collect_error_messages(report.get("errors", []))

    if not messages and int(report.get("failed") or 0) > 0:
        messages.append("One or more TestQL checks failed without detailed error output")

    return _dedupe_messages(messages)


def _extract_file_from_message(message: str) -> str | None:
    """Best-effort extraction of file path from a failure message."""
    match = re.search(r"([\w./-]+\.[A-Za-z0-9]+)", message)
    if not match:
        return None
    return match.group(1)


def build_testql_tickets(
    report: dict[str, Any],
    scenario_path: str | Path,
    *,
    max_tickets: int = 25,
) -> list[dict[str, Any]]:
    """Build planfile task entries from a TestQL report."""
    if bool(report.get("ok")):
        return []

    scenario = Path(scenario_path)
    scenario_label = scenario.name
    failures = _collect_failure_messages(report)[: max(1, int(max_tickets or 25))]

    tickets: list[dict[str, Any]] = []
    for idx, failure in enumerate(failures, start=1):
        digest = hashlib.sha1(f"{scenario_label}|{failure}".encode()).hexdigest()[:10]
        ticket_id = f"TQL-{digest}"
        short_failure = failure if len(failure) <= 88 else f"{failure[:85]}..."
        title = f"testql: {scenario_label} :: {short_failure}"
        file_path = _extract_file_from_message(failure)

        description_lines = [
            f"TestQL scenario failed: {scenario}",
            "",
            f"Failure #{idx}:",
            failure,
            "",
            "Runbook:",
            f"- Re-run: testql run {scenario} --output json",
            "- Fix failing DSL expectation or implementation code.",
        ]

        ticket: dict[str, Any] = {
            "id": ticket_id,
            "title": title,
            "description": "\n".join(description_lines),
            "action": "fix",
            "priority": 2,
            "status": "todo",
            "labels": ["testql", "dsl-validation", "auto-generated"],
            "source": "testql",
        }
        if file_path:
            ticket["file"] = file_path

        tickets.append(ticket)

    return tickets


def _default_strategy_payload() -> dict[str, Any]:
    return {
        "schema": "1.0",
        "tasks": [],
        "sprints": [
            {
                "id": "sprint-1",
                "name": "Code Quality Improvements",
                "duration": "2 weeks",
                "objectives": ["Fix code quality issues"],
                "task_patterns": [],
            }
        ],
    }


def _load_or_init_strategy(strategy_file: Path) -> dict[str, Any]:
    if strategy_file.exists():
        loaded = yaml.safe_load(strategy_file.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else {}
    return _default_strategy_payload()


def _ensure_strategy_lists(
    strategy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tasks = strategy.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
        strategy["tasks"] = tasks

    sprints = strategy.get("sprints")
    if not isinstance(sprints, list) or not sprints:
        sprints = _default_strategy_payload()["sprints"]
        strategy["sprints"] = sprints

    sprint = sprints[0] if isinstance(sprints[0], dict) else {}
    if not isinstance(sprints[0], dict):
        sprints[0] = sprint
    task_patterns = sprint.get("task_patterns")
    if not isinstance(task_patterns, list):
        task_patterns = []
        sprint["task_patterns"] = task_patterns

    return tasks, task_patterns, sprint


def _build_task_pattern_entry(ticket: dict[str, Any], ticket_id: str) -> dict[str, Any]:
    return {
        "id": ticket_id,
        "name": ticket.get("title") or ticket.get("name") or ticket_id,
        "description": ticket.get("description", ""),
        "task_type": "fix",
        "model_hints": {"planning": "balanced", "implementation": "balanced"},
        "priority": "high",
        "status": "todo",
        "file": ticket.get("file", ""),
    }


def _upsert_single_ticket(
    ticket: dict[str, Any],
    tasks: list[dict[str, Any]],
    task_patterns: list[dict[str, Any]],
    existing_task_ids: set[str],
    existing_pattern_ids: set[str],
    existing_identity_keys: set[str],
) -> bool:
    ticket_id = str(ticket.get("id") or "").strip()
    if not ticket_id:
        return False
    ticket_identity_keys = _collect_ticket_identity_keys(ticket)
    if ticket_id in existing_task_ids or any(k in existing_identity_keys for k in ticket_identity_keys):
        return False

    tasks.append(ticket)
    existing_task_ids.add(ticket_id)
    existing_identity_keys.update(ticket_identity_keys)

    if ticket_id not in existing_pattern_ids:
        task_patterns.append(_build_task_pattern_entry(ticket, ticket_id))
        existing_pattern_ids.add(ticket_id)

    return True


def upsert_testql_tickets(
    strategy_path: str | Path,
    tickets: list[dict[str, Any]],
    *,
    project_path: str | Path = ".",
) -> dict[str, Any]:
    """Upsert TestQL tickets into planfile.yaml tasks and sprint task_patterns."""
    project_root = Path(project_path).resolve()
    strategy_file = Path(strategy_path)
    if not strategy_file.is_absolute():
        strategy_file = (project_root / strategy_file).resolve()

    strategy = _load_or_init_strategy(strategy_file)
    tasks, task_patterns, _sprint = _ensure_strategy_lists(strategy)

    existing_task_ids = {str(t.get("id")) for t in tasks if isinstance(t, dict) and t.get("id")}
    existing_pattern_ids = {str(p.get("id")) for p in task_patterns if isinstance(p, dict) and p.get("id")}
    existing_identity_keys: set[str] = set()
    for existing_task in tasks:
        if isinstance(existing_task, dict):
            existing_identity_keys.update(_collect_ticket_identity_keys(existing_task))

    created_ids: list[str] = []
    skipped_ids: list[str] = []

    for ticket in tickets:
        if not isinstance(ticket, dict):
            continue
        ticket_id = str(ticket.get("id") or "").strip()
        if not ticket_id:
            continue
        if _upsert_single_ticket(
            ticket, tasks, task_patterns,
            existing_task_ids, existing_pattern_ids, existing_identity_keys,
        ):
            created_ids.append(ticket_id)
        else:
            skipped_ids.append(ticket_id)

    strategy_file.write_text(
        yaml.safe_dump(strategy, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    return {
        "strategy_path": str(strategy_file),
        "created": len(created_ids),
        "skipped": len(skipped_ids),
        "created_ticket_ids": created_ids,
        "skipped_ticket_ids": skipped_ids,
    }


def _resolve_sync_backend(config: Any, integration: str) -> Any:
    if integration == "markdown":
        return config.get_default_backend()
    return config.get_integration_backend(integration)


def _sync_ticket_to_backend(
    ticket: dict[str, Any], backend: Any, integration: str
) -> tuple[str, int]:
    update_ref = _resolve_update_reference(backend, ticket, integration)
    if update_ref.get("id"):
        try:
            backend.update_ticket(
                update_ref["id"],
                name=ticket.get("name") or ticket.get("title"),
                body=ticket.get("description") or ticket.get("body"),
                status=ticket.get("status"),
                labels=ticket.get("labels"),
                priority=ticket.get("priority"),
                assignee=ticket.get("assignee"),
            )
            _attach_external_ref(ticket, integration, update_ref)
            return "updated", 1
        except Exception as exc:
            if not _looks_not_found_error(exc):
                raise
    created_ref = _extract_created_ticket_ref(backend.create_ticket(ticket))
    _attach_external_ref(ticket, integration, created_ref)
    return "created", 1


def _sync_tickets_to_integration(
    tickets: list[dict[str, Any]], backend: Any, integration: str
) -> dict[str, Any]:
    created = updated = skipped = failed = 0
    for ticket in tickets:
        try:
            outcome, _ = _sync_ticket_to_backend(ticket, backend, integration)
            if outcome == "updated":
                updated += 1
            else:
                created += 1
        except Exception as exc:
            if _looks_already_exists_error(exc):
                skipped += 1
            else:
                failed += 1
    return {"integration": integration, "created": created, "updated": updated, "skipped": skipped, "failed": failed}


def sync_testql_tickets(
    tickets: list[dict[str, Any]],
    *,
    project_path: str | Path = ".",
    include_configured: bool = True,
) -> dict[str, Any]:
    """Sync generated TestQL tickets to markdown first, then configured integrations."""
    project_root = Path(project_path).resolve()
    config = IntegrationConfig(str(project_root))
    config.load_configs()

    sync_order: list[str] = ["markdown"]
    if include_configured:
        for name in (config.config.get("integrations") or {}).keys():
            if name != "markdown":
                sync_order.append(name)

    integrations_report: list[dict[str, Any]] = []
    for integration in sync_order:
        try:
            if integration != "markdown" and not config.validate_integration(integration):
                integrations_report.append(
                    {"integration": integration, "created": 0, "skipped": 0, "failed": len(tickets), "error": "integration_not_configured"}
                )
                continue
            backend = _resolve_sync_backend(config, integration)
            integrations_report.append(_sync_tickets_to_integration(tickets, backend, integration))
        except Exception as exc:
            integrations_report.append(
                {"integration": integration, "created": 0, "updated": 0, "skipped": 0, "failed": len(tickets), "error": str(exc)}
            )

    return {
        "sync_order": sync_order,
        "integrations": integrations_report,
    }
