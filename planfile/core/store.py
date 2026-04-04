"""YAML-based ticket storage in .planfile/ directory."""

import copy
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from filelock import FileLock

from planfile.core.models import Ticket

PLANFILE_DIR = ".planfile"

# Constants
CACHE_TIMEOUT_SECONDS = 30
MAX_CACHE_SIZE = 100
INITIAL_SPRINT_ID = 1
INITIAL_TICKET_ID = 1
FILE_LOCK_TIMEOUT = 5


class TicketFilter:
    """Base class for ticket filters."""

    def apply(self, tickets) -> list[Ticket]:
        """Apply filter to tickets."""
        raise NotImplementedError


class StatusFilter(TicketFilter):
    """Filter tickets by status."""

    def __init__(self, status):
        self.status = status

    def apply(self, tickets) -> list[Ticket]:
        return [t for t in tickets
                if t.status == self.status or t.status.value == self.status]


class PriorityFilter(TicketFilter):
    """Filter tickets by priority."""

    def __init__(self, priority):
        self.priority = priority

    def apply(self, tickets) -> list[Ticket]:
        return [t for t in tickets if t.priority == self.priority]


class SourceFilter(TicketFilter):
    """Filter tickets by source tool."""

    def __init__(self, source):
        self.source = source

    def apply(self, tickets) -> list[Ticket]:
        return [t for t in tickets
                if t.source and t.source.tool == self.source]


class LabelsFilter(TicketFilter):
    """Filter tickets by labels."""

    def __init__(self, labels):
        self.label_set = set(labels)

    def apply(self, tickets) -> list[Ticket]:
        return [t for t in tickets
                if self.label_set.intersection(set(t.labels))]


class TicketFilterChain:
    """Chain of ticket filters."""

    def __init__(self):
        self.filters = []

    def add_filter(self, filter_obj):
        """Add a filter to the chain."""
        self.filters.append(filter_obj)

    def apply(self, tickets) -> list[Ticket]:
        """Apply all filters in sequence."""
        for filter_obj in self.filters:
            tickets = filter_obj.apply(tickets)
        return tickets


class PlanfileStore:
    """Read/write tickets and sprints to .planfile/ YAML files."""

    def __init__(self, project_path: str = "."):
        self.root = Path(project_path).resolve()
        self.planfile_dir = self.root / PLANFILE_DIR
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._cache_timeout = CACHE_TIMEOUT_SECONDS  # seconds
        self._max_cache_size = MAX_CACHE_SIZE  # Maximum number of files to cache

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
                "next_id": INITIAL_TICKET_ID,
            })

    def is_initialized(self) -> bool:
        return self.planfile_dir.exists()

    def _get_file_mtime(self, file_path: str) -> float:
        """Get file modification time for cache invalidation."""
        path = Path(file_path)
        return path.stat().st_mtime if path.exists() else 0

    def _read_yaml_cached(self, file_path: Path) -> dict[str, Any]:
        """Read YAML file with caching."""
        path_str = str(file_path)
        current_mtime = self._get_file_mtime(path_str)

        with self._cache_lock:
            if path_str in self._cache:
                cached_data, cached_mtime = self._cache[path_str]
                if cached_mtime == current_mtime:
                    return copy.deepcopy(cached_data)

        # File changed or not in cache, read it
        data = self._read_yaml(file_path)

        with self._cache_lock:
            # Enforce cache size limit
            if len(self._cache) >= self._max_cache_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[path_str] = (data, current_mtime)

        return copy.deepcopy(data)

    def _invalidate_cache(self, file_path: Path = None):
        """Invalidate cache for a file or all files."""
        with self._cache_lock:
            if file_path:
                self._cache.pop(str(file_path), None)
            else:
                self._cache.clear()

    # ─── Ticket CRUD ───

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Add ticket to its sprint file."""
        sprint_file = self._sprint_file(ticket.sprint)
        data = self._read_yaml_cached(sprint_file)
        sprint_data = data.get("sprint", data)
        sprint_data.setdefault("tickets", {})[ticket.id] = ticket.model_dump(
            mode="json", exclude_none=True)
        if "sprint" in data:
            data["sprint"] = sprint_data
        self._write_yaml(sprint_file, data)
        self._invalidate_cache(sprint_file)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        """Find ticket across all sprint files."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml_cached(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                return Ticket(**tickets[ticket_id])
        return None

    def update_ticket(self, ticket_id: str, **updates) -> Ticket | None:
        """Update ticket fields."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml_cached(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                # Convert updates to JSON-compatible types (e.g. Enums to strings)
                json_updates = {}
                for k, v in updates.items():
                    if hasattr(v, 'value'): # Handle Enums
                        json_updates[k] = v.value
                    elif isinstance(v, datetime):
                        json_updates[k] = v.isoformat()
                    else:
                        json_updates[k] = v
                
                tickets[ticket_id].update(json_updates)
                tickets[ticket_id]["updated_at"] = datetime.utcnow().isoformat()
                if "sprint" in data:
                    data["sprint"] = sprint_data
                self._write_yaml(sprint_file, data)
                self._invalidate_cache(sprint_file)
                return Ticket(**tickets[ticket_id])
        return None

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete ticket from its sprint file."""
        for sprint_file in self._all_sprint_files():
            data = self._read_yaml_cached(sprint_file)
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                del tickets[ticket_id]
                if "sprint" in data:
                    data["sprint"] = sprint_data
                self._write_yaml(sprint_file, data)
                self._invalidate_cache(sprint_file)
                return True
        return False

    def list_tickets(self, sprint: str = "current", **filters) -> list[Ticket]:
        """List tickets with filters."""
        if sprint == "all":
            tickets = []
            for sprint_file in self._all_sprint_files():
                data = self._read_yaml_cached(sprint_file)
                if not data: continue
                sprint_data = data.get("sprint") or data
                tickets_dict = sprint_data.get("tickets") or {}
                for t_data in tickets_dict.values():
                    try:
                        # Handle legacy data: ensure 'id' exists and fix 'integration' -> 'labels'
                        if "id" not in t_data:
                            continue  # Skip invalid tickets without ID
                        if "integration" in t_data and isinstance(t_data["integration"], str):
                            # Convert old 'integration' field to 'labels'
                            t_data["labels"] = [t_data.pop("integration")]
                        tickets.append(Ticket(**t_data))
                    except Exception:
                        # Skip tickets that fail validation
                        continue
        else:
            sprint_file = self._sprint_file(sprint)
            data = self._read_yaml_cached(sprint_file)
            if not data: return []
            sprint_data = data.get("sprint") or data
            tickets_dict = sprint_data.get("tickets") or {}
            tickets = []
            for t_data in tickets_dict.values():
                try:
                    if "id" not in t_data:
                        continue
                    if "integration" in t_data and isinstance(t_data["integration"], str):
                        t_data["labels"] = [t_data.pop("integration")]
                    tickets.append(Ticket(**t_data))
                except Exception:
                    continue
        return self._apply_filters(tickets, **filters)

    def _apply_filters(self, tickets, **filters):
        """Apply filters to a list of tickets."""
        filtered = tickets

        if "status" in filters:
            status = filters["status"]
            filtered = [t for t in filtered if t.status == status]

        if "labels" in filters:
            labels = filters["labels"]
            filtered = [t for t in filtered if any(l in t.labels for l in labels)]

        if "assignee" in filters:
            assignee = filters["assignee"]
            filtered = [t for t in filtered if t.assignee == assignee]

        if "source" in filters:
            source = filters["source"]
            filtered = [t for t in filtered if t.source == source]

        if "priority" in filters:
            priority = filters["priority"]
            filtered = [t for t in filtered if t.priority == priority]

        if "type" in filters:
            ticket_type = filters["type"]
            filtered = [t for t in filtered if t.type == ticket_type]

        return filtered

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
        num = config.get("next_id", INITIAL_TICKET_ID)
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
        lock = FileLock(str(path) + ".lock", timeout=FILE_LOCK_TIMEOUT)
        with lock:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _write_yaml(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(path) + ".lock", timeout=FILE_LOCK_TIMEOUT)
        with lock:
            try:
                # Use safe_dump to prevent circular reference issues
                content = yaml.safe_dump(data, default_flow_style=False,
                                         allow_unicode=True, sort_keys=False)
            except Exception as e:
                # Fallback to regular dump if safe_dump fails
                print(f"Warning: safe_dump failed, using regular dump: {e}")
                content = yaml.dump(data, default_flow_style=False,
                                   allow_unicode=True, sort_keys=False)
            path.write_text(content, encoding="utf-8")

    def load_sprint(self, sprint: str = "current") -> dict:
        """Load sprint data as dictionary."""
        sprint_file = self._sprint_file(sprint)
        data = self._read_yaml(sprint_file)
        # Handle both old format {"sprint": {...}} and new format
        sprint_data = data.get("sprint", data)
        if not sprint_data:
            return {"tickets": {}}
        return sprint_data

    def save_sprint(self, sprint: str, data: dict):
        """Save sprint data to file."""
        sprint_file = self._sprint_file(sprint)
        # Wrap in old format for compatibility
        if "sprint" not in data:
            output = {"sprint": data}
        else:
            output = data
        self._write_yaml(sprint_file, output)

    def load_backlog(self) -> dict:
        """Load backlog as dictionary."""
        return self.load_sprint("backlog")

    def save_backlog(self, data: dict):
        """Save backlog data."""
        self.save_sprint("backlog", data)

    # ─── Analytics & Export ───

    def stats(self) -> dict:
        """
        Get ticket statistics.
        
        Returns:
            {
                "total": int,
                "by_status": {"open": int, "done": int, ...},
                "by_priority": {"high": int, "normal": int, ...},
                "by_label": {"bug": int, "feature": int, ...},
                "by_sprint": {"current": int, "backlog": int, ...}
            }
        """
        tickets = self.list_tickets(sprint="all")
        from collections import Counter
        
        def status_value(s):
            return s.value if hasattr(s, 'value') else str(s)
        
        return {
            "total": len(tickets),
            "by_status": dict(Counter(status_value(t.status) for t in tickets)),
            "by_priority": dict(Counter(t.priority for t in tickets)),
            "by_label": dict(Counter(
                label for t in tickets for label in (t.labels or [])
            )),
            "by_sprint": dict(Counter(t.sprint for t in tickets))
        }

    def export(self, format: str = "json", sprint: str = None, **filters) -> str:
        """
        Export tickets to various formats.
        
        Args:
            format: "json", "csv", or "markdown"
            sprint: Filter by sprint (None = all)
            **filters: Additional filters for list_tickets
        
        Returns:
            Exported data as string
        """
        tickets = self.list_tickets(sprint=sprint or "all", **filters)
        
        if format == "json":
            import json
            return json.dumps([t.model_dump(mode="json") for t in tickets], indent=2)
        
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "title", "status", "priority", "sprint", "labels", "description"])
            for t in tickets:
                writer.writerow([
                    t.id,
                    t.title,
                    t.status.value if hasattr(t.status, 'value') else str(t.status),
                    t.priority,
                    t.sprint,
                    "|".join(t.labels or []),
                    t.description[:100] if t.description else ""
                ])
            return output.getvalue()
        
        elif format == "markdown":
            lines = ["# Tickets\n"]
            for t in tickets:
                lines.append(f"\n## {t.id} [{t.priority}]")
                lines.append(f"**{t.title}**")
                lines.append(f"- Status: {t.status}")
                lines.append(f"- Sprint: {t.sprint}")
                if t.labels:
                    lines.append(f"- Labels: {', '.join(t.labels)}")
                if t.description:
                    lines.append(f"\n{t.description[:200]}...")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unknown format: {format}. Use 'json', 'csv', or 'markdown'")

    def search(self, query: str, fields: list = None) -> list[Ticket]:
        """
        Full-text search in tickets.
        
        Args:
            query: Search string (case-insensitive)
            fields: Fields to search (default: ["title", "description"])
        
        Returns:
            List of matching tickets
        """
        fields = fields or ["title", "description"]
        tickets = self.list_tickets(sprint="all")
        query_lower = query.lower()
        
        results = []
        for t in tickets:
            for field in fields:
                value = getattr(t, field, "")
                if value and query_lower in str(value).lower():
                    results.append(t)
                    break
        return results
