import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
from filelock import FileLock
from procache import CachedPyGithubRequester, SQLiteResponseCache
from rich.console import Console

from planfile.sync.base import BasePMBackend, TicketRef, TicketState
from planfile.sync.state import normalize_repository

try:
    from github import Github
    from github.GithubObject import GithubObject
    from github.Issue import Issue
    from github.Repository import Repository
except ImportError:
    Github = None
    GithubObject = None
    Issue = None
    Repository = None  # pip install PyGithub

console = Console()
logger = logging.getLogger(__name__)


class GitHubReadCache:
    """Small durable cache for safe, repeatable GitHub reads.

    Only metadata such as label names and issue identities is cached. Mutations
    and issue bodies never enter this cache. SQLite makes the cache reusable by
    separate hourly CLI processes while FileLock serializes schema and writes.
    """

    def __init__(self, repository: str, config: dict[str, Any]):
        self.enabled = bool(config.get("cache_enabled", True))
        self.ttl = max(0.0, float(config.get("cache_ttl_seconds", 600)))
        configured_dir = config.get("cache_dir") or os.environ.get("PLANFILE_GITHUB_CACHE_DIR")
        root = Path(configured_dir or Path.home() / ".cache" / "planfile" / "github")
        # A hit in this metadata layer skips the account-scoped HTTP requester.
        # Keep it isolated by the same principal and provider origin.
        identity = json.dumps([
            "github-metadata-v2", repository,
            config.get("token") or os.environ.get("GITHUB_TOKEN"),
            config.get("base_url") or config.get("api_url") or "https://api.github.com",
        ], separators=(",", ":"))
        self.path = root / f"{hashlib.sha256(identity.encode()).hexdigest()[:24]}.sqlite3"
        self.lock = FileLock(str(self.path) + ".lock")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute(
            """CREATE TABLE IF NOT EXISTS github_read_cache (
                namespace TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload TEXT,
                expires_at REAL NOT NULL,
                PRIMARY KEY (namespace, cache_key)
            )"""
        )
        connection.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return connection

    def get(self, namespace: str, cache_key: str) -> tuple[bool, Any]:
        if not self.enabled or self.ttl <= 0:
            return False, None
        with self.lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT payload, expires_at FROM github_read_cache "
                    "WHERE namespace=? AND cache_key=?",
                    (namespace, cache_key),
                ).fetchone()
                if row is None:
                    return False, None
                if row[1] <= time.time():
                    connection.execute(
                        "DELETE FROM github_read_cache WHERE namespace=? AND cache_key=?",
                        (namespace, cache_key),
                    )
                    connection.commit()
                    return False, None
                return True, json.loads(row[0])
            finally:
                connection.close()

    def put(self, namespace: str, cache_key: str, value: Any, ttl: float | None = None) -> None:
        if not self.enabled or self.ttl <= 0:
            return
        expires_at = time.time() + (self.ttl if ttl is None else max(0.0, ttl))
        with self.lock:
            connection = self._connect()
            try:
                connection.execute(
                    "INSERT OR REPLACE INTO github_read_cache "
                    "(namespace, cache_key, payload, expires_at) VALUES (?, ?, ?, ?)",
                    (namespace, cache_key, json.dumps(value, sort_keys=True), expires_at),
                )
                connection.commit()
            finally:
                connection.close()

    def clear(self) -> None:
        if not self.enabled:
            return
        with self.lock:
            connection = self._connect()
            try:
                connection.execute("DELETE FROM github_read_cache")
                connection.commit()
            finally:
                connection.close()


class GitHubBackend(BasePMBackend):
    """GitHub Issues integration backend."""

    # Sync owns the managed description, not deliberate tracker titles.
    preserves_remote_titles = True
    _managed_description_projection = True

    MAX_LABEL_LENGTH = 50
    DEFAULT_MUTATION_INTERVAL = 1.0
    MAX_QUARANTINED_INBOUND_ISSUES = 64
    QUARANTINE_PREVIEW_LIMIT = 5

    def __init__(self, repo: str, token: str | None = None, **kwargs):
        """
        Initialize GitHub backend.

        Args:
            repo: Repository in format "owner/repo"
            token: GitHub token (defaults to GITHUB_TOKEN env var)
        """
        if Github is None:
            raise ImportError("PyGithub is required. Install with: pip install PyGithub")

        config = {"repo": repo, "token": token or os.environ.get("GITHUB_TOKEN"), **kwargs}
        super().__init__(config)

        cache_path = self.config.get("cache_path") or os.environ.get("SUBACTOR_PROCACHE_PATH")
        if cache_path is None:
            cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            cache_path = cache_root / "subactor" / "planfile-github.sqlite3"
        self._provider_read_cache = SQLiteResponseCache(cache_path, namespace=f"planfile-github:{repo}")
        # OutboundJournal owns durable retry/cooldown. PyGithub's default retry
        # can sleep until quota reset before the journal ever sees the failure.
        self.github = Github(self.config["token"], retry=0, per_page=100)
        # Identity observations must bypass the read cache: an old name may
        # have been reused by a different repository since the cached response.
        self._identity_requester = self.github.requester
        self.github._Github__requester = CachedPyGithubRequester(
            self.github.requester,
            self._provider_read_cache,
            ttl=float(os.environ.get("SUBACTOR_GITHUB_READ_TTL", "15")),
        )
        self.repo: Repository = self.github.get_repo(repo)
        self._label_names: set[str] | None = None
        self._last_mutation_at = 0.0
        self._mutation_interval = float(kwargs.get("mutation_interval", self.DEFAULT_MUTATION_INTERVAL))
        self._read_cache = GitHubReadCache(repo, self.config)
        self._quarantined_inbound_issues: list[dict[str, str]] = []
        self._quarantined_inbound_count = 0

    @property
    def quarantined_inbound_issues(self) -> tuple[dict[str, str], ...]:
        """Bounded body-free diagnostics for issues quarantined in the latest _list_tickets pass."""
        return tuple(getattr(self, "_quarantined_inbound_issues", ()))

    @property
    def quarantined_inbound_count(self) -> int:
        """Total number of issues quarantined in the latest _list_tickets pass."""
        return int(getattr(self, "_quarantined_inbound_count", 0))

    def _record_quarantined_inbound_issue(self, issue: Any, reason: str) -> None:
        """Record one body-free quarantine diagnostic for an unreadable remote issue."""
        repo_name = (
            getattr(self, "_verified_repository", None)
            or getattr(getattr(self, "repo", None), "full_name", None)
            or (getattr(self, "config", {}) or {}).get("repo", "")
            or ""
        )
        raw_number = getattr(issue, "number", None)
        issue_id = "" if raw_number is None else str(raw_number)
        issue_key = (
            f"{repo_name}#{issue_id}"
            if repo_name and issue_id
            else (f"#{issue_id}" if issue_id else repo_name)
        )
        record = {
            "id": issue_id,
            "key": issue_key,
            "url": str(getattr(issue, "html_url", "") or ""),
            "state": str(getattr(issue, "state", "") or ""),
            "reason": reason,
        }
        self._quarantined_inbound_count = int(getattr(self, "_quarantined_inbound_count", 0)) + 1
        records = getattr(self, "_quarantined_inbound_issues", None)
        if not isinstance(records, list):
            records = []
            self._quarantined_inbound_issues = records
        if len(records) < self.MAX_QUARANTINED_INBOUND_ISSUES:
            records.append(record)
        logger.warning(
            "Quarantined GitHub issue %s during inbound list_tickets: %s",
            issue_key or "<unknown>",
            reason,
        )

    def resolve_repository_identity(self, repository: str | None = None) -> dict | None:
        """Verify a named route against fresh GitHub numeric-ID readback."""
        from planfile.sync.state import SyncStateRepositoryMismatch, normalize_repository

        requester = getattr(self, "_identity_requester", None)
        if requester is None:
            # Legacy adapters/test doubles do not claim redirect capability.
            return None
        name = normalize_repository(repository or self.config["repo"])
        _, metadata = requester.requestJsonAndCheck("GET", f"/repos/{name}")
        identity = metadata.get("id") if isinstance(metadata, dict) else None
        if not isinstance(identity, int) or isinstance(identity, bool) or identity <= 0:
            raise SyncStateRepositoryMismatch("GitHub repository identity is unavailable")
        canonical = normalize_repository(metadata.get("full_name"))
        _, confirmed = requester.requestJsonAndCheck("GET", f"/repositories/{identity}")
        if (not canonical or not isinstance(confirmed, dict)
                or not isinstance(confirmed.get("id"), int) or isinstance(confirmed.get("id"), bool)
                or confirmed.get("id") != identity
                or normalize_repository(confirmed.get("full_name")) != canonical):
            raise SyncStateRepositoryMismatch("GitHub repository identity readback disagrees")
        return {"repository": canonical, "repository_id": str(identity)}

    def _bind_repository_identity(self, identity: dict) -> None:
        """Use the verified numeric route rather than a stale SDK name handle."""
        client = getattr(self, "github", None)
        if client is None:
            return
        requester = client.requester
        self.repo = Repository(
            requester, completed=True,
            attributes={
                "id": int(identity["repository_id"]),
                "full_name": identity["repository"],
                "url": f"{requester.base_url.rstrip('/')}/repositories/{identity['repository_id']}",
            },
        )

    def _cache(self) -> GitHubReadCache:
        cache = getattr(self, "_read_cache", None)
        if cache is None:
            repository = str(getattr(self.repo, "full_name", self.config.get("repo", "")))
            cache = GitHubReadCache(repository, self.config)
            self._read_cache = cache
        return cache

    def _validate_config(self) -> None:
        """Validate GitHub configuration."""
        if not self.config.get("token"):
            raise ValueError("GitHub token is required")

        if not self.config.get("repo"):
            raise ValueError("Repository is required")

        if "/" not in self.config["repo"]:
            raise ValueError("Repository must be in format 'owner/repo'")

    def _clear_read_cache(self) -> None:
        metadata_cache = getattr(self, "_read_cache", None)
        if metadata_cache is not None:
            metadata_cache.clear()
        provider_cache = getattr(self, "_provider_read_cache", None)
        if provider_cache is not None:
            provider_cache.clear()

    def _ensure_labels_exist(self, labels: list[str]):
        """Ensure labels exist in the repository, create them if needed."""
        if getattr(self, "_label_names", None) is None:
            hit, cached = self._cache().get("labels", "names")
            if hit:
                self._label_names = set(cached or [])
            else:
                self._label_names = {label.name for label in self.repo.get_labels()}
                self._cache().put("labels", "names", sorted(self._label_names))

        for label in labels:
            if label not in self._label_names:
                self._throttle_mutation()
                try:
                    self.repo.create_label(
                        name=label,
                        color="0366d6",  # Default blue color
                        description=f"Auto-created label for {label}",
                    )
                except Exception as error:
                    if getattr(error, "status", None) in {403, 429} or any(
                        marker in str(error).lower()
                        for marker in ("rate limit", "secondary rate", "abuse detection")
                    ):
                        raise
                self._label_names.add(label)
                self._cache().put("labels", "names", sorted(self._label_names))

    def _throttle_mutation(self) -> None:
        """Keep provider mutations below GitHub's abuse-detection threshold."""
        interval = getattr(self, "_mutation_interval", 0.0)
        last = getattr(self, "_last_mutation_at", 0.0)
        delay = interval - (time.monotonic() - last)
        if delay > 0:
            time.sleep(delay)
        self._last_mutation_at = time.monotonic()

    @classmethod
    def _canonical_labels(cls, labels: list[str] | None, priority: str | None) -> list[str]:
        """Build and validate the provider label projection without I/O."""
        issue_labels = []
        for raw_label in labels or []:
            if not isinstance(raw_label, str):
                raise ValueError(f"Invalid GitHub label: {raw_label!r}")
            # Dedupe keys are persisted in metadata/body markers. They are not
            # GitHub labels and can exceed GitHub's 50-character limit.
            if raw_label.startswith("dedupe:") or raw_label.startswith("priority: "):
                continue
            if not raw_label or any(ord(char) < 32 for char in raw_label):
                raise ValueError(f"Invalid GitHub label: {raw_label!r}")
            parts = (
                [part.strip() for part in raw_label.split(",") if part.strip()]
                if "," in raw_label
                else [raw_label]
            )
            if not parts:
                raise ValueError(f"Invalid GitHub label: {raw_label!r}")
            for label in parts:
                if label.startswith("dedupe:") or label.startswith("priority: "):
                    continue
                if not label or len(label) > cls.MAX_LABEL_LENGTH or any(ord(char) < 32 for char in label):
                    raise ValueError(f"Invalid GitHub label: {label!r}")
                if label not in issue_labels:
                    issue_labels.append(label)
        if priority:
            priority_label = f"priority-{priority}"
            if len(priority_label) > cls.MAX_LABEL_LENGTH:
                raise ValueError(f"Invalid GitHub label: {priority_label!r}")
            if priority_label not in issue_labels:
                issue_labels.append(priority_label)
        for default in ("planfile", "managed"):
            if default not in issue_labels:
                issue_labels.append(default)
        return issue_labels

    def preflight(self, tickets) -> None:
        """Validate lifecycle, templates and labels before the first provider mutation."""
        template = self._resolve_issue_template()
        extra_labels = self._merge_unique_labels(
            self._default_configured_labels(),
            template["labels"] if template is not None else None,
        )
        for _, ticket in tickets:
            status = ticket.get("status")
            if status and self.project_remote_status(status) is None:
                raise ValueError("sync_github_status_unsupported")
        for _, ticket in tickets:
            merged_labels = self._merge_unique_labels(extra_labels, ticket.get("labels"))
            self._canonical_labels(merged_labels, ticket.get("priority"))

    def _prepare_labels(
        self,
        labels: list[str] | None,
        priority: str | None,
    ) -> list[str]:
        """Build label list, filtering old priority labels and adding defaults."""
        issue_labels = self._canonical_labels(labels, priority)
        self._ensure_labels_exist(issue_labels)
        return issue_labels

    def _build_metadata_body(self, body: str, metadata: dict[str, Any] | None) -> str:
        """Append strategy metadata section to body."""
        if not metadata:
            return body
        metadata = dict(metadata)
        if metadata.get("planfile_id") and not any(
            metadata.get(key) for key in ("deduplication_key", "dedupe_key", "fingerprint")
        ):
            local_id = str(metadata["planfile_id"])
            repository = str(getattr(self.repo, "full_name", self.config.get("repo", "")))
            if repository and not local_id.startswith(f"{repository}:"):
                # Legacy callers supplied a store-local ID only. Namespacing it
                # by the target repository prevents cross-repository marker
                # collisions while preserving same-store retry idempotency.
                metadata["planfile_id"] = f"{repository}:{local_id}"
        deduplication_key = next(
            (
                str(metadata[key]).strip()
                for key in ("deduplication_key", "dedupe_key", "fingerprint", "planfile_id")
                if metadata.get(key)
            ),
            None,
        )
        if deduplication_key:
            safe_key = deduplication_key.replace("-->", "").replace("\n", " ")
            marker = f"<!-- planfile:deduplication-key={safe_key} -->"
            if marker not in body:
                body = f"{marker}\n{body}"
        metadata_section = "\n\n---\n\n**Strategy Metadata:**\n"
        for key, value in metadata.items():
            if key != "model_hints":
                metadata_section += f"- {key}: {value}\n"
        if "model_hints" in metadata:
            metadata_section += "\n**Model Hints:**\n"
            for phase, tier in metadata["model_hints"].items():
                if tier:
                    metadata_section += f"- {phase}: {tier}\n"
        return body + metadata_section

    DESCRIPTION_START = "<!-- planfile:description:start -->"
    DESCRIPTION_END = "<!-- planfile:description:end -->"

    @classmethod
    def _description_bounds(cls, body: str) -> tuple[int, int] | None:
        """Accept only an absent or unique, well ordered owned region."""
        starts, ends = body.count(cls.DESCRIPTION_START), body.count(cls.DESCRIPTION_END)
        if not starts and not ends:
            return None
        if starts != 1 or ends != 1:
            raise ValueError("sync_github_description_markers_ambiguous")
        start, end = body.index(cls.DESCRIPTION_START), body.index(cls.DESCRIPTION_END)
        if end < start:
            raise ValueError("sync_github_description_markers_ambiguous")
        return start, end + len(cls.DESCRIPTION_END)

    @classmethod
    def _description_text(cls, body: str | None) -> str:
        """Import owned text; unmarked legacy issues retain whole-body imports."""
        current = body or ""
        bounds = cls._description_bounds(current)
        if bounds is None:
            return current
        start, end = bounds
        return current[start + len(cls.DESCRIPTION_START):end - len(cls.DESCRIPTION_END)].strip()

    @classmethod
    def _merge_description(cls, existing: str | None, description: str) -> str:
        """Write the description into its own section and keep the rest.

        An issue body accumulates discussion, evidence and decisions from
        everyone; the ticket description is the local planning record.
        Replacing the body with the description deletes the former, so own a
        delimited section and leave every other line untouched.
        """
        if cls.DESCRIPTION_START in description or cls.DESCRIPTION_END in description:
            raise ValueError("sync_github_description_contains_reserved_marker")
        section = f"{cls.DESCRIPTION_START}\n{description.strip()}\n{cls.DESCRIPTION_END}"
        current = existing or ""
        bounds = cls._description_bounds(current)
        if bounds is not None:
            start, end = bounds
            return current[:start] + section + current[end:]
        if not current:
            return section
        return f"{current}\n\n{section}"

    @staticmethod
    def _deduplication_markers(body: str | None) -> list[str]:
        patterns = (
            r"<!--\s*planfile:deduplication-key=[^>]+?\s*-->",
            r"<!--\s*ifuri-doctor:deduplication_key=[^>]+?\s*-->",
            r"<!--\s*ifuri-doctor:fingerprint=[^>]+?\s*-->",
        )
        return [match.group(0) for pattern in patterns if (match := re.search(pattern, body or ""))]

    def _find_issue_by_markers(self, markers: list[str]):
        if not markers:
            return None
        cache_key = json.dumps(sorted(markers), separators=(",", ":"))
        hit, cached = self._cache().get("markers", cache_key)
        if hit:
            return SimpleNamespace(**cached) if cached else None

        matches = []
        for issue in self.repo.get_issues(state="all"):
            # GitHub's list payload omits pull_request for ordinary issues.
            # PyGithub's lazy property then hydrates every issue individually.
            # Use the complete list projection; retain hydration for partial
            # objects and compatibility with alternative backend test doubles.
            # CompletableGithubObject.raw_data also triggers hydration; the
            # base accessor exposes only the payload already received.
            raw = (
                GithubObject.raw_data.fget(issue)
                if Issue is not None and isinstance(issue, Issue)
                else None
            )
            if isinstance(raw, dict) and {"number", "body", "state"} <= raw.keys():
                is_pull_request = raw.get("pull_request") is not None
            else:
                is_pull_request = bool(getattr(issue, "pull_request", None))
            if is_pull_request:
                continue
            if any(marker in (getattr(issue, "body", "") or "") for marker in markers):
                matches.append(issue)

        if not matches:
            self._cache_marker_result(markers, None)
            return None

        # Prioritize OPEN issues over CLOSED duplicates
        open_matches = [i for i in matches if getattr(i, "state", "").lower() == "open"]
        if open_matches:
            # Lowest issue number is canonical (oldest created)
            open_matches.sort(key=lambda i: getattr(i, "number", 0))
            canonical = open_matches[0]
            if len(open_matches) > 1:
                duplicate_numbers = [getattr(i, "number", None) for i in open_matches[1:]]
                canonical.duplicate_numbers = duplicate_numbers
                console.print(
                    f"  ⚠️  Detected duplicate open GitHub issues sharing markers: "
                    f"#{canonical.number} and duplicates {duplicate_numbers}; binding to #{canonical.number}"
                )
            return self._cache_marker_result(markers, canonical)

        # If only closed exist, select highest issue ID (most recently closed/created)
        matches.sort(key=lambda i: getattr(i, "number", 0), reverse=True)
        canonical = matches[0]
        if len(matches) > 1:
            duplicate_numbers = [getattr(i, "number", None) for i in matches[1:]]
            canonical.duplicate_numbers = duplicate_numbers
            console.print(
                f"  ⚠️  Detected duplicate closed GitHub issues sharing markers: "
                f"#{canonical.number} and duplicates {duplicate_numbers}; binding to #{canonical.number}"
            )
        return self._cache_marker_result(markers, canonical)

    def _cache_marker_result(self, markers: list[str], issue):
        """Cache one marker lookup, including a short-lived negative result."""
        cache_key = json.dumps(sorted(markers), separators=(",", ":"))
        if issue is None:
            self._cache().put("markers", cache_key, None, ttl=60)
        else:
            payload = {
                "number": getattr(issue, "number", None),
                "html_url": getattr(issue, "html_url", None),
                "state": getattr(issue, "state", None),
            }
            if hasattr(issue, "duplicate_numbers") and issue.duplicate_numbers:
                payload["duplicate_numbers"] = issue.duplicate_numbers
            self._cache().put(
                "markers",
                cache_key,
                payload,
            )
        return issue

    def _creation_lock(self, deduplication_key: str | None = None) -> FileLock:
        config = getattr(self, "config", {}) or {}
        configured_dir = config.get("cache_dir") or os.environ.get("PLANFILE_GITHUB_CACHE_DIR")
        root = Path(configured_dir or Path.home() / ".cache" / "planfile" / "github")
        lock_dir = root / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        repo_name = str(getattr(self.repo, "full_name", None) or config.get("repo", "repo"))
        repo_hash = hashlib.sha256(repo_name.encode("utf-8")).hexdigest()[:16]
        key_part = hashlib.sha256(str(deduplication_key or "default").encode("utf-8")).hexdigest()[:16]
        lock_file = lock_dir / f"create_{repo_hash}_{key_part}.lock"
        return FileLock(str(lock_file), timeout=60)

    @staticmethod
    def project_remote_status(status: str) -> str | None:
        """Project the existing Planfile lifecycle onto GitHub's two states."""
        normalized = str(getattr(status, "value", status)).strip().lower().replace("-", "_")
        if normalized in {"closed", "close", "resolved", "done", "completed", "failed", "canceled", "cancelled"}:
            return "closed"
        if normalized in {"open", "triage", "in_progress", "inprogress", "doing", "active", "todo", "backlog", "review", "blocked"}:
            return "open"
        return None

    TEMPLATE_TOKEN_RE = re.compile(
        r"\{\{\s*(description|body|title|name|id|ticket_id|priority|status|assignee|labels)\s*\}\}"
        r"|\{\s*(description|body|title|name|id|ticket_id|priority|status|assignee|labels)\s*\}"
    )
    FORM_SLOT_RE = re.compile(r"\x00FORM_SLOT:([A-Za-z0-9_.-]+)\x00")

    @staticmethod
    def _coerce_template_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("sync_github_issue_template_invalid")

    @staticmethod
    def _merge_unique_labels(*groups: list[str] | None) -> list[str]:
        merged: list[str] = []
        for group in groups:
            for label in group or ():
                if label and label not in merged:
                    merged.append(label)
        return merged

    def _default_configured_labels(self) -> list[str]:
        config = getattr(self, "config", None) or {}
        raw = config.get("default_labels") if isinstance(config, dict) else None
        return self._coerce_template_list(raw) if raw else []

    @staticmethod
    def _check_no_symlinks(base: Path, target: Path) -> None:
        resolved_base = base.resolve()
        try:
            relative = target.relative_to(base)
        except ValueError as exc:
            raise ValueError("sync_github_issue_template_invalid") from exc
        current = base
        if current.is_symlink():
            raise ValueError("sync_github_issue_template_invalid")
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("sync_github_issue_template_invalid")
        if not target.resolve().is_relative_to(resolved_base):
            raise ValueError("sync_github_issue_template_invalid")

    @classmethod
    def _resolve_template_file(cls, project_dir: Path, raw: str) -> Path | None:
        if "\x00" in raw or raw.startswith("~") or ".." in Path(raw).parts:
            raise ValueError("sync_github_issue_template_invalid")
        base = project_dir.resolve()
        raw_path = Path(raw)
        if raw_path.is_absolute():
            cls._check_no_symlinks(base, raw_path)
            if not raw_path.is_file():
                raise ValueError(f"sync_github_issue_template_not_found:{raw}")
            return raw_path

        if raw.lower() == "auto":
            for fixed in (".github/ISSUE_TEMPLATE.md", ".github/issue_template.md"):
                candidate = base / fixed
                cls._check_no_symlinks(base, candidate)
                if candidate.is_file():
                    return candidate
            tmpl_dir = base / ".github" / "ISSUE_TEMPLATE"
            cls._check_no_symlinks(base, tmpl_dir)
            if tmpl_dir.is_dir():
                found: list[Path] = []
                for entry in sorted(tmpl_dir.iterdir()):
                    cls._check_no_symlinks(base, entry)
                    if (
                        entry.is_file()
                        and entry.suffix.lower() in {".md", ".yml", ".yaml"}
                        and entry.name.lower() not in {"config.yml", "config.yaml"}
                    ):
                        found.append(entry)
                if len(found) == 1:
                    return found[0]
                if len(found) > 1:
                    raise ValueError("sync_github_issue_template_ambiguous")
            raise ValueError("sync_github_issue_template_not_found:auto")

        candidates = [base / raw_path]
        if "/" not in raw and "\\" not in raw:
            tmpl_root = base / ".github" / "ISSUE_TEMPLATE"
            candidates.extend([
                tmpl_root / raw,
                tmpl_root / f"{raw}.md",
                tmpl_root / f"{raw}.yml",
                tmpl_root / f"{raw}.yaml",
            ])
        for candidate in candidates:
            cls._check_no_symlinks(base, candidate)
            if candidate.is_file():
                return candidate

        looks_like_file = (
            "/" in raw
            or "\\" in raw
            or raw.startswith(".")
            or raw.lower().endswith((".md", ".yml", ".yaml", ".txt"))
        )
        if looks_like_file:
            raise ValueError(f"sync_github_issue_template_not_found:{raw}")
        return None

    @classmethod
    def _parse_markdown_issue_template(cls, text: str) -> dict[str, Any]:
        labels: list[str] = []
        assignees: list[str] = []
        title_default: str | None = None
        body = text
        match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, flags=re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
            except yaml.YAMLError as exc:
                raise ValueError("sync_github_issue_template_invalid") from exc
            if frontmatter is not None and not isinstance(frontmatter, dict):
                raise ValueError("sync_github_issue_template_invalid")
            if isinstance(frontmatter, dict):
                labels = cls._coerce_template_list(frontmatter.get("labels"))
                assignees = cls._coerce_template_list(frontmatter.get("assignees"))
                raw_title = frontmatter.get("title")
                if raw_title is not None and str(raw_title).strip():
                    title_default = str(raw_title).strip()
            body = text[match.end():].lstrip("\r\n")
        return {
            "kind": "markdown",
            "body": body,
            "labels": labels,
            "assignees": assignees,
            "title_default": title_default,
            "form_defaults": {},
        }

    @classmethod
    def _parse_yaml_form_template(cls, text: str) -> dict[str, Any]:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError("sync_github_issue_template_invalid") from exc
        if not isinstance(data, dict) or not isinstance(data.get("body"), list):
            raise ValueError("sync_github_issue_template_invalid")

        labels = cls._coerce_template_list(data.get("labels"))
        assignees = cls._coerce_template_list(data.get("assignees"))
        raw_title = data.get("title")
        title_default = str(raw_title).strip() if raw_title is not None and str(raw_title).strip() else None

        items = data["body"]
        has_explicit_desc = any(
            isinstance(item, dict)
            and isinstance(item.get("attributes"), dict)
            and (
                "{description}" in str(item["attributes"].get("value") or "")
                or "{body}" in str(item["attributes"].get("value") or "")
            )
            for item in items
        )
        desc_index: int | None = None
        if not has_explicit_desc:
            preferred_ids = {"description", "body", "summary", "details", "what_happened"}
            for idx, item in enumerate(items):
                if isinstance(item, dict) and str(item.get("id") or "").strip().lower() in preferred_ids:
                    desc_index = idx
                    break
            if desc_index is None:
                for idx, item in enumerate(items):
                    if isinstance(item, dict) and str(item.get("type") or "").strip().lower() == "textarea":
                        desc_index = idx
                        break

        blocks: list[str] = []
        form_defaults: dict[str, str] = {}
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError("sync_github_issue_template_invalid")
            item_type = str(item.get("type") or "").strip().lower()
            attrs = item.get("attributes") or {}
            if not isinstance(attrs, dict):
                raise ValueError("sync_github_issue_template_invalid")
            if item_type == "markdown":
                content = str(attrs.get("value") or "").strip()
                if content:
                    blocks.append(content)
                continue

            item_id = str(item.get("id") or "").strip()
            label = str(attrs.get("label") or item_id or "Details").strip()
            if idx == desc_index:
                section_value = "{description}"
            elif item_type == "checkboxes":
                options = attrs.get("options") or []
                lines = []
                for opt in options:
                    if isinstance(opt, dict) and opt.get("label"):
                        lines.append(f"- [ ] {str(opt['label']).strip()}")
                section_value = "\n".join(lines) or "_No response_"
            elif item_type == "dropdown":
                options = attrs.get("options") or []
                default_val = attrs.get("default")
                resolved_opt: str | None = None
                if isinstance(default_val, int) and not isinstance(default_val, bool) and 0 <= default_val < len(options):
                    resolved_opt = str(options[default_val])
                elif default_val is not None and str(default_val).strip():
                    resolved_opt = str(default_val).strip()
                if item_id:
                    form_defaults[item_id] = resolved_opt or "_No response_"
                    section_value = f"\x00FORM_SLOT:{item_id}\x00"
                else:
                    section_value = resolved_opt or "_No response_"
            else:
                explicit_val = attrs.get("value")
                fallback = (
                    str(explicit_val).strip()
                    if explicit_val is not None and str(explicit_val).strip()
                    else "_No response_"
                )
                if item_id and explicit_val is None:
                    form_defaults[item_id] = fallback
                    section_value = f"\x00FORM_SLOT:{item_id}\x00"
                else:
                    section_value = fallback
            blocks.append(f"### {label}\n\n{section_value}")

        return {
            "kind": "yaml_form",
            "body": "\n\n".join(blocks),
            "labels": labels,
            "assignees": assignees,
            "title_default": title_default,
            "form_defaults": form_defaults,
        }

    def _resolve_issue_template(self) -> dict[str, Any] | None:
        config = getattr(self, "config", None) or {}
        raw_spec = config.get("issue_template") if isinstance(config, dict) else None
        if raw_spec is None:
            return None
        if not isinstance(raw_spec, str):
            raise ValueError("sync_github_issue_template_invalid")
        raw = raw_spec.strip()
        if not raw:
            return None

        if "\n" not in raw:
            project_dir = Path(str(config.get("project_dir") or ".")).resolve()
            file_path = self._resolve_template_file(project_dir, raw)
            if file_path is not None:
                try:
                    content = file_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    raise ValueError("sync_github_issue_template_invalid") from exc
                if file_path.suffix.lower() in {".yml", ".yaml"}:
                    return self._parse_yaml_form_template(content)
                return self._parse_markdown_issue_template(content)

        return self._parse_markdown_issue_template(raw_spec)

    def _render_issue_template(
        self,
        template: dict[str, Any],
        ticket: dict[str, Any],
        description: str | None,
    ) -> tuple[str, list[str], str | None, str | None]:
        raw_name = str(ticket.get("name") or ticket.get("title") or "").strip()
        resolved_name = raw_name or template.get("title_default") or None
        merged_labels = self._merge_unique_labels(
            self._default_configured_labels(),
            template.get("labels"),
            ticket.get("labels"),
        )
        assignees = template.get("assignees") or []
        resolved_assignee = ticket.get("assignee") or (assignees[0] if assignees else None)

        plain_description = "" if description is None else str(description)
        managed_section = None if description is None else self._merge_description(None, plain_description)
        used_managed = False

        metadata = ticket.get("metadata") if isinstance(ticket.get("metadata"), dict) else {}
        form_defaults = template.get("form_defaults") or {}

        def _replace_form_slot(match: re.Match[str]) -> str:
            field_id = match.group(1)
            candidate = ticket.get(field_id)
            if candidate is None:
                candidate = metadata.get(field_id)
            if candidate is not None and str(candidate).strip():
                return str(candidate).strip()
            return str(form_defaults.get(field_id, "_No response_"))

        values = {
            "title": raw_name or (resolved_name or ""),
            "name": raw_name or (resolved_name or ""),
            "id": str(ticket.get("id") or ""),
            "ticket_id": str(ticket.get("id") or ""),
            "priority": str(ticket.get("priority") or ""),
            "status": str(ticket.get("status") or ""),
            "assignee": str(resolved_assignee or ""),
            "labels": ", ".join(merged_labels),
        }

        def _replace_token(match: re.Match[str]) -> str:
            nonlocal used_managed
            token = match.group(1) or match.group(2)
            if token in {"description", "body"}:
                if managed_section is None:
                    return ""
                if not used_managed:
                    used_managed = True
                    return managed_section
                return plain_description.strip()
            return values.get(token, match.group(0))

        rendered_body = self.TEMPLATE_TOKEN_RE.sub(
            _replace_token, str(template.get("body") or "")
        )
        rendered_body = self.FORM_SLOT_RE.sub(_replace_form_slot, rendered_body)
        if managed_section is not None and not used_managed:
            rendered_body = self._merge_description(rendered_body, plain_description)
        self._description_bounds(rendered_body)
        return rendered_body, merged_labels, resolved_name, resolved_assignee

    def create_ticket(self, ticket: dict[str, Any], **kwargs) -> TicketRef:
        """Apply lifecycle to both a new issue and a durable-marker match."""
        status = ticket.get("status")
        # Reject unsupported states before a non-idempotent provider create.
        expected = self.project_remote_status(status) if status else None
        if status and expected is None:
            raise ValueError("sync_github_status_unsupported")
        payload = dict(ticket)
        description = ticket.get("description") if "description" in ticket else ticket.get("body")
        template = self._resolve_issue_template()
        if template is not None:
            rendered_body, merged_labels, resolved_name, resolved_assignee = self._render_issue_template(
                template, payload, description
            )
            payload["description"] = rendered_body
            payload["labels"] = merged_labels
            if resolved_name and not str(payload.get("name") or payload.get("title") or "").strip():
                payload["name"] = resolved_name
            if resolved_assignee and not payload.get("assignee"):
                payload["assignee"] = resolved_assignee
        else:
            default_labels = self._default_configured_labels()
            if default_labels:
                payload["labels"] = self._merge_unique_labels(default_labels, payload.get("labels"))
            if description is not None:
                payload["description"] = self._merge_description(None, description)
        reference = super().create_ticket(payload, **kwargs)
        self._clear_read_cache()
        issue = self.repo.get_issue(int(reference.id))
        if getattr(issue, "pull_request", None) is not None:
            raise ValueError("sync_github_create_resolved_pull_request")
        if description is not None:
            # A durable marker may resolve to an older issue. Repair that same
            # issue's owned region and preserve its independently written prose.
            self._update_ticket(str(reference.id), body=description)
        if expected is not None:
            self._update_issue_state(issue, status)
            self._clear_read_cache()
            reference = reference.model_copy(update={"status": issue.state})
        return reference

    def _create_ticket(
        self,
        name: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        """Create a new GitHub issue."""
        body = self._build_metadata_body(body, metadata)
        self._description_bounds(body)
        markers = self._deduplication_markers(body)
        dedup_key = markers[0] if markers else None

        with self._creation_lock(dedup_key):
            existing = self._find_issue_by_markers(markers)
            if existing is not None:
                if getattr(existing, "pull_request", None) is not None:
                    raise ValueError(
                        f"{self.repo.full_name}#{existing.number} is a pull request, not an issue"
                    )
                self._description_bounds(getattr(existing, "body", "") or "")
                return self.build_ticket_ref(
                    id=str(existing.number),
                    url=existing.html_url,
                    key=f"{self.repo.full_name}#{existing.number}",
                    status=existing.state,
                    metadata=metadata,
                )

            create_kwargs = {
                "title": name,
                "body": body,
                "labels": self._prepare_labels(labels, priority),
            }
            if assignee:
                create_kwargs["assignee"] = assignee

            self._throttle_mutation()
            issue: Issue = self.repo.create_issue(**create_kwargs)
            self._clear_read_cache()
            if markers:
                self._cache_marker_result(markers, issue)

            return self.build_ticket_ref(
                id=str(issue.number),
                url=issue.html_url,
                key=f"{self.repo.full_name}#{issue.number}",
                status=issue.state,
                metadata=metadata,
            )

    def _update_labels(
        self,
        issue: Issue,
        labels: list[str] | None,
        priority: str | None,
    ) -> None:
        """Replace labels with the canonical, de-duplicated Planfile projection."""
        # ``_prepare_labels`` removes legacy ``priority: high`` values, emits
        # the canonical ``priority-high`` label and never mutates ``labels``.
        # The old code appended to the caller's list, so every sync rewrote the
        # local ticket with another priority label.
        self._throttle_mutation()
        issue.set_labels(*self._prepare_labels(labels, priority))

    def _update_issue_state(self, issue: Issue, status: str) -> None:
        """Update issue state using GitHub's two-state issue lifecycle.

        Planfile has richer execution statuses, so all terminal values must
        be projected explicitly before an outbound update is sent.
        """
        expected = self.project_remote_status(status)
        if expected is not None and getattr(issue, "state", None) != expected:
            self._throttle_mutation()
            issue.edit(state=expected)

    def _update_ticket(
        self,
        ticket_id: str,
        name: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
    ) -> None:
        """Update an existing GitHub issue."""
        if status and self.project_remote_status(status) is None:
            raise ValueError("sync_github_status_unsupported")
        self._clear_read_cache()
        issue = self.repo.get_issue(int(ticket_id))
        if getattr(issue, "pull_request", None) is not None:
            raise ValueError(
                f"{self.repo.full_name}#{ticket_id} is a pull request, not an issue"
            )

        # The title is set when the issue is created. Renaming it from a ticket
        # name silently shortened semcod/fixos#46 on 2026-09-16, so a rename is
        # a deliberate action on the issue, not a side effect of a sync.
        if body is not None:
            merged = self._merge_description(issue.body, body)
            markers = self._deduplication_markers(issue.body)
            missing_markers = [marker for marker in markers if marker not in merged]
            if missing_markers:
                merged = "\n".join(missing_markers) + "\n" + merged
            if merged != (issue.body or ""):
                self._throttle_mutation()
                issue.edit(body=merged)
        if labels is not None or priority:
            self._update_labels(issue, labels, priority)
        if status:
            self._update_issue_state(issue, status)
        if assignee:
            self._throttle_mutation()
            issue.edit(assignee=assignee)
        self._clear_read_cache()

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Read actual provider state, bypassing cached lifecycle observations."""
        self._clear_read_cache()
        issue = self.repo.get_issue(int(ticket_id))
        if getattr(issue, "pull_request", None) is not None:
            # GET /issues/{number} answers for a pull request number too, so a
            # caller that resolves a ticket ref through this path (readback
            # verification, recovery-after-lost-create) would otherwise accept
            # a PR as if it were the issue it just created or is updating.
            raise ValueError(
                f"{self.repo.full_name}#{ticket_id} is a pull request, not an issue"
            )

        return self._issue_to_ticket_status(issue)

    @staticmethod
    def _issue_raw_data(issue: Any) -> dict[str, Any] | None:
        """Return already-fetched raw payload without triggering PyGithub _completeIfNeeded()."""
        raw_data = getattr(issue, "_rawData", None)
        if isinstance(raw_data, dict):
            return raw_data
        if GithubObject is not None and isinstance(issue, GithubObject):
            return None
        fallback = getattr(issue, "raw_data", None)
        return fallback if isinstance(fallback, dict) else None

    @classmethod
    def _is_pull_request_issue(cls, issue: Any) -> bool:
        """Detect pull requests without triggering PyGithub lazy _completeIfNotSet fetches."""
        raw_data = cls._issue_raw_data(issue)
        if raw_data is not None:
            return bool(raw_data.get("pull_request"))
        return bool(getattr(issue, "pull_request", None))

    def _issue_to_ticket_status(self, issue: Issue) -> TicketState:
        """Convert a GitHub issue object into a TicketState."""
        raw_data = self._issue_raw_data(issue)
        state_reason = (
            raw_data.get("state_reason")
            if raw_data is not None
            else getattr(issue, "state_reason", None)
        )
        metadata = {"state_reason": state_reason}
        body = getattr(issue, "body", "") or ""
        if markers := self._deduplication_markers(body):
            metadata["deduplication_key"] = markers[0].split("=", 1)[1].rsplit("-->", 1)[0].strip()
        assignee = getattr(issue, "assignee", None)
        assignee_login = getattr(assignee, "login", None) if assignee else (assignee if isinstance(assignee, str) else None)
        raw_labels = getattr(issue, "labels", None) or []
        labels = [getattr(label, "name", str(label)) for label in raw_labels]
        updated_at = getattr(issue, "updated_at", None)
        updated_at_str = (
            updated_at.isoformat()
            if hasattr(updated_at, "isoformat")
            else (str(updated_at) if updated_at else None)
        )
        repo_name = getattr(self.repo, "full_name", None) or (getattr(self, "config", {}) or {}).get("repo", "")
        number = getattr(issue, "number", "")
        return self.build_ticket_state(
            id=str(number),
            key=f"{repo_name}#{number}",
            name=getattr(issue, "title", ""),
            description=self._description_text(body),
            url=getattr(issue, "html_url", ""),
            status=getattr(issue, "state", ""),
            assignee=assignee_login,
            labels=labels,
            updated_at=updated_at_str,
            metadata=metadata,
        )

    def list_selected_tickets(
        self, ticket_ids: set[str], labels: list[str] | None = None,
    ) -> list[TicketState]:
        """Read only resolved issue numbers, retaining exact provider bindings."""
        repository = normalize_repository(
            getattr(self, "_verified_repository", None) or self.repo.full_name
        )
        numbers = set()
        for reference in ticket_ids:
            number = str(reference).strip()
            if "#" in number:
                prefix, number = number.rsplit("#", 1)
                if prefix and normalize_repository(prefix) != repository:
                    continue
            if (number.isascii() and number.isdecimal() and int(number) > 0
                    and str(int(number)) == number):
                numbers.add(number)
        tickets = []
        for number in sorted(numbers, key=int):
            ticket = self.get_ticket(number)
            key_repository, separator, key_number = str(ticket.key or "").rpartition("#")
            url_repository, url_separator, url_number = str(ticket.url or "").removeprefix(
                "https://github.com/"
            ).rpartition("/issues/")
            if (str(ticket.id) != number
                    or not separator or key_number != number
                    or normalize_repository(key_repository) != repository
                    or not str(ticket.url or "").startswith("https://github.com/")
                    or not url_separator or url_number != number
                    or normalize_repository(url_repository) != repository):
                raise ValueError("sync_selected_provider_binding_mismatch")
            if labels and not set(labels).issubset(ticket.labels):
                continue
            tickets.append(ticket)
        return tickets

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[TicketState]:
        """List GitHub issues with filters."""
        state = "all" if not status else status.lower()
        self._quarantined_inbound_issues = []
        self._quarantined_inbound_count = 0

        # Build kwargs - only include optional params if provided
        kwargs: dict[str, Any] = {"state": state}
        if labels:
            kwargs["labels"] = labels
        if assignee:
            kwargs["assignee"] = assignee
        if since is not None:
            since_utc = (
                since.replace(tzinfo=timezone.utc)
                if since.tzinfo is None
                else since.astimezone(timezone.utc)
            )
            kwargs["since"] = since_utc

        issues = self.repo.get_issues(**kwargs)

        tickets = []
        # GitHub listing path
        for issue in issues:
            if self._is_pull_request_issue(issue) and not self.config.get(
                "include_pull_requests", False
            ):
                continue
            if limit and len(tickets) >= limit:
                break
            try:
                ticket_state = self._issue_to_ticket_status(issue)
            except ValueError as error:
                if str(error) == "sync_github_description_markers_ambiguous":
                    self._record_quarantined_inbound_issue(issue, str(error))
                    continue
                raise
            tickets.append(ticket_state)

        if self._quarantined_inbound_count:
            preview_keys = ", ".join(
                entry["key"] or entry["id"] or "<unknown>"
                for entry in self._quarantined_inbound_issues[: self.QUARANTINE_PREVIEW_LIMIT]
            )
            remaining = self._quarantined_inbound_count - min(
                len(self._quarantined_inbound_issues), self.QUARANTINE_PREVIEW_LIMIT
            )
            suffix = f" (+{remaining} more)" if remaining > 0 else ""
            console.print(
                f"[yellow]⚠️ Quarantined {self._quarantined_inbound_count} GitHub issue(s) "
                f"with ambiguous description markers ({preview_keys}{suffix})[/yellow]"
            )

        return tickets

    def _search_tickets(self, query: str) -> list[TicketState]:
        """Search GitHub issues."""
        issues = self.repo.get_issues(state="all")

        tickets = []
        # GitHub search path
        for issue in issues:
            if getattr(issue, "pull_request", None) and not self.config.get(
                "include_pull_requests", False
            ):
                continue
            if query.lower() in issue.title.lower() or query.lower() in (issue.body or "").lower():
                tickets.append(self._issue_to_ticket_status(issue))

        return tickets
