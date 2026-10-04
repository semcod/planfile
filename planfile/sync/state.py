"""Durable, repository-bound mappings for external ticket synchronisation."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml
from filelock import FileLock

from planfile.core.fastio import _atomic_write_text

SYNC_STATE_SCHEMA = "planfile.sync-state/v2"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class SyncStateRepositoryMismatch(ValueError):
    """Raised when a state file belongs to a different external repository."""


def normalize_repository(value: str | None) -> str | None:
    """Return a stable ``owner/name`` identity for GitHub-style repositories."""
    if value is None:
        return None
    candidate = str(value).strip()
    if candidate.lower().startswith("git@github.com:"):
        candidate = candidate[len("git@github.com:") :]
    for prefix in ("https://github.com/", "http://github.com/", "ssh://git@github.com/"):
        if candidate.lower().startswith(prefix):
            candidate = candidate[len(prefix) :]
            break
    candidate = candidate.removesuffix("/").removesuffix(".git")
    if not _REPOSITORY.fullmatch(candidate):
        raise ValueError("invalid repository identity; expected owner/name")
    owner, name = candidate.split("/", 1)
    return f"{owner.lower()}/{name.lower()}"


def _discover_repository(planfile_dir: Path, backend: str) -> str | None:
    """Read the repository target from the project-local integration config."""
    project_dir = planfile_dir.parent
    candidates = (
        project_dir / ".planfile" / f"{backend}.planfile.yaml",
        project_dir / ".planfile" / "integrations.oql.planfile.yaml",
    )
    for path in candidates:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        section = data.get("integrations", {}).get(backend, {})
        if isinstance(section, dict) and section.get("repo"):
            try:
                return normalize_repository(str(section["repo"]))
            except ValueError:
                return None
        section = data.get(backend, {})
        if isinstance(section, dict) and section.get("repo"):
            try:
                return normalize_repository(str(section["repo"]))
            except ValueError:
                return None
    return None


class SyncState:
    """Persist local-to-remote IDs without crossing repository boundaries.

    Version 1 state files (which only contained ``ticket_map``) remain readable
    and are upgraded on the first write. A configured repository is required for
    new sync runs; an existing different binding fails closed before any remote
    operation is attempted.
    """

    def __init__(
        self,
        planfile_dir: Path,
        backend: str,
        repository: str | None = None,
    ):
        self.planfile_dir = Path(planfile_dir)
        self.backend = str(backend)
        self.repository = (
            normalize_repository(repository)
            if repository
            else _discover_repository(self.planfile_dir, self.backend)
        )
        # A clone-local, non-secret namespace prevents two Planfile stores
        # using the same local ticket number from claiming one another's issue.
        # It is deliberately derived from the store path and never persisted as
        # a credential or a user-facing path.
        self.store_identity = hashlib.sha256(
            str(self.planfile_dir.resolve()).encode("utf-8")
        ).hexdigest()[:16]
        self.state_file = self.planfile_dir / "sync" / f"{self.backend}.state.yaml"
        self.lock_file = self.state_file.with_suffix(self.state_file.suffix + ".lock")
        self.repository_id: str | None = None
        self._verified_aliases: set[str] = set()

    @staticmethod
    def _safe_state(state: dict) -> dict:
        return {
            key: state[key] for key in (
                "schema", "backend", "repository", "repository_id",
                "repository_aliases", "ticket_map", "synced_at",
            ) if key in state
        }

    @classmethod
    def from_backend(
        cls, planfile_dir: Path, backend_name: str, backend,
        *, dry_run: bool = False, persist: bool = True,
    ) -> SyncState:
        """Bind mappings to a fresh provider identity before following redirects.

        Dry-run performs no additional provider query or migration. Read-only
        reconciliation can verify the route with ``persist=False``. Providers
        without an explicit identity capability retain their existing contract.
        """
        from planfile.sync.operations import _backend_repository

        state = cls(planfile_dir, backend_name, repository=_backend_repository(backend))
        resolver = getattr(type(backend), "resolve_repository_identity", None)
        if dry_run or backend_name != "github" or not callable(resolver):
            return state
        # Clear prior per-batch proof before asking for a fresh observation.
        backend._verified_repository = None
        backend._verified_repository_aliases = ()
        initial = state._read_unlocked()
        identity = resolver(backend)
        if identity is None:
            return state
        canonical = normalize_repository(identity["repository"])
        repository_id = identity["repository_id"]
        recorded = normalize_repository(initial.get("repository"))
        recorded_id = initial.get("repository_id")
        if recorded_id is not None and str(recorded_id) != repository_id:
            raise SyncStateRepositoryMismatch("sync state numeric repository identity disagrees")
        # A v2 binding without a numeric ID needs a fresh observation of its
        # original route. Local alias strings cannot waive this check.
        aliases = set()
        configured = normalize_repository(backend.config.get("repo"))
        if configured and configured != canonical:
            aliases.add(configured)
        if recorded and recorded != canonical:
            previous = resolver(backend, recorded)
            if previous != identity:
                raise SyncStateRepositoryMismatch("previous repository route is not the same GitHub repository")
            aliases.add(recorded)
        candidates = initial.get("repository_aliases") or []
        if not isinstance(candidates, list) or len(candidates) > 16:
            raise SyncStateRepositoryMismatch("invalid repository alias inventory")
        for candidate in candidates:
            normalized = normalize_repository(candidate) if isinstance(candidate, str) else None
            if not normalized or normalized == canonical or normalized in aliases:
                continue
            try:
                observed = resolver(backend, normalized)
            except Exception as error:
                if getattr(error, "status", None) == 404:
                    continue
                raise
            if observed == identity:
                aliases.add(normalized)
        if len(aliases) > 16:
            raise SyncStateRepositoryMismatch("verified repository alias inventory exceeds bound")
        state.repository = canonical
        state.repository_id = repository_id
        state._verified_aliases = aliases
        binder = getattr(type(backend), "_bind_repository_identity", None)
        if callable(binder):
            binder(backend, identity)
        if persist:
            with state._locked():
                current = state._read_unlocked()
                binding = (current.get("repository"), current.get("repository_id"))
                if binding != (initial.get("repository"), initial.get("repository_id")):
                    raise SyncStateRepositoryMismatch("sync state binding changed during identity verification")
                clean = state._safe_state(current)
                clean.update(schema=SYNC_STATE_SCHEMA, backend=backend_name,
                             repository=canonical, repository_id=repository_id,
                             repository_aliases=sorted(aliases))
                if clean != current:
                    _atomic_write_text(state.state_file, yaml.safe_dump(clean, sort_keys=False))
        backend._verified_repository = canonical
        backend._verified_repository_aliases = tuple(sorted(aliases))
        return state

    def _read_unlocked(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            value = yaml.safe_load(self.state_file.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"invalid sync state: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("invalid sync state: expected mapping")
        return value

    def _validate_repository(self, state: dict) -> None:
        if (self.repository_id is not None and state.get("repository_id") is not None
                and str(state["repository_id"]) != self.repository_id):
            raise SyncStateRepositoryMismatch("sync state numeric repository identity disagrees")
        recorded = state.get("repository")
        if recorded is None or self.repository is None:
            return
        try:
            normalized = normalize_repository(str(recorded))
        except ValueError as exc:
            raise SyncStateRepositoryMismatch("sync state has invalid repository identity") from exc
        aliases: set[str] = set()
        for alias in state.get("repository_aliases") or []:
            if not isinstance(alias, str):
                continue
            try:
                aliases.add(normalize_repository(alias))
            except ValueError:
                continue
        accepted_alias = (normalized in self._verified_aliases if self.repository_id is not None
                          else self.repository in aliases)
        if normalized != self.repository and not accepted_alias:
            raise SyncStateRepositoryMismatch(
                f"sync state belongs to {normalized}, backend targets {self.repository}"
            )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.lock_file), timeout=30):
            yield

    def get_last_sync(self) -> dict:
        """Read and validate the current state without exposing credentials."""
        state = self._read_unlocked()
        self._validate_repository(state)
        return state

    def save_sync(self, ticket_map: dict[str, str]) -> None:
        """Merge mappings under a lock and replace the state atomically."""
        if not isinstance(ticket_map, dict):
            raise TypeError("ticket_map must be a mapping")
        clean_map = {
            str(local_id): str(remote_id)
            for local_id, remote_id in ticket_map.items()
            if str(local_id).strip() and str(remote_id).strip()
        }
        with self._locked():
            state = self._read_unlocked()
            self._validate_repository(state)
            # Only copy the documented, non-secret state fields. Older files
            # were permissive and could contain a token or an API response.
            state = self._safe_state(state)
            state["schema"] = SYNC_STATE_SCHEMA
            state["backend"] = self.backend
            if self.repository:
                state.setdefault("repository", self.repository)
            existing = state.get("ticket_map")
            if not isinstance(existing, dict):
                existing = {}
            state["ticket_map"] = {
                **{str(k): str(v) for k, v in existing.items()},
                **clean_map,
            }
            state["synced_at"] = datetime.now(timezone.utc).isoformat()
            content = yaml.safe_dump(state, default_flow_style=False, sort_keys=False)
            _atomic_write_text(self.state_file, content)

    def get_remote_id(self, local_id: str) -> str | None:
        """Look up a remote ID for a local ticket."""
        value = self.get_last_sync().get("ticket_map", {}).get(local_id)
        return str(value) if value is not None else None

    def get_local_id(self, remote_id: str) -> str | None:
        """Reverse-lookup a remote ID, rejecting ambiguous duplicate mappings."""
        state = self.get_last_sync()
        matches = [
            str(local_id)
            for local_id, mapped_id in (state.get("ticket_map") or {}).items()
            if str(mapped_id) == str(remote_id)
        ]
        if len(matches) > 1:
            raise ValueError(f"ambiguous sync mapping for remote ticket {remote_id}")
        return matches[0] if matches else None
