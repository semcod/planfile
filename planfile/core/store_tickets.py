from __future__ import annotations

import fnmatch
from typing import Any

from .models import Ticket


class TicketStoreMixin:
    def _ticket_from_data(self, t_data: dict[str, Any]) -> Ticket | None:
        try:
            if 'id' not in t_data:
                return None
            if 'integration' in t_data and isinstance(t_data['integration'], str):
                t_data = dict(t_data)
                t_data['labels'] = [t_data.pop('integration')]
            return Ticket(**t_data)
        except Exception:
            return None

    def _tickets_from_sprint_data(self, sprint_data: dict[str, Any]) -> list[Ticket]:
        tickets_dict = sprint_data.get('tickets') or {}
        tickets: list[Ticket] = []
        for t_data in tickets_dict.values():
            ticket = self._ticket_from_data(t_data)
            if ticket is not None:
                tickets.append(ticket)
        return tickets

    def _apply_filters(self, tickets: list[Ticket], **filters) -> list[Ticket]:
        result = tickets
        for key, value in filters.items():
            if value is None:
                continue
            # Special handling for files filter with glob patterns
            if key == 'files':
                patterns = value if isinstance(value, list) else [value]
                result = [t for t in result if t.files and any(
                    any(fnmatch.fnmatch(f, pattern) for f in t.files)
                    for pattern in patterns
                )]
            elif key == 'labels':
                labels = value if isinstance(value, list) else [value]
                result = [t for t in result if any(label in (t.labels or []) for label in labels)]
            else:
                result = [t for t in result if getattr(t, key, None) == value]
        return result

    def list_tickets(self, sprint: str = 'current', **filters) -> list[Ticket]:
        """List tickets with filters."""
        tickets: list[Ticket] = []
        if sprint == 'all':
            for sprint_file in self._all_sprint_files():
                data = self._read_yaml_cached(sprint_file)
                if not data:
                    continue
                sprint_data = data.get('sprint') or data
                tickets.extend(self._tickets_from_sprint_data(sprint_data))
        else:
            sprint_file = self._sprint_file(sprint)
            data = self._read_yaml_cached(sprint_file)
            if not data:
                return []
            sprint_data = data.get('sprint') or data
            tickets = self._tickets_from_sprint_data(sprint_data)
        return self._apply_filters(tickets, **filters)
