"""Import tickets from generic YAML files."""

import yaml


def import_yaml(path: str, **kwargs) -> list[dict]:
    """Parse a YAML file containing ticket data.

    Accepts either a list of ticket dicts or a single dict with a
    ``tickets`` key.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if isinstance(data, list):
        return [_normalize(item) for item in data]
    if isinstance(data, dict):
        items = data.get("tickets", data.get("issues", [data]))
        if isinstance(items, list):
            return [_normalize(item) for item in items]
        return [_normalize(items)]
    return []


def _normalize(item: dict) -> dict:
    """Ensure minimal ticket fields exist."""
    return {
        "title": item.get("title") or item.get("name") or item.get("summary", "Untitled"),
        "description": item.get("description", ""),
        "priority": item.get("priority", "normal"),
        "labels": item.get("labels", item.get("tags", [])),
        **{k: v for k, v in item.items() if k not in ("title", "name", "summary",
                                                        "description", "priority",
                                                        "labels", "tags")},
    }
