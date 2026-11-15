"""CLI commands for ``in_progress`` reconciliation and canonical executable queue reporting."""

from __future__ import annotations

import json
import sys
from typing import Any

import typer
import yaml
from rich.table import Table

from planfile.cli.core import console


def _emit_structured(payload: dict[str, Any], fmt: str) -> bool:
    normalized = fmt.strip().lower()
    if normalized == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=False) + "\n")
        return True
    if normalized == "yaml":
        sys.stdout.write(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        return True
    return False


def _render_reconcile_table(report: dict[str, Any]) -> None:
    counts = report["counts"]
    mode_label = "APPLIED" if report["mode"] == "apply" else "DRY-RUN"
    console.print(
        f"[bold]in_progress reconciliation ({mode_label})[/bold] — "
        f"scanned={counts['scanned_in_progress']} "
        f"merged->done={counts['merged_to_done']} "
        f"abandoned->open={counts['abandoned_to_open']} "
        f"active={counts['active_retained']} "
        f"unobserved={counts['unobserved_preserved']}"
    )
    decisions = report.get("decisions") or []
    if not decisions:
        console.print("[dim]No in_progress tickets found in scope.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("Ticket", style="cyan", no_wrap=True)
    table.add_column("Sprint")
    table.add_column("Class")
    table.add_column("Transition", no_wrap=True)
    table.add_column("Applied")
    table.add_column("Reason / Evidence")

    for item in decisions:
        evidence = str(item.get("reason") or "")
        if item.get("terminalSha"):
            evidence = f"{evidence} ({str(item['terminalSha'])[:12]})"
        elif item.get("leaseId"):
            evidence = f"{evidence}"
        table.add_row(
            str(item.get("id") or ""),
            str(item.get("sprint") or ""),
            str(item.get("classification") or ""),
            f"{item.get('previous_status')} -> {item.get('proposed_status')}",
            "yes" if item.get("applied") else "no",
            evidence,
        )
    console.print(table)


def _render_executable_queue_table(report: dict[str, Any]) -> None:
    counts = report["counts"]
    console.print(
        f"[bold]Executable Pending Queue ({report['schema']})[/bold] — "
        f"executable={counts['executable']} "
        f"open={counts['open']} "
        f"in_progress={counts['in_progress']} "
        f"excluded={counts['excluded']} "
        f"scanned={counts['total_scanned']}"
    )
    candidates = report.get("candidates") or []
    if not candidates:
        console.print("[dim]No executable candidates in scope.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Priority", no_wrap=True)
    table.add_column("Sprint", no_wrap=True)
    table.add_column("Repository")
    table.add_column("Name")

    for cand in candidates:
        table.add_row(
            str(cand.get("id") or ""),
            str(cand.get("priority") or "normal"),
            str(cand.get("sprint") or "current"),
            str(cand.get("repository") or cand.get("repo_path") or ""),
            str(cand.get("name") or ""),
        )
    console.print(table)


def ticket_reconcile(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    sprint: str = typer.Option(
        "active",
        "--sprint",
        "-s",
        help="Sprint scope ('active', 'current', 'backlog', 'all', or sprint ID)",
    ),
    workspace_root: str | None = typer.Option(
        None,
        "--workspace-root",
        "-w",
        help="Workspace directory for resolving external target repositories",
    ),
    fleet: bool = typer.Option(
        False,
        "--fleet",
        help="Reconcile all .planfile repositories discovered under workspace root",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Atomically apply status transitions (default is dry-run report)",
    ),
    actor: str = typer.Option(
        "planfile.reconcile",
        "--actor",
        help="Audit actor recorded when --apply mutates tickets",
    ),
    fmt: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """Reconcile in_progress tickets with live leases, worktrees, and merge receipts."""
    if fmt.strip().lower() not in {"table", "json", "yaml"}:
        console.print(f"[red]Unsupported format: {fmt} (choose table, json, or yaml)[/red]")
        raise typer.Exit(2)

    from planfile.reconcile import reconcile_fleet_in_progress, reconcile_in_progress

    if fleet:
        root_dir = workspace_root or project
        report = reconcile_fleet_in_progress(
            root_dir,
            apply=apply,
            sprint=sprint,
            actor=actor,
        )
    else:
        report = reconcile_in_progress(
            project,
            apply=apply,
            sprint=sprint,
            workspace_root=workspace_root,
            actor=actor,
        )

    if not _emit_structured(report, fmt):
        _render_reconcile_table(report)


def ticket_executable_queue(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    sprint: str = typer.Option(
        "active",
        "--sprint",
        "-s",
        help="Sprint scope ('active', 'current', 'backlog', 'all', or sprint ID)",
    ),
    workspace_root: str | None = typer.Option(
        None,
        "--workspace-root",
        "-w",
        help="Workspace directory for resolving external target repositories",
    ),
    fleet: bool = typer.Option(
        False,
        "--fleet",
        help="Aggregate canonical executable queue across all fleet repositories",
    ),
    queue: str | None = typer.Option(
        None,
        "--queue",
        "-q",
        help="Filter candidates by execution queue name",
    ),
    fmt: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, or yaml",
    ),
) -> None:
    """Evaluate and report the canonical planfile.executable-queue/v1 pending queue."""
    if fmt.strip().lower() not in {"table", "json", "yaml"}:
        console.print(f"[red]Unsupported format: {fmt} (choose table, json, or yaml)[/red]")
        raise typer.Exit(2)

    from planfile.executable_queue import executable_queue, fleet_executable_queue

    if fleet:
        root_dir = workspace_root or project
        report = fleet_executable_queue(
            root_dir,
            sprint=sprint,
            queue=queue,
        )
    else:
        report = executable_queue(
            project,
            sprint=sprint,
            workspace_root=workspace_root,
            queue=queue,
        )

    if not _emit_structured(report, fmt):
        _render_executable_queue_table(report)
