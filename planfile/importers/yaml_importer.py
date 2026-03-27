"""Import tickets from generic YAML files."""

import yaml

from planfile.importers.common import load_structured_tickets


def import_yaml(path: str, **kwargs) -> list[dict]:
    """Parse a YAML file containing ticket data.

    Accepts either a list of ticket dicts or a single dict with a
    ``tickets`` key.
    """
    return load_structured_tickets(path, yaml.safe_load)
