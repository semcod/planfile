"""Import tickets from generic JSON files."""

import json

from planfile.importers.common import load_structured_tickets


def import_json(path: str, **kwargs) -> list[dict]:
    """Parse a JSON file containing ticket data.

    Accepts either a list of ticket dicts or a single dict with a
    ``tickets`` key.
    """
    return load_structured_tickets(path, json.load)
