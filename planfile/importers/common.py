"""Shared helpers for ticket importers."""

from collections.abc import Callable
from typing import Any


def normalize_ticket_dict(item: dict) -> dict:
    """Ensure minimal ticket fields exist."""
    return {
        "title": item.get("title") or item.get("name") or item.get("summary", "Untitled"),
        "description": item.get("description", ""),
        "priority": item.get("priority", "normal"),
        "labels": item.get("labels", item.get("tags", [])),
        **{
            k: v for k, v in item.items()
            if k not in ("title", "name", "summary", "description", "priority", "labels", "tags")
        },
    }


def load_structured_tickets(path: str, loader: Callable[[Any], Any]) -> list[dict]:
    """Load tickets from JSON/YAML-like structured data."""
    with open(path, encoding="utf-8") as f:
        data = loader(f)

    if isinstance(data, list):
        return [normalize_ticket_dict(item) for item in data]

    if isinstance(data, dict):
        items = data.get("tickets", data.get("issues", [data]))
        if isinstance(items, list):
            return [normalize_ticket_dict(item) for item in items]
        return [normalize_ticket_dict(items)]

    return []
