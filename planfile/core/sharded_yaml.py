"""Sharded YAML ticket storage.

The engine deliberately operates on plain dictionaries. Validation and public
models stay in :mod:`planfile.core.store`, so changing the physical layout does
not change the ticket contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from .fastio import mirror_path, read_yaml_fast

SHARDED_YAML_SCHEMA = "planfile.sharded-yaml/v1"
_NUMERIC_SUFFIX = re.compile(r"(\d+)$")

YamlWriter = Callable[..., None]


class ShardedYamlStorage:
    """Store sprint metadata separately from fixed-range ticket shards."""

    def __init__(
        self,
        sprints_dir: Path,
        yaml_writer: YamlWriter,
        *,
        shard_size: int = 100,
        custom_shards: int = 16,
    ) -> None:
        self.sprints_dir = Path(sprints_dir)
        self.yaml_writer = yaml_writer
        self.shard_size = max(1, int(shard_size))
        self.custom_shards = max(1, min(int(custom_shards), 256))

    def sprint_dir(self, sprint: str) -> Path:
        return self.sprints_dir / f"{sprint}.shards"

    def metadata_path(self, sprint: str) -> Path:
        return self.sprint_dir(sprint) / "metadata.yaml"

    def manifest_path(self, sprint: str) -> Path:
        return self.sprint_dir(sprint) / "manifest.json"

    def sprint_ids(self) -> list[str]:
        if not self.sprints_dir.exists():
            return []
        ids = [
            path.name[: -len(".shards")]
            for path in self.sprints_dir.glob("*.shards")
            if path.is_dir()
        ]
        return self._prioritize_sprints(ids)

    @staticmethod
    def _prioritize_sprints(sprints: list[str]) -> list[str]:
        order = {"current": 0, "backlog": 1}
        return sorted(set(sprints), key=lambda value: (order.get(value, 2), value))

    def shard_name(self, ticket_id: str) -> str:
        match = _NUMERIC_SUFFIX.search(str(ticket_id))
        if match:
            number = int(match.group(1))
            start = (number // self.shard_size) * self.shard_size
            end = start + self.shard_size - 1
            width = max(6, len(str(end)))
            return f"tickets-{start:0{width}d}-{end:0{width}d}.yaml"
        digest = hashlib.sha256(str(ticket_id).encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % self.custom_shards
        return f"tickets-custom-{bucket:02x}.yaml"

    def shard_path(self, sprint: str, ticket_id: str) -> Path:
        return self.sprint_dir(sprint) / self.shard_name(ticket_id)

    def ticket_files(self, sprint: str) -> list[Path]:
        directory = self.sprint_dir(sprint)
        return sorted(directory.glob("tickets-*.yaml")) if directory.exists() else []

    def storage_files(self, sprint: str) -> list[Path]:
        paths = [self.metadata_path(sprint), *self.ticket_files(sprint)]
        manifest = self.manifest_path(sprint)
        if manifest.exists():
            paths.append(manifest)
        return [path for path in paths if path.exists()]

    @staticmethod
    def _root(data: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        root = data.get("sprint", data)
        return root if isinstance(root, dict) else {}

    @staticmethod
    def _tickets(data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not isinstance(data, dict):
            return {}
        root = data.get("tickets")
        if root is None:
            root = ShardedYamlStorage._root(data).get("tickets")
        return root if isinstance(root, dict) else {}

    def load_sprint(self, sprint: str) -> dict[str, Any]:
        metadata_data = read_yaml_fast(self.metadata_path(sprint)) or {}
        metadata = dict(self._root(metadata_data))
        tickets: dict[str, dict[str, Any]] = {}
        for path in self.ticket_files(sprint):
            tickets.update(self._tickets(read_yaml_fast(path)))
        metadata.setdefault("id", sprint)
        metadata.setdefault("name", sprint.replace("-", " ").title())
        metadata.setdefault("status", "active")
        metadata["tickets"] = tickets
        return {"sprint": metadata}

    def get_ticket(self, sprint: str, ticket_id: str) -> dict[str, Any] | None:
        data = read_yaml_fast(self.shard_path(sprint, ticket_id)) or {}
        ticket = self._tickets(data).get(ticket_id)
        return dict(ticket) if isinstance(ticket, dict) else None

    def locate_ticket(self, ticket_id: str) -> tuple[str, dict[str, Any]] | None:
        for sprint in self.sprint_ids():
            ticket = self.get_ticket(sprint, ticket_id)
            if ticket is not None:
                return sprint, ticket
        return None

    def ensure_sprint(
        self,
        sprint: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        path = self.metadata_path(sprint)
        if path.exists():
            return
        root = {
            "id": sprint,
            "name": sprint.replace("-", " ").title(),
            "status": "active",
            **(metadata or {}),
        }
        root.pop("tickets", None)
        self.yaml_writer(path, {"sprint": root}, allow_unicode=True)
        self._write_manifest(
            sprint,
            {
                "schema": SHARDED_YAML_SCHEMA,
                "sprint": sprint,
                "generation": 1,
                "shard_size": self.shard_size,
                "custom_shards": self.custom_shards,
                "ticket_count": 0,
                "shards": {},
            },
        )

    def upsert_ticket(
        self,
        sprint: str,
        ticket_id: str,
        ticket: dict[str, Any],
    ) -> None:
        self.upsert_tickets(sprint, {ticket_id: ticket})

    def upsert_tickets(
        self,
        sprint: str,
        incoming: dict[str, dict[str, Any]],
    ) -> None:
        if not incoming:
            return
        self.ensure_sprint(sprint)
        grouped: dict[Path, dict[str, dict[str, Any]]] = {}
        for ticket_id, ticket in incoming.items():
            grouped.setdefault(self.shard_path(sprint, ticket_id), {})[ticket_id] = ticket

        counts: dict[Path, int] = {}
        for path, additions in grouped.items():
            data = read_yaml_fast(path) or {"tickets": {}}
            tickets = self._tickets(data)
            tickets.update(additions)
            self.yaml_writer(path, {"tickets": tickets}, allow_unicode=True)
            counts[path] = len(tickets)

        manifest = self._read_manifest(sprint)
        if not self._valid_manifest(manifest, sprint):
            self._rebuild_manifest(sprint)
            return
        shards = dict(manifest["shards"])
        for path, count in counts.items():
            shards[path.name] = self._shard_manifest_entry(path, count)
        manifest.update(
            generation=int(manifest.get("generation", 0)) + 1,
            shard_size=self.shard_size,
            custom_shards=self.custom_shards,
            ticket_count=sum(int(item.get("count", 0)) for item in shards.values()),
            shards=shards,
        )
        self._write_manifest(sprint, manifest)

    def delete_ticket(self, sprint: str, ticket_id: str) -> dict[str, Any] | None:
        path = self.shard_path(sprint, ticket_id)
        data = read_yaml_fast(path) or {}
        tickets = self._tickets(data)
        removed = tickets.pop(ticket_id, None)
        if removed is None:
            return None
        if tickets:
            self.yaml_writer(path, {"tickets": tickets}, allow_unicode=True)
            count = len(tickets)
        else:
            path.unlink(missing_ok=True)
            mirror_path(path).unlink(missing_ok=True)
            count = 0
        self._update_manifest_for_shard(sprint, path, count)
        return dict(removed)

    def write_sprint(self, sprint: str, data: dict[str, Any]) -> None:
        root = dict(self._root(data))
        tickets = self._tickets(root)
        root.pop("tickets", None)
        root.setdefault("id", sprint)
        self.yaml_writer(self.metadata_path(sprint), {"sprint": root}, allow_unicode=True)

        grouped: dict[str, dict[str, dict[str, Any]]] = {}
        for ticket_id, ticket in tickets.items():
            grouped.setdefault(self.shard_name(ticket_id), {})[ticket_id] = ticket

        directory = self.sprint_dir(sprint)
        existing = {path.name: path for path in self.ticket_files(sprint)}
        for filename, shard_tickets in grouped.items():
            path = directory / filename
            current = self._tickets(read_yaml_fast(path)) if path.exists() else None
            if current != shard_tickets:
                self.yaml_writer(path, {"tickets": shard_tickets}, allow_unicode=True)
        for filename, path in existing.items():
            if filename in grouped:
                continue
            path.unlink(missing_ok=True)
            mirror_path(path).unlink(missing_ok=True)

        old = self._read_manifest(sprint)
        generation = int(old.get("generation", 0)) + 1
        self._write_manifest(
            sprint,
            {
                "schema": SHARDED_YAML_SCHEMA,
                "sprint": sprint,
                "generation": generation,
                "shard_size": self.shard_size,
                "custom_shards": self.custom_shards,
                "ticket_count": len(tickets),
                "shards": {
                    filename: self._shard_manifest_entry(
                        directory / filename,
                        len(shard_tickets),
                    )
                    for filename, shard_tickets in sorted(grouped.items())
                },
            },
        )

    def sprint_size(self, sprint: str) -> int:
        total = 0
        for path in self.storage_files(sprint):
            try:
                total += path.stat().st_size
            except OSError:
                continue
        return total

    def signature(self, sprint: str) -> tuple[tuple[str, int, int], ...]:
        result = []
        for path in self.storage_files(sprint):
            try:
                stat = path.stat()
                result.append((str(path), stat.st_mtime_ns, stat.st_size))
            except OSError:
                result.append((str(path), -1, -1))
        return tuple(result)

    def summary(self, sprint: str) -> dict[str, Any]:
        metadata = dict(self._root(read_yaml_fast(self.metadata_path(sprint)) or {}))
        manifest = self._read_manifest(sprint)
        if (
            not self._valid_manifest(manifest, sprint)
            or not self._manifest_matches_files(sprint, manifest)
        ):
            manifest = self._rebuild_manifest(sprint)
        declared_id = metadata.pop("id", None)
        metadata.pop("tickets", None)
        if declared_id and declared_id != sprint:
            metadata["declared_id"] = declared_id
        return metadata | {
            "id": sprint,
            "ticket_count": int(manifest.get("ticket_count", 0)),
        }

    def _read_manifest(self, sprint: str) -> dict[str, Any]:
        try:
            data = json.loads(self.manifest_path(sprint).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _valid_manifest(manifest: dict[str, Any], sprint: str) -> bool:
        return (
            manifest.get("schema") == SHARDED_YAML_SCHEMA
            and manifest.get("sprint") == sprint
            and isinstance(manifest.get("shards"), dict)
        )

    def _rebuild_manifest(self, sprint: str) -> dict[str, Any]:
        previous = self._read_manifest(sprint)
        shards = {}
        for path in self.ticket_files(sprint):
            shards[path.name] = self._shard_manifest_entry(
                path,
                len(self._tickets(read_yaml_fast(path))),
            )
        manifest = {
            "schema": SHARDED_YAML_SCHEMA,
            "sprint": sprint,
            "generation": int(previous.get("generation", 0)) + 1,
            "shard_size": self.shard_size,
            "custom_shards": self.custom_shards,
            "ticket_count": sum(item["count"] for item in shards.values()),
            "shards": shards,
        }
        self._write_manifest(sprint, manifest)
        return manifest

    def _update_manifest_for_shard(self, sprint: str, path: Path, count: int) -> None:
        manifest = self._read_manifest(sprint)
        if not self._valid_manifest(manifest, sprint):
            self._rebuild_manifest(sprint)
            return
        shards = dict(manifest["shards"])
        if count:
            shards[path.name] = self._shard_manifest_entry(path, count)
        else:
            shards.pop(path.name, None)
        manifest.update(
            generation=int(manifest.get("generation", 0)) + 1,
            shard_size=self.shard_size,
            custom_shards=self.custom_shards,
            ticket_count=sum(int(item.get("count", 0)) for item in shards.values()),
            shards=shards,
        )
        self._write_manifest(sprint, manifest)

    @staticmethod
    def _shard_manifest_entry(path: Path, count: int) -> dict[str, int]:
        try:
            stat = path.stat()
            return {
                "count": count,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
            }
        except OSError:
            return {"count": count, "mtime_ns": -1, "size": -1}

    def _manifest_matches_files(self, sprint: str, manifest: dict[str, Any]) -> bool:
        files = {path.name: path for path in self.ticket_files(sprint)}
        shards = manifest.get("shards") or {}
        if set(files) != set(shards):
            return False
        for filename, path in files.items():
            item = shards.get(filename)
            if not isinstance(item, dict):
                return False
            try:
                stat = path.stat()
            except OSError:
                return False
            if (
                item.get("mtime_ns") != stat.st_mtime_ns
                or item.get("size") != stat.st_size
            ):
                return False
        return True

    def _write_manifest(self, sprint: str, manifest: dict[str, Any]) -> None:
        path = self.manifest_path(sprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)
