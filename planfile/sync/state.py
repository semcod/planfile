"""Track bidirectional sync state between planfile and external PM systems."""

import yaml
from pathlib import Path
from datetime import datetime


class SyncState:
    """Persist mapping between local ticket IDs and remote IDs."""

    def __init__(self, planfile_dir: Path, backend: str):
        self.state_file = planfile_dir / "sync" / f"{backend}.state.yaml"

    def get_last_sync(self) -> dict:
        if self.state_file.exists():
            return yaml.safe_load(self.state_file.read_text(encoding="utf-8")) or {}
        return {}

    def save_sync(self, ticket_map: dict):
        """Save mapping: local_id → remote_id."""
        state = self.get_last_sync()
        state["ticket_map"] = {**state.get("ticket_map", {}), **ticket_map}
        state["synced_at"] = datetime.utcnow().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            yaml.dump(state, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def get_remote_id(self, local_id: str) -> str | None:
        """Look up remote ID for a local ticket."""
        state = self.get_last_sync()
        return state.get("ticket_map", {}).get(local_id)

    def get_local_id(self, remote_id: str) -> str | None:
        """Reverse lookup: remote ID → local ID."""
        state = self.get_last_sync()
        for lid, rid in state.get("ticket_map", {}).items():
            if rid == remote_id:
                return lid
        return None
