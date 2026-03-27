"""Shared helpers for planfile API and MCP servers."""


from planfile import Planfile

_planfile: Planfile | None = None


def get_planfile(start_path: str = ".") -> Planfile:
    """Return a cached Planfile instance discovered from the project tree."""
    global _planfile
    if _planfile is None:
        _planfile = Planfile.auto_discover(start_path)
    return _planfile
