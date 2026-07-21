from __future__ import annotations

import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel

from .models import Ticket
from .store_files import StoreFileMixin
from .store_tickets import TicketStoreMixin


class Store(StoreFileMixin, TicketStoreMixin):
    """File-based ticket store using .planfile/ directory."""

    DEFAULT_ARCHIVE_CONFIG = {
        "enabled": True,
        "max_current_tickets": 500,
        "max_current_bytes": 1_000_000,
        "retain_terminal_tickets": 100,
        "terminal_statuses": ["done", "canceled", "failed"],
    }
    SPRINT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

    def __init__(self, directory: str | Path):
        self.project_dir = Path(directory).resolve()
        self.base_dir = self.project_dir / ".planfile"
        self._config_path = self.base_dir / "config.yaml"
        self._sprints_dir = self.base_dir / "sprints"
        self._lock_path = self.base_dir / ".store.lock"

    @contextmanager
    def mutation_lock(self):
        """Serialize multi-process YAML mutations."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_path.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            lock_file.close()

    def _write_yaml_atomic(self, path: Path, data: dict, *, allow_unicode: bool = False) -> None:
        from planfile.core.fastio import dump_yaml, write_mirror

        path.parent.mkdir(parents=True, exist_ok=True)
        content = dump_yaml(data, allow_unicode=allow_unicode)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            # Stat immediately after our own replace, under mutation_lock() (no other
            # writer can be interleaved here) — pass it through instead of letting
            # write_mirror() re-stat independently later (see its docstring).
            mtime_ns = path.stat().st_mtime_ns
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        write_mirror(path, data, mtime_ns=mtime_ns)

    def is_initialized(self) -> bool:
        return self._config_path.exists()

    def load_sprint(self, sprint: str) -> dict:
        """Load sprint data from YAML."""
        path = self._sprint_file(sprint)
        data = self._read_yaml_cached(path) or {}
        return data.get("sprint") or data

    def load_backlog(self) -> dict:
        """Load backlog data from YAML."""
        path = self._sprint_file("backlog")
        data = self._read_yaml_cached(path) or {}
        return data.get("sprint") or data

    def save_sprint(self, sprint: str, data: dict) -> None:
        """Merge sprint data back to YAML without dropping concurrent mutations.

        Callers such as external-system sync intentionally hold an in-memory
        snapshot while doing network work.  Replacing the whole sprint with
        that snapshot can erase tickets created after ``load_sprint()``.  The
        mutation lock serializes writers, but it cannot make a stale snapshot
        current, so merge it with a fresh read taken inside the lock.

        Tickets absent from ``data`` are preserved.  Explicit deletion must go
        through ``delete_ticket(s)``.  When the same ticket changed on both
        sides, the record with the newer ``updated_at`` wins; a stale bulk
        save therefore fails closed instead of reverting a newer lifecycle
        transition.
        """
        path = self._sprint_file(sprint)
        with self.mutation_lock():
            from planfile.core.fastio import read_yaml_fast

            current = read_yaml_fast(path) or {}
            merged = self._merge_sprint_snapshots(current, data)
            self._write_yaml_atomic(path, merged, allow_unicode=True)
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(path), None)
        if sprint == "current":
            self.archive_completed()

    @staticmethod
    def _ticket_timestamp(ticket: dict) -> datetime:
        for key in ("updated_at", "created_at"):
            value = ticket.get(key) if isinstance(ticket, dict) else None
            if isinstance(value, datetime):
                parsed = value
            elif isinstance(value, str) and value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return datetime.min.replace(tzinfo=UTC)

    @classmethod
    def _merge_sprint_snapshots(cls, current: dict, incoming: dict) -> dict:
        """Return a wrapped sprint snapshot that preserves newer disk state."""
        current_root = current.get("sprint", current) if isinstance(current, dict) else {}
        incoming_root = incoming.get("sprint", incoming) if isinstance(incoming, dict) else {}
        current_root = current_root if isinstance(current_root, dict) else {}
        incoming_root = incoming_root if isinstance(incoming_root, dict) else {}

        merged_root = {**current_root, **incoming_root}
        current_tickets = current_root.get("tickets") or {}
        incoming_tickets = incoming_root.get("tickets") or {}
        current_tickets = current_tickets if isinstance(current_tickets, dict) else {}
        incoming_tickets = incoming_tickets if isinstance(incoming_tickets, dict) else {}

        merged_tickets = dict(current_tickets)
        for ticket_id, incoming_ticket in incoming_tickets.items():
            current_ticket = current_tickets.get(ticket_id)
            if (
                isinstance(current_ticket, dict)
                and isinstance(incoming_ticket, dict)
                and cls._ticket_timestamp(current_ticket) > cls._ticket_timestamp(incoming_ticket)
            ):
                continue
            merged_tickets[ticket_id] = incoming_ticket
        merged_root["tickets"] = merged_tickets
        return {"sprint": merged_root}

    def save_backlog(self, data: dict) -> None:
        """Merge backlog data with the same concurrency guarantees as a sprint."""
        self.save_sprint("backlog", data)

    def init(self) -> None:
        """Create the .planfile/ structure from scratch."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sprints_dir.mkdir(exist_ok=True)
        if not self._config_path.exists():
            self._config_path.write_text(
                yaml.dump(
                    {
                        "project": self.project_dir.name,
                        "prefix": "PLF",
                        "next_id": 1,
                        "archive": dict(self.DEFAULT_ARCHIVE_CONFIG),
                    }
                ),
                encoding="utf-8",
            )
        current = self._sprints_dir / "current.yaml"
        if not current.exists():
            current.write_text(
                yaml.dump(
                    {
                        "sprint": {
                            "id": "sprint-001",
                            "name": "Sprint 1",
                            "status": "active",
                            "tickets": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
        backlog = self._sprints_dir / "backlog.yaml"
        if not backlog.exists():
            backlog.write_text(
                yaml.dump(
                    {
                        "sprint": {
                            "id": "backlog",
                            "name": "Backlog",
                            "status": "active",
                            "tickets": {},
                        }
                    }
                ),
                encoding="utf-8",
            )

    def _read_config(self) -> dict:
        if not self._config_path.exists():
            return {"project": "unknown", "prefix": "PLF", "next_id": 1}
        return yaml.safe_load(self._config_path.read_text()) or {}

    def _write_config(self, config: dict) -> None:
        self._write_yaml_atomic(self._config_path, config)

    def _next_id_unlocked(self) -> str:
        config = self._read_config()
        prefix = config.get("prefix", "PLF")
        nid = config.get("next_id", 1)
        ticket_id = f"{prefix}-{nid:03d}"
        config["next_id"] = nid + 1
        self._write_config(config)
        return ticket_id

    def _archive_config(self) -> dict:
        """Return validated automatic-archive settings with safe defaults."""
        configured = self._read_config().get("archive") or {}
        if not isinstance(configured, dict):
            configured = {}
        result = dict(self.DEFAULT_ARCHIVE_CONFIG)
        result.update(configured)
        for key in ("max_current_tickets", "max_current_bytes", "retain_terminal_tickets"):
            try:
                result[key] = max(0, int(result[key]))
            except (TypeError, ValueError):
                result[key] = self.DEFAULT_ARCHIVE_CONFIG[key]
        statuses = result.get("terminal_statuses")
        if not isinstance(statuses, list) or not statuses:
            statuses = self.DEFAULT_ARCHIVE_CONFIG["terminal_statuses"]
        result["terminal_statuses"] = {str(status).lower() for status in statuses}
        result["enabled"] = bool(result.get("enabled", True))
        return result

    @staticmethod
    def _ticket_archive_timestamp(ticket: dict) -> datetime:
        """Choose the best stable timestamp for ordering and archive naming."""
        execution = ticket.get("execution")
        values = []
        if isinstance(execution, dict):
            values.append(execution.get("finished_at"))
        values.extend((ticket.get("updated_at"), ticket.get("created_at")))
        for value in values:
            if isinstance(value, datetime):
                parsed = value
            elif isinstance(value, str) and value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return datetime.now(UTC)

    def archive_completed(self) -> dict:
        """Archive old terminal tickets when ``current.yaml`` exceeds its limits.

        Archive files are partitioned by month. The operation is serialized with all
        other store mutations and is idempotent after an interrupted multi-file write.
        """
        with self.mutation_lock():
            return self._archive_completed_unlocked()

    def _archive_completed_unlocked(self) -> dict:
        from planfile.core.fastio import read_yaml_fast

        config = self._archive_config()
        current_file = self._sprint_file("current")
        report = {
            "triggered": False,
            "archived": 0,
            "remaining": 0,
            "archive_files": [],
        }
        if not config["enabled"] or not current_file.exists():
            return report

        data = read_yaml_fast(current_file) or {}
        sprint_data = data.get("sprint", data)
        tickets = sprint_data.get("tickets") or {}
        if not isinstance(tickets, dict):
            return report
        report["remaining"] = len(tickets)

        over_count = (
            config["max_current_tickets"] > 0 and len(tickets) > config["max_current_tickets"]
        )
        try:
            current_size = current_file.stat().st_size
        except OSError:
            current_size = 0
        over_size = config["max_current_bytes"] > 0 and current_size > config["max_current_bytes"]
        if not (over_count or over_size):
            return report
        report["triggered"] = True

        terminal = [
            (self._ticket_archive_timestamp(ticket), ticket_id, ticket)
            for ticket_id, ticket in tickets.items()
            if isinstance(ticket, dict)
            and str(ticket.get("status", "")).lower() in config["terminal_statuses"]
        ]
        terminal.sort(key=lambda item: (item[0], item[1]))
        move_count = max(0, len(terminal) - config["retain_terminal_tickets"])
        if move_count == 0:
            return report

        archive_data: dict[Path, dict] = {}
        moved_ids: list[str] = []
        for timestamp, ticket_id, ticket in terminal[:move_count]:
            archive_name = f"archive-{timestamp:%Y-%m}"
            archive_file = self._sprint_file(archive_name)
            archive = archive_data.get(archive_file)
            if archive is None:
                archive = read_yaml_fast(archive_file) if archive_file.exists() else None
                archive = archive or {
                    "sprint": {
                        "id": archive_name,
                        "name": f"Archive {timestamp:%Y-%m}",
                        "status": "archived",
                        "tickets": {},
                    }
                }
                archive_data[archive_file] = archive
            archive_sprint = archive.get("sprint", archive)
            archive_tickets = archive_sprint.setdefault("tickets", {})
            archived_ticket = dict(ticket)
            archived_ticket["sprint"] = archive_name
            # Overwrite makes a retry safe if a process stopped after writing the
            # archive but before removing the same ticket from current.yaml.
            archive_tickets[ticket_id] = archived_ticket
            moved_ids.append(ticket_id)

        # Write destinations first: interruption can temporarily duplicate data,
        # but can never lose a ticket. A later run removes any duplicates safely.
        for archive_file, archive in archive_data.items():
            self._write_yaml_atomic(archive_file, archive, allow_unicode=True)
            if hasattr(self, "_yaml_cache"):
                self._yaml_cache.pop(str(archive_file), None)
        for ticket_id in moved_ids:
            tickets.pop(ticket_id, None)
        self._write_yaml_atomic(current_file, data, allow_unicode=True)
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(current_file), None)

        report["archived"] = len(moved_ids)
        report["remaining"] = len(tickets)
        report["archive_files"] = [path.stem for path in sorted(archive_data)]
        return report

    def next_id(self) -> str:
        with self.mutation_lock():
            return self._next_id_unlocked()

    # --- Override base_dir for StoreFileMixin ---
    def _sprint_file(self, sprint: str) -> Path:
        if not self.SPRINT_ID_PATTERN.fullmatch(str(sprint)):
            raise ValueError(f"invalid_sprint_id:{sprint}")
        return self._sprints_dir / f"{sprint}.yaml"

    def _all_sprint_files(self) -> list[Path]:
        return sorted(self._sprints_dir.glob("*.yaml"))

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Persist a ticket into the current sprint file."""
        with self.mutation_lock():
            return self._create_ticket_unlocked(ticket)

    def _create_ticket_unlocked(self, ticket: Ticket) -> Ticket:
        """Persist a ticket while the caller holds ``mutation_lock``."""
        sprint = ticket.sprint or "current"
        sprint_file = self._sprint_file(sprint)

        if sprint_file.exists():
            from planfile.core.fastio import read_yaml_fast

            data = read_yaml_fast(sprint_file) or {}
        else:
            data = {
                "sprint": {"id": sprint, "name": sprint.title(), "status": "active", "tickets": {}}
            }

        sprint_data = data.get("sprint", data)
        if "tickets" not in sprint_data:
            sprint_data["tickets"] = {}

        sprint_data["tickets"][ticket.id] = ticket.model_dump(mode="json", exclude_none=True)
        data["sprint"] = sprint_data

        self._write_yaml_atomic(sprint_file, data, allow_unicode=True)

        # Invalidate yaml cache
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(sprint_file), None)

        if sprint == "current":
            self._archive_completed_unlocked()

        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml_cached(sprint_file)
            if not data:
                continue
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                return self._ticket_from_data(tickets[ticket_id])
        return None

    def _serialize_update_value(self, value):
        """Convert rich Python/Pydantic values into YAML-safe primitives."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [self._serialize_update_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_update_value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _execution_state(ticket_data: dict) -> str | None:
        execution = ticket_data.get("execution")
        if not isinstance(execution, dict):
            return None
        return execution.get("state")

    @classmethod
    def _build_history_entry(
        cls,
        previous: dict,
        current: dict,
        changed_keys: list[str],
        reason: str | None = None,
        actor: str | None = None,
    ) -> dict:
        previous_status = previous.get("status")
        current_status = current.get("status")
        previous_state = cls._execution_state(previous)
        current_state = cls._execution_state(current)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": "update",
            "source": "planfile.store",
            "changes": changed_keys,
        }
        if previous_status != current_status:
            entry["action"] = "status_change"
            entry["status"] = current_status
            entry["previous_status"] = previous_status
        if previous_state != current_state:
            entry["execution_state"] = current_state
            entry["previous_execution_state"] = previous_state
        if reason:
            entry["reason"] = reason
        if actor:
            entry["actor"] = actor
            entry["by"] = actor  # alias for "by whom"
        return entry

    def update_ticket(
        self, ticket_id: str, reason: str | None = None, actor: str | None = None, **updates
    ) -> Ticket | None:
        """Update a ticket. If status (or execution state) changes, a structured history entry
        is appended automatically, including optional `reason` (why) and `actor` (who / by whom).
        Use reason/actor (or _reason/_actor in **updates) for rich audit on status transitions.
        """
        with self.mutation_lock():
            return self._update_ticket_unlocked(ticket_id, reason=reason, actor=actor, **updates)

    def _update_ticket_unlocked(
        self, ticket_id: str, reason: str | None = None, actor: str | None = None, **updates
    ) -> Ticket | None:
        from planfile.core.fastio import read_yaml_fast

        for sprint_file in self._all_sprint_files():
            data = read_yaml_fast(sprint_file) or {}
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                previous = dict(tickets[ticket_id])
                # Extract history metadata (reason=why the change, actor/by=who performed it)
                # Support both named params (from high-level methods) and _-prefixed or bare in updates
                history_reason = (
                    reason or updates.pop("reason", None) or updates.pop("_reason", None)
                )
                history_actor = actor or updates.pop("actor", None) or updates.pop("_actor", None)

                serialized_updates = {
                    key: self._serialize_update_value(value) for key, value in updates.items()
                }
                terminal_status = serialized_updates.get("status")
                if terminal_status in {"done", "canceled", "blocked", "failed"}:
                    execution_update = serialized_updates.get("execution")
                    if not isinstance(execution_update, dict):
                        execution_update = dict(previous.get("execution") or {})
                    else:
                        execution_update = dict(execution_update)
                    execution_update["state"] = terminal_status
                    execution_update["assigned_to"] = None
                    execution_update["lease_expires_at"] = None
                    execution_update["finished_at"] = datetime.now(UTC).isoformat()
                    serialized_updates["execution"] = execution_update
                tickets[ticket_id].update(serialized_updates)
                tickets[ticket_id]["updated_at"] = datetime.now(UTC).isoformat()
                changed_keys = sorted(
                    key
                    for key, value in serialized_updates.items()
                    if key != "history" and previous.get(key) != value
                )
                if changed_keys and "history" not in serialized_updates:
                    history = list(tickets[ticket_id].get("history") or [])
                    entry = self._build_history_entry(
                        previous,
                        tickets[ticket_id],
                        changed_keys,
                        reason=history_reason,
                        actor=history_actor,
                    )
                    history.append(entry)
                    tickets[ticket_id]["history"] = history[-200:]
                self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)
                if sprint_file == self._sprint_file("current"):
                    self._archive_completed_unlocked()
                return self._ticket_from_data(tickets[ticket_id])
        return None

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True if deleted, False if not found."""
        from planfile.core.fastio import read_yaml_fast

        with self.mutation_lock():
            for sprint_file in self._all_sprint_files():
                data = read_yaml_fast(sprint_file) or {}
                sprint_data = data.get("sprint", data)
                tickets = sprint_data.get("tickets", {})
                if ticket_id in tickets:
                    del tickets[ticket_id]
                    self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                    if hasattr(self, "_yaml_cache"):
                        self._yaml_cache.pop(str(sprint_file), None)
                    return True
        return False

    def move_ticket(self, ticket_id: str, to_sprint: str) -> bool:
        """Move a ticket under one lock, rolling back if source removal fails."""
        from planfile.core.fastio import read_yaml_fast

        destination_file = self._sprint_file(to_sprint)
        with self.mutation_lock():
            for source_file in self._all_sprint_files():
                source_data = read_yaml_fast(source_file) or {}
                source_root = source_data.get("sprint", source_data)
                source_tickets = source_root.get("tickets", {})
                if ticket_id not in source_tickets:
                    continue
                if source_file == destination_file:
                    return True

                previous_ticket = dict(source_tickets[ticket_id])
                moved_ticket = dict(previous_ticket)
                moved_ticket["sprint"] = to_sprint
                moved_ticket["updated_at"] = datetime.now(UTC).isoformat()
                history = list(moved_ticket.get("history") or [])
                history.append(
                    self._build_history_entry(
                        previous_ticket,
                        moved_ticket,
                        ["sprint"],
                        reason="move_ticket",
                    )
                )
                moved_ticket["history"] = history[-200:]

                destination_existed = destination_file.exists()
                destination_before = read_yaml_fast(destination_file) if destination_existed else None
                destination_data = destination_before or {
                    "sprint": {
                        "id": to_sprint,
                        "name": to_sprint.replace("-", " ").title(),
                        "status": "active",
                        "tickets": {},
                    }
                }
                destination_root = destination_data.get("sprint", destination_data)
                destination_tickets = destination_root.setdefault("tickets", {})
                if ticket_id in destination_tickets:
                    raise ValueError(f"ticket_exists_in_target_sprint:{ticket_id}:{to_sprint}")
                destination_tickets[ticket_id] = moved_ticket
                destination_data["sprint"] = destination_root

                self._write_yaml_atomic(destination_file, destination_data, allow_unicode=True)
                try:
                    del source_tickets[ticket_id]
                    self._write_yaml_atomic(source_file, source_data, allow_unicode=True)
                except Exception:
                    if destination_existed and destination_before is not None:
                        self._write_yaml_atomic(destination_file, destination_before, allow_unicode=True)
                    else:
                        destination_file.unlink(missing_ok=True)
                    raise
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(source_file), None)
                    self._yaml_cache.pop(str(destination_file), None)
                return True
        return False

    def delete_tickets_bulk(self, ticket_ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple tickets by ID. Returns (deleted_ids, not_found_ids)."""
        deleted = []
        not_found = []

        with self.mutation_lock():
            # Load all sprint files into memory
            from planfile.core.fastio import read_yaml_fast

            sprint_contents = {}
            for sprint_file in self._all_sprint_files():
                sprint_contents[sprint_file] = read_yaml_fast(sprint_file) or {}

            modified_files = set()

            for ticket_id in ticket_ids:
                found = False
                for sprint_file, data in sprint_contents.items():
                    sprint_data = data.get("sprint", data)
                    tickets = sprint_data.get("tickets", {})
                    if isinstance(tickets, dict) and ticket_id in tickets:
                        del tickets[ticket_id]
                        modified_files.add(sprint_file)
                        deleted.append(ticket_id)
                        found = True
                        break
                if not found:
                    not_found.append(ticket_id)

            # Write only the modified sprint files back to disk, exactly once!
            for sprint_file in modified_files:
                data = sprint_contents[sprint_file]
                self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)

        return deleted, not_found


PlanfileStore = Store
