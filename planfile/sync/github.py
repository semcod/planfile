import hashlib
import json
import os
import re
import sqlite3
import time
from types import SimpleNamespace
from typing import Any
from pathlib import Path

from procache import CachedPyGithubRequester, SQLiteResponseCache

from filelock import FileLock

try:
    from github import Github
    from github.Issue import Issue
    from github.Repository import Repository
except ImportError:
    Github = None
    Issue = None
    Repository = None  # pip install PyGithub

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


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
        self.path = root / f"{hashlib.sha256(repository.encode()).hexdigest()[:24]}.sqlite3"
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

    MAX_LABEL_LENGTH = 50
    DEFAULT_MUTATION_INTERVAL = 1.0

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
        self.github = Github(self.config["token"])
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
        for label in labels or []:
            # Dedupe keys are persisted in metadata/body markers. They are not
            # GitHub labels and can exceed GitHub's 50-character limit.
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
        """Validate every outbound label before the first provider mutation."""
        for _, ticket in tickets:
            self._canonical_labels(ticket.get("labels"), ticket.get("priority"))

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
    def _merge_description(cls, existing: str | None, description: str) -> str:
        """Write the description into its own section and keep the rest.

        An issue body accumulates discussion, evidence and decisions from
        everyone; the ticket description is the local planning record.
        Replacing the body with the description deletes the former, so own a
        delimited section and leave every other line untouched.
        """
        section = f"{cls.DESCRIPTION_START}\n{description.strip()}\n{cls.DESCRIPTION_END}"
        current = existing or ""
        owned = re.compile(
            re.escape(cls.DESCRIPTION_START) + r".*?" + re.escape(cls.DESCRIPTION_END),
            re.DOTALL,
        )
        if owned.search(current):
            return owned.sub(lambda _match: section, current, count=1)
        if not current.strip():
            return section
        return f"{current.rstrip()}\n\n{section}"

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
        for issue in self.repo.get_issues(state="all"):
            if getattr(issue, "pull_request", None):
                continue
            if any(marker in (issue.body or "") for marker in markers):
                return self._cache_marker_result(markers, issue)
        self._cache_marker_result(markers, None)
        return None

    def _cache_marker_result(self, markers: list[str], issue):
        """Cache one marker lookup, including a short-lived negative result."""
        cache_key = json.dumps(sorted(markers), separators=(",", ":"))
        if issue is None:
            self._cache().put("markers", cache_key, None, ttl=60)
        else:
            self._cache().put(
                "markers",
                cache_key,
                {
                    "number": issue.number,
                    "html_url": issue.html_url,
                    "state": issue.state,
                },
            )
        return issue

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
        issue_labels = self._prepare_labels(labels, priority)
        body = self._build_metadata_body(body, metadata)
        existing = self._find_issue_by_markers(self._deduplication_markers(body))
        if existing is not None:
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
            "labels": issue_labels,
        }
        if assignee:
            create_kwargs["assignee"] = assignee

        self._throttle_mutation()
        issue: Issue = self.repo.create_issue(**create_kwargs)
        self._clear_read_cache()

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
        status_lower = status.lower()
        # Planfile uses ``done``/``completed`` (and cancellation variants) for
        # terminal tickets, while GitHub only exposes open/closed issue state.
        # Projecting every terminal status here keeps outbound lifecycle sync
        # fail-closed and prevents completed local tickets from remaining open
        # forever on GitHub.
        if status_lower in {
            "closed",
            "done",
            "completed",
            "blocked",
            "failed",
            "canceled",
            "cancelled",
        }:
            self._throttle_mutation()
            issue.edit(state="closed")
        elif status_lower in {"open", "triage", "in_progress", "in-progress"}:
            self._throttle_mutation()
            issue.edit(state="open")

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
        issue = self.repo.get_issue(int(ticket_id))

        # The title is set when the issue is created. Renaming it from a ticket
        # name silently shortened semcod/fixos#46 on 2026-09-16, so a rename is
        # a deliberate action on the issue, not a side effect of a sync.
        if body:
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
        """Get GitHub issue status."""
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

    def _issue_to_ticket_status(self, issue: Issue) -> TicketState:
        """Convert a GitHub issue object into a TicketState."""
        return self.build_ticket_state(
            id=str(issue.number),
            key=f"{self.repo.full_name}#{issue.number}",
            name=issue.title,
            description=issue.body or "",
            url=issue.html_url,
            status=issue.state,
            assignee=issue.assignee.login if issue.assignee else None,
            labels=[label.name for label in issue.labels],
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
            metadata={"deduplication_key": markers[0].split("=", 1)[1].rsplit("-->", 1)[0].strip()}
            if (markers := self._deduplication_markers(issue.body))
            else {},
        )

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketState]:
        """List GitHub issues with filters."""
        state = "all" if not status else status.lower()

        # Build kwargs - only include optional params if provided
        kwargs = {"state": state}
        if labels:
            kwargs["labels"] = labels
        if assignee:
            kwargs["assignee"] = assignee

        issues = self.repo.get_issues(**kwargs)

        tickets = []
        # GitHub listing path
        for issue in issues:
            if getattr(issue, "pull_request", None) and not self.config.get(
                "include_pull_requests", False
            ):
                continue
            if limit and len(tickets) >= limit:
                break
            tickets.append(self._issue_to_ticket_status(issue))

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
