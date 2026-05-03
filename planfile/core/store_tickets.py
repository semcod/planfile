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

    def _filter_by_files(self, tickets: list[Ticket], value: Any) -> list[Ticket]:
        patterns = value if isinstance(value, list) else [value]
        return [t for t in tickets if self._matches_files(t, patterns)]

    def _filter_by_labels(self, tickets: list[Ticket], value: Any) -> list[Ticket]:
        labels = value if isinstance(value, list) else [value]
        return [t for t in tickets if any(label in (t.labels or []) for label in labels)]

    def _filter_by_attribute(self, tickets: list[Ticket], key: str, value: Any) -> list[Ticket]:
        return [t for t in tickets if getattr(t, key, None) == value]

    def _apply_filters(self, tickets: list[Ticket], **filters) -> list[Ticket]:
        result = tickets
        for key, value in filters.items():
            if value is None:
                continue
            if key == 'files':
                result = self._filter_by_files(result, value)
            elif key == 'labels':
                result = self._filter_by_labels(result, value)
            else:
                result = self._filter_by_attribute(result, key, value)
        return result

    def _matches_files(self, ticket: Ticket, patterns: list[str]) -> bool:
        """Check if ticket matches any of the file patterns."""
        # Check files list
        if ticket.files:
            for f in ticket.files:
                for pattern in patterns:
                    if fnmatch.fnmatch(f, pattern):
                        return True
        # Check single file field (backward compatibility)
        if ticket.file:
            for pattern in patterns:
                if fnmatch.fnmatch(ticket.file, pattern):
                    return True
        return False

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
