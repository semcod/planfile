"""YAML-based ticket storage in .planfile/ directory."""

import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional
from filelock import FileLock

from planfile.core.models import Ticket, TicketStatus, TicketSource

PLANFILE_DIR = ".planfile"


class PlanfileStore:
    """Read/write tickets and sprints to .planfile/ YAML files."""

    def __init__(self, project_path: str = "."):
        self.root = Path(project_path).resolve()
        self.planfile_dir = self.root / PLANFILE_DIR

    def init(self):
        """Create .planfile/ structure."""
        (self.planfile_dir / "sprints").mkdir(parents=True, exist_ok=True)
        (self.planfile_dir / "sync").mkdir(exist_ok=True)

        # Create default files if missing
        current = self.planfile_dir / "sprints" / "current.yaml"
        if not current.exists():
            self._write_yaml(current, {"sprint": {
                "id": "sprint-001", "name": "Sprint 1",
                "status": "active", "tickets": {}
            }})

        backlog = self.planfile_dir / "sprints" / "backlog.yaml"
        if not backlog.exists():
            self._write_yaml(backlog, {"sprint": {
                "id": "backlog", "name": "Backlog",
                "status": "active", "tickets": {}
            }})

        config = self.planfile_dir / "config.yaml"
        if not config.exists():
            self._write_yaml(config, {
                "project": self.root.name,
                "prefix": "PLF",
                "next_id": 1,
            })

    def is_initialized(self) -> bool:
        return self.planfile_dir.exists()

    # ─── Ticket CRUD ───

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Add ticket to its sprint file."""
        sprint_file = self._sprint_file(ticket.sprint)
        data = self._read_yaml(sprint_file)
        sprint_data = data.get("sprint", data)
        sprint_data.setdefault("tickets", {})[ticket.id] = ticket.model_dump(
            mode="json", exclude_none=True)
        if "sprint" in data:
            data["sprint"] = sprint_data
        self._write_yaml(sprint_file, data)
        return ticket

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Find ticket across all sprint files."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                return Ticket(**tickets[ticket_id])
        return None

    def update_ticket(self, ticket_id: str, **updates) -> Optional[Ticket]:
        """Update ticket fields."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                tickets[ticket_id].update(updates)
                tickets[ticket_id]["updated_at"] = datetime.utcnow().isoformat()
                if "sprint" in data:
                    data["sprint"] = sprint_data
                self._write_yaml(sprint_file, data)
                return Ticket(**tickets[ticket_id])
        return None

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete ticket from its sprint file."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                del tickets[ticket_id]
                if "sprint" in data:
                    data["sprint"] = sprint_data
                self._write_yaml(sprint_file, data)
                return True
        return False

    def list_tickets(self, sprint: str = "current", **filters) -> list[Ticket]:
        """List tickets with filters."""
        if sprint == "all":
            tickets = []
            for sprint_file in self._all_sprint_files():
                data = self._read_yaml(sprint_file)
                sprint_data = data.get("sprint", data)
                tickets.extend(
                    Ticket(**t) for t in sprint_data.get("tickets", {}).values()
                )
        else:
            sprint_file = self._sprint_file(sprint)
            data = self._read_yaml(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = [Ticket(**t) for t in sprint_data.get("tickets", {}).values()]
        return self._apply_filters(tickets, **filters)

    def move_ticket(self, ticket_id: str, to_sprint: str) -> bool:
        """Move ticket between sprints."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return False
        self.delete_ticket(ticket_id)
        ticket.sprint = to_sprint
        self.create_ticket(ticket)
        return True

    # ─── ID generation ───

    def next_id(self) -> str:
        config = self._read_yaml(self.planfile_dir / "config.yaml")
        prefix = config.get("prefix", "PLF")
        num = config.get("next_id", 1)
        config["next_id"] = num + 1
        self._write_yaml(self.planfile_dir / "config.yaml", config)
        return f"{prefix}-{num:03d}"

    # ─── Internal ───

    def _sprint_file(self, sprint: str) -> Path:
        if sprint in ("current", "backlog"):
            return self.planfile_dir / "sprints" / f"{sprint}.yaml"
        return self.planfile_dir / "sprints" / f"{sprint}.yaml"

    def _all_sprint_files(self) -> list[Path]:
        sprints_dir = self.planfile_dir / "sprints"
        if not sprints_dir.exists():
            return []
        return sorted(sprints_dir.glob("*.yaml"))

    def _read_yaml(self, path: Path) -> dict:
        if not path.exists():
            return {}
        lock = FileLock(str(path) + ".lock", timeout=5)
        with lock:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _write_yaml(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(path) + ".lock", timeout=5)
        with lock:
            path.write_text(
                yaml.dump(data, default_flow_style=False,
                          allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    @staticmethod
    def _apply_filters(tickets, status=None, priority=None,
                       source=None, labels=None, **kw):
        if status:
            tickets = [t for t in tickets if t.status == status or t.status.value == status]
        if priority:
            tickets = [t for t in tickets if t.priority == priority]
        if source:
            tickets = [t for t in tickets
                       if t.source and t.source.tool == source]
        if labels:
            label_set = set(labels)
            tickets = [t for t in tickets
                       if label_set.intersection(set(t.labels))]
        return tickets
