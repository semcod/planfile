"""Core sync logic for planfile CLI."""

from __future__ import annotations

import glob
from copy import deepcopy
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.progress import Progress, SpinnerColumn, TextColumn

from planfile.cli.core import console, print_error, print_warning
from planfile.integrations.config import IntegrationConfig
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import (
    _bind_sync_state,
    _extract_ticket_data,
    _ticket_external_id,
    sync_from_external,
)
from planfile.sync.outbound import OutboundSyncError, sync_to_external
from planfile.sync.ticket_comments import sync_pending_comments


def _initialize_backend(integration_name: str, config: IntegrationConfig, show_header: bool) -> Any:
    """Initialize and validate backend for sync operation."""
    # Special handling for markdown backend (default when no integrations configured)
    if integration_name == "markdown":
        backend = config.get_default_backend()
        if show_header:
            console.print("✅ Using default markdown backend (CHANGELOG.md, TODO.md)")
        return backend

    # Validate integration for other backends
    if not config.validate_integration(integration_name):
        print_error(f"{integration_name} integration not configured or invalid")
        raise typer.Exit(1)

    # Get backend
    try:
        backend = config.get_integration_backend(integration_name)
        if show_header:
            console.print(f"✅ Connected to {integration_name}")
    except Exception as e:
        print_error(f"Failed to connect to {integration_name}: {e}")
        raise typer.Exit(1) from e

    return backend


def _apply_github_overrides(
    config: IntegrationConfig,
    repo: str | None,
) -> None:
    """Apply explicit CLI overrides before validating the GitHub backend."""
    if not repo:
        return

    integrations = config.config.setdefault("integrations", {})
    github = dict(integrations.get("github") or {})
    if repo:
        github["repo"] = repo
    integrations["github"] = github


def _ticket_matches_integration(ticket: dict, integration_name: str) -> bool:
    """Check if ticket matches the given integration."""
    ticket_integration = ticket.get("integration")
    if not ticket_integration:
        return False
    if isinstance(ticket_integration, list):
        return integration_name in ticket_integration
    return ticket_integration == integration_name


def _collect_tickets_from_sprint(
    sprint: dict | None, integration_name: str
) -> list[tuple[str, dict]]:
    """Collect tickets from sprint matching integration."""
    if not sprint:
        return []
    tickets = []
    for ticket_id, ticket in sprint.get("tickets", {}).items():
        if _ticket_matches_integration(ticket, integration_name):
            tickets.append((ticket_id, ticket))
    return tickets


def _collect_tickets_from_backlog(
    backlog: dict | None, integration_name: str
) -> list[tuple[str, dict]]:
    """Collect tickets from backlog matching integration."""
    if not backlog:
        return []
    tickets = []
    for ticket_id, ticket in backlog.get("tickets", {}).items():
        if _ticket_matches_integration(ticket, integration_name):
            tickets.append((ticket_id, ticket))
    return tickets


def _ticket_matches_integration_v1(ticket: dict, integration_name: str) -> bool:
    """Check if a v1 format ticket matches the integration."""
    ticket_integration = ticket.get("integration", integration_name)
    if isinstance(ticket_integration, list):
        return integration_name in ticket_integration
    return ticket_integration == integration_name


def _collect_tickets_from_section(
    data: dict, section: str, integration_name: str
) -> list[tuple[str, dict]]:
    """Collect tickets from a specific section (sprint or backlog)."""
    tickets = []
    section_data = data.get(section, {})
    for ticket_id, ticket in section_data.get("tickets", {}).items():
        if _ticket_matches_integration_v1(ticket, integration_name):
            tickets.append((ticket_id, ticket))
    return tickets


def _process_planfile_v1(
    planfile_path: str,
    integration_name: str,
    all_tickets: list,
    tickets_source: str | None,
    v1_source_file: str | None,
    v1_data: dict | None,
) -> tuple:
    """Process a single v1 planfile and extract tickets. Returns updated (tickets_source, v1_source_file, v1_data)."""
    try:
        with open(planfile_path) as f:
            data = yaml.safe_load(f) or {}

        has_sprint = "sprint" in data and "tickets" in data.get("sprint", {})
        has_backlog = "backlog" in data and "tickets" in data.get("backlog", {})

        # Process sprint section
        if has_sprint:
            if tickets_source is None:
                tickets_source = f"{Path(planfile_path).name} (sprint)"
                v1_source_file = planfile_path
                v1_data = data
            all_tickets.extend(_collect_tickets_from_section(data, "sprint", integration_name))

        # Process backlog section
        if has_backlog:
            if tickets_source is None:
                tickets_source = f"{Path(planfile_path).name} (backlog)"
                v1_source_file = planfile_path
                v1_data = data
            all_tickets.extend(_collect_tickets_from_section(data, "backlog", integration_name))

    except Exception as e:
        console.print(f"[dim]⚠️ Could not load {planfile_path}: {e}[/dim]")

    return tickets_source, v1_source_file, v1_data


def _load_tickets_v1_format(
    directory: str, integration_name: str
) -> tuple[list[tuple[str, dict]], str | None, str | None, dict | None]:
    """Load tickets from v1 format (*.planfile.yaml files)."""
    all_tickets = []
    tickets_source = None
    v1_source_file = None
    v1_data = None

    planfile_pattern = Path(directory) / "*.planfile.yaml"
    for planfile_path in glob.glob(str(planfile_pattern)):
        tickets_source, v1_source_file, v1_data = _process_planfile_v1(
            planfile_path, integration_name, all_tickets, tickets_source, v1_source_file, v1_data
        )

    return all_tickets, tickets_source, v1_source_file, v1_data


def _load_tickets_for_sync(
    store: Any,
    directory: str,
    integration_name: str,
    ticket_ids: list[str] | None = None,
    sprint_ids: list[str] | None = None,
) -> tuple[list[tuple[str, dict]], str | None, str | None, dict | None]:
    """Load tickets from all sources for sync operation."""
    tickets_source = None
    v1_source_file = None
    v1_data = None
    all_tickets = []

    # Try 1: New .planfile/ structure. Completed tickets are moved to
    # history-* sprints, but their mapped external issue still needs its final
    # state synchronized. Iterate every sprint rather than only ``current``.
    if store.is_initialized():
        tickets_source = ".planfile/ structure"
        seen_ids: set[str] = set()
        requested_tickets = {str(value).strip() for value in (ticket_ids or []) if str(value).strip()}
        requested_sprints = {str(value).strip() for value in (sprint_ids or []) if str(value).strip()}
        available_sprints = store._all_sprint_ids()
        sprint_scan = (
            [sprint for sprint in available_sprints if sprint in requested_sprints]
            if requested_sprints
            else available_sprints
        )
        for sprint_id in sprint_scan:
            sprint = store.load_sprint(sprint_id)
            for ticket_id, ticket in _collect_tickets_from_sprint(sprint, integration_name):
                if requested_tickets and ticket_id not in requested_tickets:
                    continue
                # A physical ticket ID is the Planfile identity. If an
                # interrupted move leaves it in two sprints, publish one
                # deterministic record and keep the first source visible for
                # later reconciliation instead of creating duplicate issues.
                if ticket_id in seen_ids:
                    console.print(
                        f"[yellow]⚠️ Duplicate local ticket {ticket_id}; "
                        f"ignoring sprint {sprint_id}[/yellow]"
                    )
                    continue
                seen_ids.add(ticket_id)
                all_tickets.append((ticket_id, ticket))

    # Try 2: Old format v1 (*.planfile.yaml files with sprint/backlog sections)
    if not all_tickets:
        v1_tickets, tickets_source, v1_source_file, v1_data = _load_tickets_v1_format(
            directory, integration_name
        )
        all_tickets.extend(v1_tickets)

    if ticket_ids:
        requested_tickets = {str(value).strip() for value in ticket_ids if str(value).strip()}
        all_tickets = [item for item in all_tickets if item[0] in requested_tickets]

    return all_tickets, tickets_source, v1_source_file, v1_data


class _InboundObservation:
    """Retain this pass's provider states without changing backend capabilities."""

    project_remote_status = staticmethod(GitHubBackend.project_remote_status)

    def __init__(self, backend, legacy_plans=None):
        self.backend = backend
        self.states = {}
        self.legacy_plans = legacy_plans or {}
        self.guard = None

    def resolve_repository_identity(self, *args, **kwargs):
        resolver = getattr(type(self.backend), "resolve_repository_identity", None)
        return resolver(self.backend, *args, **kwargs) if callable(resolver) else None

    def _bind_repository_identity(self, identity):
        binder = getattr(type(self.backend), "_bind_repository_identity", None)
        if callable(binder):
            binder(self.backend, identity)

    def update_ticket(self, remote_id, **changes):
        if self.guard is not None:
            self.guard()
        # Lifecycle belongs to inbound in both. A closure after that read
        # must survive a later metadata edit; normal readback reports drift.
        changes.pop("status", None)
        return self.backend.update_ticket(remote_id, **changes)

    def create_ticket(self, ticket):
        if self.guard is not None:
            self.guard()
        return self.backend.create_ticket(ticket)

    def __getattr__(self, name):
        value = getattr(self.backend, name)
        if name not in {"list_tickets", "list_selected_tickets"} or not callable(value):
            return value

        def observe(*args, **kwargs):
            result = value(*args, **kwargs)
            if result is None:
                return None
            tickets = deepcopy(list(result))
            for ticket in tickets:
                data = _extract_ticket_data(ticket)
                previous = self.states.setdefault(data["id"], data["status"])
                if previous != data["status"]:
                    raise ValueError("sync_inbound_conflicting_remote_states")
                if data["id"] in self.legacy_plans:
                    description = self.legacy_plans[data["id"]]
                    if isinstance(ticket, dict):
                        ticket["description"] = description
                    else:
                        ticket.description = description
            return tickets

        return observe


class _LocalPlanningStore:
    """Preserve this SDK snapshot's planning text while retaining normal CAS."""

    def __init__(self, store):
        self.store = store

    def __getattr__(self, name):
        return getattr(self.store, name)

    def update_ticket(self, ticket_id, **changes):
        snapshot = changes.get("expected_snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError("sync_planning_requires_snapshot")
        if "description" in changes:
            changes["description"] = snapshot.get("description", "")
        return self.store.update_ticket(ticket_id, **changes)



class _OutboundSnapshotStore:
    """Persist only backend references under exact native snapshot preconditions."""

    def __init__(self, store, tickets):
        self.store, self.payloads = store, dict(tickets)
        self.snapshots, self.rejected = {}, set()
        for key, payload in tickets:
            located = store._locate_ticket_source(key)
            if located is None or located[1] != payload:
                raise ValueError("sync_outbound_snapshot_changed")
            self.snapshots[key] = (located[0], deepcopy(located[1]))

    def __getattr__(self, name):
        return getattr(self.store, name)

    def check(self, key):
        located = self.store._locate_ticket_source(key)
        if located is None or located != self.snapshots[key]:
            raise ValueError("sync_outbound_snapshot_changed")

    def check_all(self):
        for key in self.snapshots:
            self.check(key)

    def _all_sprint_ids(self):
        return list(dict.fromkeys(section for section, _ in self.snapshots.values()))

    def load_sprint(self, section):
        return {"tickets": {key: deepcopy(data) for key, (physical, data) in self.snapshots.items()
                            if physical == section}}

    def save_sprint(self, section, data):
        pending = [(key, payload) for key, payload in data.get("tickets", {}).items()
                   if key in self.payloads and payload is self.payloads[key]]
        if not pending:
            raise ValueError("sync_outbound_payload_required")
        for key, payload in pending:
            if key in self.rejected:
                continue
            try:
                self.check(key)
                physical, snapshot = self.snapshots[key]
                if physical != section:
                    raise ValueError("sync_outbound_section_changed")
                reference = deepcopy(payload.get("sync") or {})
                if reference != (snapshot.get("sync") or {}):
                    saved = self.store.update_ticket(key, sync=reference, expected_snapshot=snapshot)
                    located, current = self.store._locate_ticket_source(key), self.store.get_ticket(key)
                    if (saved is None or current is None or located is None
                            or saved.model_dump(mode="json") != current.model_dump(mode="json")
                            or any(located[1].get(k) != snapshot.get(k)
                                   for k in set(located[1]) | set(snapshot)
                                   if k not in {"sync", "updated_at", "history"})):
                        raise ValueError("sync_outbound_snapshot_changed")
                    self.snapshots[key] = (located[0], deepcopy(located[1]))
            except Exception:
                self.rejected.add(key)
                raise

    def save_backlog(self, data):
        self.save_sprint("backlog", data)


def _legacy_planning_descriptions(backend, store, tickets):
    state = _bind_sync_state(Path(store.base_dir), "github", backend, dry_run=True)
    plans = {}
    for ticket_id, ticket in tickets:
        remote_id = _ticket_external_id(ticket, ticket_id, "github", state)
        if remote_id is not None:
            description = ticket.get("description", "")
            if remote_id in plans and plans[remote_id] != description:
                raise ValueError("sync_ambiguous_local_planning")
            plans[remote_id] = description
    return plans


def _github_reconciled_outbound(backend, store, tickets, observed):
    """Leave native lifecycle conflicts and unobserved mappings for explicit sync."""
    state = _bind_sync_state(Path(store.base_dir), "github", backend, dry_run=True)
    eligible = []
    deferred = []
    for ticket_id, ticket in tickets:
        remote_id = _ticket_external_id(ticket, ticket_id, "github", state)
        if remote_id is not None and (
            remote_id not in observed
            or GitHubBackend.project_remote_status(ticket.get("status")) != observed[remote_id]
        ):
            deferred.append(ticket_id)
        else:
            eligible.append((ticket_id, ticket))
    if deferred:
        print_warning(
            f"Deferred {len(deferred)} mapped ticket(s): lifecycle conflict or no inbound "
            "observation. Reconcile intent before explicit --direction to."
        )
    return eligible, deferred


def _execute_sync_with_progress(
    backend: Any,
    all_tickets: list[tuple[str, dict]],
    dry_run: bool,
    store: Any,
    integration_name: str,
    v1_source_file: str | None,
    v1_data: dict | None,
    direction: str,
    publish_to: list[str] | None = None,
    ticket_ids: list[str] | None = None,
    sprint_ids: list[str] | None = None,
    remote_labels: list[str] | None = None,
    exclude_incident_noise: bool = False,
) -> None:
    """Execute sync; GitHub both observes inbound before outbound mutation."""
    inbound_first = integration_name == "github" and direction == "both"
    legacy_plans = (
        _legacy_planning_descriptions(backend, store, all_tickets)
        if inbound_first and v1_source_file else None
    )
    observer = _InboundObservation(backend, legacy_plans) if inbound_first else None
    inbound_store = _LocalPlanningStore(store) if inbound_first and not v1_source_file else store
    deferred = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        def pull():
            task = progress.add_task("Syncing from external system...", total=None)
            sync_from_external(
                observer if inbound_first else backend,
                inbound_store,
                dry_run,
                integration_name,
                v1_source_file,
                v1_data,
                publish_to=publish_to,
                ticket_ids=ticket_ids,
                sprint_ids=sprint_ids,
                remote_labels=remote_labels,
                exclude_incident_noise=exclude_incident_noise,
            )
            progress.update(task, description="[green]✓ Synced from external system[/green]")

        if inbound_first:
            pull()
            if dry_run:
                console.print(
                    "[dim]Outbound preview deferred: inbound dry-run is not persisted. "
                    "Use --direction to for a local-only outbound preview.[/dim]"
                )
                return
            all_tickets, _, v1_source_file, v1_data = _load_tickets_for_sync(
                store, str(store.project_dir), integration_name,
                ticket_ids=ticket_ids, sprint_ids=sprint_ids,
            )
            all_tickets, deferred = _github_reconciled_outbound(
                backend, store, all_tickets, observer.states
            )

        outbound_store = store
        if inbound_first and not v1_source_file:
            all_tickets = deepcopy(all_tickets)
            outbound_store = _OutboundSnapshotStore(store, all_tickets)
            observer.guard = outbound_store.check_all
        if direction in ["to", "both"] and (all_tickets or not inbound_first):
            task = progress.add_task("Syncing to external system...", total=None)
            sync_to_external(
                observer if inbound_first else backend, all_tickets, dry_run, outbound_store,
                integration_name, v1_source_file, v1_data
            )
            if inbound_first and not v1_source_file:
                outbound_store.check_all()
            progress.update(task, description="[green]✓ Synced to external system[/green]")

        if deferred:
            # Keep successful receipts, but do not claim the full selection is
            # synchronized or deliver queued comments for unresolved work.
            raise typer.Exit(2)

        if direction in ["from", "both"] and not inbound_first:
            pull()


def sync_integration(
    integration_name: str,
    directory: str,
    dry_run: bool,
    direction: str,
    show_header: bool = True,
    publish_to: list[str] | None = None,
    ticket_ids: list[str] | None = None,
    sprint_ids: list[str] | None = None,
    repo: str | None = None,
    managed_only: bool = False,
    incremental: bool = False,
    max_tickets: int = 2,
    exclude_incident_noise: bool = False,
) -> None:
    """Sync with a specific integration."""
    if show_header:
        console.print(f"🔄 Syncing with {integration_name}...")

    # Load configuration
    config = IntegrationConfig(directory)
    config.load_configs()
    if integration_name == "github":
        _apply_github_overrides(config, repo)

    if incremental:
        import json

        from planfile import Planfile
        from planfile.core.store import PlanfileStore
        from planfile.sync.incremental import sync_incremental

        if integration_name != 'github' or direction != 'to':
            print_error('Incremental sync requires github --direction to')
            raise typer.Exit(1)
        store = PlanfileStore(directory)
        if not store.is_initialized():
            print_error('Incremental sync requires an initialized native .planfile store')
            raise typer.Exit(1)
        selected, _, legacy, _ = _load_tickets_for_sync(
            store, directory, integration_name, ticket_ids=ticket_ids, sprint_ids=sprint_ids
        )
        if legacy:
            print_error('Incremental sync does not publish legacy v1 records')
            raise typer.Exit(1)
        try:
            outcome = sync_incremental(
                Planfile(directory), ticket_ids=[ident for ident, _ in selected],
                repository=config.get_integration_config('github').get('repo'),
                max_tickets=max_tickets, dry_run=dry_run,
            )
        except Exception:
            print_error('sync_incremental_failed: local state retained; remote completion unverified')
            raise typer.Exit(1) from None
        print(json.dumps(outcome))
        if outcome['failed']:
            raise typer.Exit(1)
        return

    # Initialize backend
    backend = _initialize_backend(integration_name, config, show_header)
    if publish_to is None:
        configured_targets = config.get_integration_config(integration_name).get("publish_to", [])
        publish_to = (
            [str(item) for item in configured_targets]
            if isinstance(configured_targets, list)
            else [str(configured_targets)]
            if configured_targets
            else []
        )

    # Load tickets from all sources
    from planfile.core.store import PlanfileStore

    store = PlanfileStore(directory)
    all_tickets, tickets_source, v1_source_file, v1_data = _load_tickets_for_sync(
        store, directory, integration_name, ticket_ids=ticket_ids, sprint_ids=sprint_ids
    )

    if not all_tickets and direction == "to":
        print_warning("No local tickets to sync to external system")
        console.print("[dim]   Searched: .planfile/ structure and *.planfile.yaml files[/dim]")
        return

    if all_tickets:
        console.print(
            f"📊 Found {len(all_tickets)} tickets for {integration_name} (source: {tickets_source})"
        )
    else:
        console.print(
            f"📊 Found 0 local tickets for {integration_name} (scanning external system next)"
        )

    if dry_run:
        console.print("\n[cyan]🔍 DRY RUN - No changes will be made[/cyan]")

    remote_labels = ["planfile", "managed"] if managed_only else None

    # Execute sync with progress
    try:
        _execute_sync_with_progress(
            backend,
            all_tickets,
            dry_run,
            store,
            integration_name,
            v1_source_file,
            v1_data,
            direction,
            publish_to,
            ticket_ids,
            sprint_ids,
            remote_labels,
            exclude_incident_noise=exclude_incident_noise,
        )
        delivered_comments = []
        if integration_name == "github" and direction in {"to", "both"} and not dry_run:
            delivered_comments = sync_pending_comments(store, backend, ticket_ids)
    except OutboundSyncError as error:
        print_error(str(error))
        raise typer.Exit(1) from error

    if not dry_run:
        console.print(f"\n✅ Sync with {integration_name} completed successfully")
        if integration_name == "github" and direction in {"to", "both"} and delivered_comments:
            console.print(f"   ✓ Delivered {len(delivered_comments)} public comment(s)")
    else:
        console.print(f"\n✅ Dry run completed for {integration_name}")
