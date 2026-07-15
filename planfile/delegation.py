"""Configured actor catalogue used by ticket delegation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path


_ACTOR_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class DelegationActor:
    """One human or bot that may receive a delegated ticket."""

    id: str
    label: str
    kind: str
    queue: str
    principal: str | None = None
    contract: str | None = None

    def model_dump(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


def load_delegation_actors(project_path: str | Path = ".") -> tuple[DelegationActor, ...]:
    """Load and validate the closed delegation catalogue.

    ``PLANFILE_DELEGATION_ACTORS_FILE`` takes precedence. Without it, Planfile
    looks for ``.planfile/delegation-actors.json``. A missing catalogue means
    delegation is disabled, never that arbitrary actor names are accepted.
    """

    configured = os.environ.get("PLANFILE_DELEGATION_ACTORS_FILE", "").strip()
    path = Path(configured) if configured else Path(project_path) / ".planfile" / "delegation-actors.json"
    if not path.is_file():
        return ()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"delegation_actor_catalog_invalid:{path}:{exc}") from exc

    rows = payload.get("actors") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("delegation_actor_catalog_invalid:actors_must_be_a_list")

    actors: list[DelegationActor] = []
    ids: set[str] = set()
    queues: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"delegation_actor_catalog_invalid:actor_{index}_must_be_an_object")
        if row.get("enabled", True) is False:
            continue
        actor_id = str(row.get("id", "")).strip()
        kind = str(row.get("kind", "")).strip()
        queue = str(row.get("queue", actor_id)).strip()
        label = str(row.get("label", actor_id)).strip()
        principal = str(row["principal"]).strip() if row.get("principal") else None
        contract = str(row["contract"]).strip() if row.get("contract") else None
        if not _ACTOR_ID.fullmatch(actor_id):
            raise ValueError(f"delegation_actor_catalog_invalid:actor_{index}_id")
        if kind not in {"human", "bot"}:
            raise ValueError(f"delegation_actor_catalog_invalid:{actor_id}_kind")
        if not _ACTOR_ID.fullmatch(queue):
            raise ValueError(f"delegation_actor_catalog_invalid:{actor_id}_queue")
        if not label:
            raise ValueError(f"delegation_actor_catalog_invalid:{actor_id}_label")
        if actor_id in ids:
            raise ValueError(f"delegation_actor_catalog_invalid:duplicate_id:{actor_id}")
        if queue in queues:
            raise ValueError(f"delegation_actor_catalog_invalid:duplicate_queue:{queue}")
        expected_principal = f"{kind}:{actor_id}"
        if principal and principal != expected_principal:
            raise ValueError(f"delegation_actor_catalog_invalid:{actor_id}_principal")
        ids.add(actor_id)
        queues.add(queue)
        actors.append(DelegationActor(actor_id, label, kind, queue, principal, contract))

    return tuple(actors)
