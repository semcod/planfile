from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CDumper as Dumper
except ImportError:
    from yaml import SafeLoader, Dumper
from pydantic import BaseModel

from .models import Ticket
from .store_files import StoreFileMixin
from .store_tickets import TicketStoreMixin


class Store(StoreFileMixin, TicketStoreMixin):
    """File-based ticket store using .planfile/ directory."""

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
        path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.dump(data, default_flow_style=False, allow_unicode=allow_unicode, Dumper=Dumper)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

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
        """Save sprint data back to YAML."""
        path = self._sprint_file(sprint)
        # Ensure format matches expected nesting
        wrapped = {"sprint": data} if "sprint" not in data else data
        with self.mutation_lock():
            self._write_yaml_atomic(path, wrapped, allow_unicode=True)
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(path), None)

    def init(self) -> None:
        """Create the .planfile/ structure from scratch."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sprints_dir.mkdir(exist_ok=True)
        if not self._config_path.exists():
            self._config_path.write_text(
                yaml.dump({"project": self.project_dir.name, "prefix": "PLF", "next_id": 1}),
                encoding="utf-8",
            )
        current = self._sprints_dir / "current.yaml"
        if not current.exists():
            current.write_text(
                yaml.dump({"sprint": {"id": "sprint-001", "name": "Sprint 1", "status": "active", "tickets": {}}}),
                encoding="utf-8",
            )
        backlog = self._sprints_dir / "backlog.yaml"
        if not backlog.exists():
            backlog.write_text(
                yaml.dump({"sprint": {"id": "backlog", "name": "Backlog", "status": "active", "tickets": {}}}),
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

    def next_id(self) -> str:
        with self.mutation_lock():
            return self._next_id_unlocked()

    # --- Override base_dir for StoreFileMixin ---
    def _sprint_file(self, sprint: str) -> Path:
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
            data = yaml.safe_load(sprint_file.read_text()) or {}
        else:
            data = {"sprint": {"id": sprint, "name": sprint.title(), "status": "active", "tickets": {}}}

        sprint_data = data.get("sprint", data)
        if "tickets" not in sprint_data:
            sprint_data["tickets"] = {}

        sprint_data["tickets"][ticket.id] = ticket.model_dump(mode="json", exclude_none=True)
        data["sprint"] = sprint_data

        self._write_yaml_atomic(sprint_file, data, allow_unicode=True)

        # Invalidate yaml cache
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(sprint_file), None)

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
            entry["status"] = current_status
            entry["previous_status"] = previous_status
        if previous_state != current_state:
            entry["execution_state"] = current_state
            entry["previous_execution_state"] = previous_state
        return entry

    def update_ticket(self, ticket_id: str, **updates) -> Ticket | None:
        for sprint_file in self._all_sprint_files():
            data = yaml.load(sprint_file.read_text(), Loader=SafeLoader) or {}
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                previous = dict(tickets[ticket_id])
                serialized_updates = {
                    key: self._serialize_update_value(value)
                    for key, value in updates.items()
                }
                tickets[ticket_id].update(serialized_updates)
                tickets[ticket_id]["updated_at"] = datetime.now(UTC).isoformat()
                changed_keys = sorted(
                    key
                    for key, value in serialized_updates.items()
                    if key != "history" and previous.get(key) != value
                )
                if changed_keys and "history" not in serialized_updates:
                    history = list(tickets[ticket_id].get("history") or [])
                    history.append(self._build_history_entry(previous, tickets[ticket_id], changed_keys))
                    tickets[ticket_id]["history"] = history[-200:]
                sprint_file.write_text(
                    yaml.dump(data, default_flow_style=False, allow_unicode=True, Dumper=Dumper), encoding="utf-8"
                )
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)
                return self._ticket_from_data(tickets[ticket_id])
        return None

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True if deleted, False if not found."""
        for sprint_file in self._all_sprint_files():
            data = yaml.load(sprint_file.read_text(), Loader=SafeLoader) or {}
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                del tickets[ticket_id]
                sprint_file.write_text(
                    yaml.dump(data, default_flow_style=False, allow_unicode=True, Dumper=Dumper), encoding="utf-8"
                )
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)
                return True
        return False

    def delete_tickets_bulk(self, ticket_ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple tickets by ID. Returns (deleted_ids, not_found_ids)."""
        deleted = []
        not_found = []

        # Load all sprint files into memory
        sprint_contents = {}
        for sprint_file in self._all_sprint_files():
            try:
                data = yaml.load(sprint_file.read_text(encoding="utf-8"), Loader=SafeLoader) or {}
            except Exception:
                data = {}
            sprint_contents[sprint_file] = data

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
            sprint_file.write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True, Dumper=Dumper), encoding="utf-8"
            )
            if hasattr(self, "_yaml_cache"):
                self._yaml_cache.pop(str(sprint_file), None)

        return deleted, not_found


PlanfileStore = Store
