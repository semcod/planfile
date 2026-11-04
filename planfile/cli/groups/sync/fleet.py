"""Fleet GitHub synchronization across local repositories with 6h schedule integration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from planfile.cli.core import console, print_error, print_success
from planfile.cli.groups.sync.core import sync_integration
from planfile.integrations.config import IntegrationConfig

DEFAULT_INTERVAL_HOURS = 6
SERVICE_NAME = "planfile-fleet-sync.service"
TIMER_NAME = "planfile-fleet-sync.timer"


def get_systemd_user_dir() -> Path:
    """Return user systemd directory, creating it if needed."""
    user_dir = Path.home() / ".config" / "systemd" / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def generate_service_content(root: Path | None = None, planfile_bin: str | None = None) -> str:
    """Generate systemd user service unit content."""
    root_str = str(root.resolve()) if root else "%h/github"
    bin_str = planfile_bin or shutil.which("planfile") or "%h/miniconda3/bin/planfile"
    return f"""[Unit]
Description=Planfile Fleet GitHub Inbound Synchronization
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart={bin_str} sync fleet {root_str}
TimeoutStartSec=20min
Nice=10
UMask=0077
NoNewPrivileges=true
"""


def generate_timer_content(interval_hours: int = DEFAULT_INTERVAL_HOURS) -> str:
    """Generate systemd user timer unit content."""
    return f"""[Unit]
Description=Run Planfile Fleet GitHub synchronization every {interval_hours} hours

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval_hours}h
Persistent=true
Unit={SERVICE_NAME}

[Install]
WantedBy=timers.target
"""


def install_fleet_systemd_timer(
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    root: Path | None = None,
) -> tuple[bool, str]:
    """Install and enable systemd user service and timer."""
    user_dir = get_systemd_user_dir()
    service_path = user_dir / SERVICE_NAME
    timer_path = user_dir / TIMER_NAME

    service_path.write_text(generate_service_content(root=root), encoding="utf-8")
    timer_path.write_text(generate_timer_content(interval_hours=interval_hours), encoding="utf-8")

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True, text=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", TIMER_NAME], check=True, capture_output=True, text=True)
        return True, f"Installed and started {TIMER_NAME} (cycle: every {interval_hours}h)"
    except Exception as exc:
        return False, f"Failed to activate systemd timer: {exc}"


def uninstall_fleet_systemd_timer() -> tuple[bool, str]:
    """Disable and remove systemd user service and timer."""
    user_dir = get_systemd_user_dir()
    service_path = user_dir / SERVICE_NAME
    timer_path = user_dir / TIMER_NAME

    try:
        subprocess.run(["systemctl", "--user", "disable", "--now", TIMER_NAME], check=False, capture_output=True, text=True)
    except Exception:
        pass

    if service_path.exists():
        service_path.unlink()
    if timer_path.exists():
        timer_path.unlink()

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True, text=True)
    except Exception:
        pass

    return True, f"Uninstalled {TIMER_NAME} and {SERVICE_NAME}"


def status_fleet_systemd_timer() -> str:
    """Check status of the systemd fleet timer."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "status", TIMER_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout or res.stderr
    except Exception as exc:
        return f"Could not inspect systemctl: {exc}"


def discover_fleet_repositories(
    root: Path,
    max_depth: int = 2,
) -> list[tuple[Path, str]]:
    """Scan subdirectories up to max_depth for .planfile stores configured with GitHub."""
    results: list[tuple[Path, str]] = []
    if not root.is_dir():
        return results

    # Breadth-first search bounded by max_depth
    queue: list[tuple[Path, int]] = [(root, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth > 0:
            try:
                planfile_dir = current / ".planfile"
                if planfile_dir.is_dir():
                    try:
                        config = IntegrationConfig(str(current))
                        config.load_configs()
                        gh_cfg = config.get_integration_config("github")
                        repo_name = gh_cfg.get("repo") if isinstance(gh_cfg, dict) else None
                        if repo_name and config.validate_integration("github"):
                            results.append((current, str(repo_name)))
                    except Exception:
                        pass
                    # Once a repository with .planfile is matched, do not descend into internal subtrees
                    continue
            except (PermissionError, OSError):
                continue

        if depth < max_depth:
            try:
                for entry in sorted(current.iterdir()):
                    if entry.is_dir() and not entry.name.startswith(".") and not entry.is_symlink():
                        queue.append((entry, depth + 1))
            except PermissionError:
                continue

    return results


def sync_fleet(
    root: Path,
    max_depth: int = 2,
    dry_run: bool = False,
    exclude_incident_noise: bool = True,
    managed_only: bool = False,
    max_projects: int | None = None,
) -> dict[str, Any]:
    """Execute inbound sync across all discovered fleet repositories."""
    discovered = discover_fleet_repositories(root, max_depth=max_depth)
    if max_projects:
        discovered = discovered[:max_projects]

    stats: dict[str, Any] = {
        "scanned": len(discovered),
        "synced": 0,
        "failed": 0,
        "results": [],
    }

    if not discovered:
        console.print(f"[dim]ℹ️ No GitHub-integrated repositories found under {root}[/dim]")
        return stats

    console.print(f"\n[bold blue]🚀 Starting Fleet Sync across {len(discovered)} repositories...[/bold blue]")
    console.print(f"[dim]   Root: {root} (depth: {max_depth})[/dim]")
    console.print("[dim]   Direction: from (inbound GitHub ➔ Planfile)[/dim]")
    console.print(f"[dim]   Filter incident noise: {exclude_incident_noise}[/dim]")
    console.print(f"[dim]   Managed labels only: {managed_only}[/dim]\n")

    for repo_path, gh_repo in discovered:
        repo_name = repo_path.name
        console.print(f"[bold cyan]📁 {repo_name}[/bold cyan] [dim]({gh_repo})[/dim]")
        try:
            sync_integration(
                "github",
                str(repo_path),
                dry_run=dry_run,
                direction="from",
                show_header=False,
                managed_only=managed_only,
                exclude_incident_noise=exclude_incident_noise,
            )
            stats["synced"] += 1
            stats["results"].append({"repo": repo_name, "github": gh_repo, "status": "ok"})
        except Exception as exc:
            stats["failed"] += 1
            stats["results"].append({
                "repo": repo_name,
                "github": gh_repo,
                "status": "error",
                "error": str(exc),
            })
            console.print(f"  [red]✗ Sync error for {repo_name}: {exc}[/red]")

    return stats


def fleet_cmd(
    root: str = typer.Argument(
        str(Path.home() / "github"),
        help="Root directory containing repositories (e.g. ~/github)",
    ),
    depth: int = typer.Option(2, "--depth", "-d", help="Directory search depth (default: 2 for ~/github/*/*)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview sync without saving changes"),
    exclude_incident_noise: bool = typer.Option(
        True,
        "--exclude-incident-noise/--include-incidents",
        help="Filter out transient browser/system crash dumps and incident logs",
    ),
    managed_only: bool = typer.Option(
        False,
        "--managed-only",
        help="Only sync issues with 'planfile' or 'managed' labels",
    ),
    install_timer: bool = typer.Option(
        False,
        "--install-timer",
        help="Install and activate 6-hour systemd user timer for automated fleet sync",
    ),
    uninstall_timer: bool = typer.Option(
        False,
        "--uninstall-timer",
        help="Uninstall and deactivate systemd user timer",
    ),
    status_timer: bool = typer.Option(
        False,
        "--status-timer",
        help="Show status of systemd fleet timer",
    ),
    interval_hours: int = typer.Option(
        DEFAULT_INTERVAL_HOURS,
        "--interval-hours",
        "-i",
        help="Timer interval in hours (default: 6)",
    ),
) -> None:
    """Synchronize GitHub issues into local Planfile backlogs across a fleet of projects."""
    if install_timer:
        ok, msg = install_fleet_systemd_timer(interval_hours=interval_hours, root=Path(root))
        if ok:
            print_success(msg)
        else:
            print_error(msg)
            raise typer.Exit(1)
        return

    if uninstall_timer:
        ok, msg = uninstall_fleet_systemd_timer()
        print_success(msg)
        return

    if status_timer:
        status_output = status_fleet_systemd_timer()
        console.print(status_output)
        return

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        print_error(f"Root path does not exist: {root_path}")
        raise typer.Exit(1)

    stats = sync_fleet(
        root_path,
        max_depth=depth,
        dry_run=dry_run,
        exclude_incident_noise=exclude_incident_noise,
        managed_only=managed_only,
    )

    table = Table(title="Fleet Sync Summary", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("GitHub Target", style="dim")
    table.add_column("Status", justify="center")

    for res in stats["results"]:
        status_styled = "[green]✓ synced[/green]" if res["status"] == "ok" else f"[red]✗ {res.get('error', 'failed')}[/red]"
        table.add_row(res["repo"], res["github"], status_styled)

    console.print(table)
    console.print(
        f"[bold]Total scanned:[/bold] {stats['scanned']} | "
        f"[green bold]Synced:[/green bold] {stats['synced']} | "
        f"[red bold]Failed:[/red bold] {stats['failed']}\n"
    )
