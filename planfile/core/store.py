from __future__ import annotations

from pathlib import Path
from datetime import datetime

import yaml

from .store_files import StoreFileMixin
from .store_tickets import TicketStoreMixin
from .models import Ticket, TicketStatus


class Store(StoreFileMixin, TicketStoreMixin):
    """File-based ticket store using .planfile/ directory."""

    def __init__(self, directory: str | Path):
        self.project_dir = Path(directory).resolve()
        self.base_dir = self.project_dir / ".planfile"
        self._config_path = self.base_dir / "config.yaml"
        self._sprints_dir = self.base_dir / "sprints"

    def is_initialized(self) -> bool:
        return self._config_path.exists()

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
        self._config_path.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")

    def next_id(self) -> str:
        config = self._read_config()
        prefix = config.get("prefix", "PLF")
        nid = config.get("next_id", 1)
        ticket_id = f"{prefix}-{nid:03d}"
        config["next_id"] = nid + 1
        self._write_config(config)
        return ticket_id

    # --- Override base_dir for StoreFileMixin ---
    def _sprint_file(self, sprint: str) -> Path:
        return self._sprints_dir / f"{sprint}.yaml"

    def _all_sprint_files(self) -> list[Path]:
        return sorted(self._sprints_dir.glob("*.yaml"))

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Persist a ticket into the current sprint file."""
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

        sprint_file.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")

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

    def update_ticket(self, ticket_id: str, **updates) -> Ticket | None:
        for sprint_file in self._all_sprint_files():
            data = yaml.safe_load(sprint_file.read_text()) or {}
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                tickets[ticket_id].update(updates)
                tickets[ticket_id]["updated_at"] = datetime.utcnow().isoformat()
                sprint_file.write_text(
                    yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8"
                )
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)
                return self._ticket_from_data(tickets[ticket_id])
        return None


PlanfileStore = Store
