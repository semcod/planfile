"""Reconcile Planfile ``in_progress`` status with live leases, worktrees, and merge receipts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import types
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from planfile.contracts import (
    RECONCILE_MERGE_EVIDENCE_SCHEMA,
    RECONCILE_REPORT_SCHEMA,
)
from planfile.core.models import Ticket, TicketExecution

if TYPE_CHECKING:
    from planfile import Planfile

TERMINAL_LEASE_PHASES: frozenset[str] = frozenset(
    {"merged", "closed", "cancelled", "canceled", "expired", "released"}
)
_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")
_NATIVE_TICKET_RE = re.compile(r"\bticket-(\d{3,})\b", re.IGNORECASE)
_PLANFILE_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")
_GITHUB_URL_SLUG_RE = re.compile(
    r"github\.com[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git|/|$)",
    re.IGNORECASE,
)
_GITHUB_ISSUE_REF_RE = re.compile(
    r"(?:issue|github|closes|fixes|refs)?[\s:#]*#(\d+)\b",
    re.IGNORECASE,
)
_RECEIPT_PR_RE = re.compile(
    r"(?:pr[-:]?|/pull/|:)(\d+)(?:/merged)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LiveLeaseInfo:
    """Active, non-expired ``.subactor/leases/*.json`` writer lease."""

    lease_id: str
    ticket_id: str
    worktree_id: str
    branch_ref: str
    owner_actor: str
    owner_session: str
    phase: str
    expires_at: str
    tokens: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class WorktreeInfo:
    """Observed linked Git worktree in a target repository."""

    path: Path
    worktree_id: str
    branch: str
    head_sha: str
    ticket_id: str | None
    dirty: bool
    ahead: int
    observation_failed: bool = False
    tokens: frozenset[str] = field(default_factory=frozenset)

    @property
    def active(self) -> bool:
        return self.dirty or self.ahead > 0


@dataclass(frozen=True)
class TerminalReceiptEntry:
    """Raw ``merged`` entry from ``.git/new-project/terminal-receipts.json``."""

    ticket_id: str
    receipt_ref: str
    terminal_sha: str
    head_sha: str
    target_branch: str
    pull_request: int | None = None
    planfile_ticket_id: str | None = None


@dataclass(frozen=True)
class VerifiedMergeEvidence:
    """Git-ancestry-verified merge evidence for closing an ``in_progress`` ticket."""

    terminal_receipt_ref: str
    terminal_sha: str
    head_sha: str | None
    target_branch: str
    native_ticket_id: str | None = None


@dataclass
class TargetRepoObservation:
    """Cached local Git, lease, worktree, and receipt snapshot for one target repository."""

    repo_dir: Path
    observable: bool
    error: str | None = None
    primary_checkout: Path | None = None
    git_common_dir: Path | None = None
    repository_slug: str | None = None
    target_branch: str = "main"
    target_ref: str | None = None
    live_leases: list[LiveLeaseInfo] = field(default_factory=list)
    worktrees: list[WorktreeInfo] = field(default_factory=list)
    merged_receipts: list[TerminalReceiptEntry] = field(default_factory=list)
    planfile_to_native: dict[str, set[str]] = field(default_factory=dict)
    issue_to_native: dict[int, set[str]] = field(default_factory=dict)
    unmerged_ticket_nums: set[str] = field(default_factory=set)
    corrupt_lease_files: list[str] = field(default_factory=list)
    receipt_registry_corrupt: bool = False
    _ancestry_cache: dict[tuple[str, str], bool] = field(default_factory=dict)


def _utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(
    cwd: Path,
    *args: str,
    timeout: float = 5.0,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            check=False,
            env=_git_env(),
            timeout=timeout,
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _parse_origin_slug(url: str) -> str | None:
    cleaned = url.strip()
    if not cleaned:
        return None
    match = _GITHUB_URL_SLUG_RE.search(cleaned)
    if match:
        return match.group(1).removesuffix(".git").lower()
    parts = [p for p in cleaned.removesuffix(".git").rstrip("/").split("/") if p]
    if len(parts) >= 2 and ":" in parts[-2]:
        owner = parts[-2].split(":")[-1]
        return f"{owner}/{parts[-1]}".lower()
    if len(parts) >= 2 and all(part not in {".", ".."} for part in parts[-2:]):
        return f"{parts[-2]}/{parts[-1]}".lower()
    return None


def _normalize_native_ticket(raw: str) -> str | None:
    match = _NATIVE_TICKET_RE.search(raw)
    if not match:
        return None
    return f"ticket-{int(match.group(1)):03d}"


def _extract_tokens(*texts: Any) -> frozenset[str]:
    markers: set[str] = set()
    for item in texts:
        if not isinstance(item, str) or not item:
            continue
        lowered = item.lower()
        markers.add(lowered)
        for pf_match in _PLANFILE_ID_RE.finditer(item.upper()):
            markers.add(pf_match.group(1).lower())
        for native_match in _NATIVE_TICKET_RE.finditer(lowered):
            markers.add(f"ticket-{int(native_match.group(1)):03d}")
    return frozenset(markers)


def _determine_target_branch_and_ref(primary: Path) -> tuple[str, str | None]:
    target_branch = "main"
    manifest_path = primary / ".governance" / "manifest.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            branches = (manifest.get("delivery") or {}).get("targetBranches")
            if isinstance(branches, list) and branches and isinstance(branches[0], str):
                target_branch = branches[0].strip() or "main"
        except (OSError, json.JSONDecodeError):
            pass

    candidates = [
        f"refs/remotes/origin/{target_branch}",
        f"refs/heads/{target_branch}",
    ]
    if target_branch == "main":
        candidates.extend(["refs/remotes/origin/master", "refs/heads/master"])
    for ref in candidates:
        rc, out = _run_git(primary, "rev-parse", "--verify", f"{ref}^{{commit}}")
        if rc == 0 and out.strip():
            resolved_branch = ref.rsplit("/", 1)[-1]
            return resolved_branch, ref
    rc, out = _run_git(primary, "rev-parse", "--verify", "HEAD^{commit}")
    if rc == 0 and out.strip():
        return target_branch, out.strip()
    return target_branch, None


def _index_native_ticket_links(
    checkout_root: Path,
    planfile_to_native: dict[str, set[str]],
    issue_to_native: dict[int, set[str]],
) -> set[str]:
    found_tokens: set[str] = set()
    project_dir = checkout_root / "project"
    if not project_dir.is_dir() or project_dir.is_symlink():
        return found_tokens
    try:
        entries = sorted(project_dir.iterdir())
    except OSError:
        return found_tokens
    for entry in entries:
        if not entry.is_dir() or entry.is_symlink():
            continue
        native_id = _normalize_native_ticket(entry.name)
        if not native_id:
            continue
        readme = entry / "README.md"
        if not readme.is_file() or readme.is_symlink():
            continue
        try:
            text = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pf_match in _PLANFILE_ID_RE.finditer(text):
            pf_id = pf_match.group(1).upper()
            planfile_to_native.setdefault(pf_id, set()).add(native_id)
            found_tokens.add(pf_id.lower())
        for issue_match in _GITHUB_ISSUE_REF_RE.finditer(text):
            try:
                issue_num = int(issue_match.group(1))
            except ValueError:
                continue
            issue_to_native.setdefault(issue_num, set()).add(native_id)
    return found_tokens


def _scan_leases(primary: Path, now: datetime, obs: TargetRepoObservation) -> None:
    subactor_dir = primary / ".subactor"
    leases_dir = subactor_dir / "leases"
    if subactor_dir.is_symlink() or leases_dir.is_symlink():
        obs.observable = False
        obs.error = "lease_directory_symlink"
        return
    if not leases_dir.exists():
        return
    if not leases_dir.is_dir():
        obs.observable = False
        obs.error = "lease_directory_invalid"
        return
    try:
        lease_files = sorted(leases_dir.glob("*.json"))
    except OSError:
        obs.observable = False
        obs.error = "lease_directory_unreadable"
        return

    for lease_file in lease_files:
        if lease_file.is_symlink():
            obs.corrupt_lease_files.append(lease_file.name)
            continue
        try:
            payload = json.loads(lease_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            obs.corrupt_lease_files.append(lease_file.name)
            continue
        if not isinstance(payload, dict):
            obs.corrupt_lease_files.append(lease_file.name)
            continue
        phase = str(
            payload.get("phase") or payload.get("status") or payload.get("state") or ""
        ).strip().lower()
        if phase in TERMINAL_LEASE_PHASES:
            continue
        if payload.get("releasedAt") not in (None, ""):
            continue
        expires_raw = payload.get("expiresAt")
        expires_dt = _parse_iso_datetime(expires_raw)
        if expires_dt is None:
            obs.corrupt_lease_files.append(lease_file.name)
            continue
        if expires_dt <= now:
            continue

        raw_ticket = str(payload.get("ticketId") or payload.get("ticket") or "").strip()
        norm_native = _normalize_native_ticket(raw_ticket)
        ticket_id = norm_native or raw_ticket
        lease_id = str(payload.get("leaseId") or lease_file.stem).strip()
        worktree_id = str(payload.get("worktreeId") or lease_file.stem).strip()
        branch_ref = str(payload.get("branchRef") or "").strip()
        owner_actor = str(payload.get("ownerActor") or "").strip()
        owner_session = str(payload.get("ownerSession") or "").strip()
        tokens = _extract_tokens(
            ticket_id,
            raw_ticket,
            lease_id,
            worktree_id,
            branch_ref,
            owner_session,
            lease_file.stem,
        )
        obs.live_leases.append(
            LiveLeaseInfo(
                lease_id=lease_id,
                ticket_id=ticket_id,
                worktree_id=worktree_id,
                branch_ref=branch_ref,
                owner_actor=owner_actor,
                owner_session=owner_session,
                phase=phase or "claimed",
                expires_at=str(expires_raw),
                tokens=tokens,
            )
        )


def _parse_worktree_porcelain(raw: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for chunk in raw.split("\0"):
        if not chunk:
            if "worktree" in current:
                records.append(current)
                current = {}
            continue
        if " " in chunk:
            key, val = chunk.split(" ", 1)
            current[key] = val
        else:
            current[chunk] = "true"
    if "worktree" in current:
        records.append(current)
    return records


def _scan_worktrees(primary: Path, obs: TargetRepoObservation) -> None:
    rc, raw = _run_git(primary, "worktree", "list", "--porcelain", "-z")
    if rc != 0:
        obs.observable = False
        obs.error = "worktree_list_failed"
        return
    records = _parse_worktree_porcelain(raw)
    for idx, entry in enumerate(records):
        wt_raw = entry.get("worktree", "")
        if not wt_raw or idx == 0:
            continue
        wt_path = Path(wt_raw)
        branch_ref = entry.get("branch", "")
        branch_short = branch_ref.removeprefix("refs/heads/")
        head_sha = entry.get("HEAD", "")
        worktree_id = wt_path.name
        native_ticket = (
            _normalize_native_ticket(worktree_id)
            or _normalize_native_ticket(branch_short)
        )
        readme_tokens: set[str] = set()
        dirty = False
        ahead = 0
        obs_failed = False

        if wt_path.is_symlink():
            obs_failed = True
        elif wt_path.is_dir():
            readme_tokens = _index_native_ticket_links(
                wt_path,
                obs.planfile_to_native,
                obs.issue_to_native,
            )
            st_rc, st_out = _run_git(
                wt_path,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            )
            if st_rc != 0:
                obs_failed = True
            else:
                dirty = bool(st_out.strip())
            if obs.target_ref and head_sha:
                av_rc, av_out = _run_git(
                    primary,
                    "rev-list",
                    "--count",
                    f"{obs.target_ref}..{head_sha}",
                )
                if av_rc == 0 and av_out.strip().isdigit():
                    ahead = int(av_out.strip())
                elif av_rc != 0:
                    obs_failed = True

        base_tokens = set(
            _extract_tokens(worktree_id, branch_short, native_ticket or "")
        )
        base_tokens.update(readme_tokens)
        obs.worktrees.append(
            WorktreeInfo(
                path=wt_path,
                worktree_id=worktree_id,
                branch=branch_short,
                head_sha=head_sha,
                ticket_id=native_ticket,
                dirty=dirty,
                ahead=ahead,
                observation_failed=obs_failed,
                tokens=frozenset(base_tokens),
            )
        )


def _scan_unmerged_ticket_branches(primary: Path, obs: TargetRepoObservation) -> None:
    if not obs.target_ref:
        return
    rc, out = _run_git(
        primary,
        "for-each-ref",
        "--format=%(refname:short)\t%(objectname)",
        "refs/heads/ticket",
        "refs/heads/ticket-*",
    )
    if rc != 0:
        return
    for line in out.splitlines():
        if "\t" not in line:
            continue
        branch_name, sha = line.split("\t", 1)
        native = _normalize_native_ticket(branch_name)
        if not native or not sha:
            continue
        if not _is_git_ancestor(obs, sha.strip(), obs.target_ref):
            obs.unmerged_ticket_nums.add(native)


def _scan_terminal_receipts(git_common_dir: Path, obs: TargetRepoObservation) -> None:
    receipts_path = git_common_dir / "new-project" / "terminal-receipts.json"
    if receipts_path.is_symlink():
        obs.receipt_registry_corrupt = True
        return
    if not receipts_path.exists():
        return
    try:
        payload = json.loads(receipts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obs.receipt_registry_corrupt = True
        return
    if not isinstance(payload, dict):
        obs.receipt_registry_corrupt = True
        return
    items = payload.get("receipts")
    if not isinstance(items, list):
        obs.receipt_registry_corrupt = True
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("outcome") or "").strip().lower() != "merged":
            continue
        raw_ticket = str(item.get("ticketId") or item.get("ticket") or "").strip()
        terminal_sha = str(item.get("terminalSha") or "").strip()
        head_sha = str(item.get("headSha") or "").strip()
        receipt_ref = str(item.get("receiptRef") or "").strip()
        target_branch = str(item.get("targetBranch") or obs.target_branch).strip()
        if not raw_ticket or not _GIT_SHA_RE.fullmatch(terminal_sha):
            continue
        norm_ticket = _normalize_native_ticket(raw_ticket) or raw_ticket
        pr_num: int | None = None
        if isinstance(item.get("pullRequest"), int):
            pr_num = int(item["pullRequest"])
        elif receipt_ref:
            pr_match = _RECEIPT_PR_RE.search(receipt_ref)
            if pr_match:
                pr_num = int(pr_match.group(1))
        pf_ticket = str(
            item.get("planfileTicketId") or item.get("planfileTicket") or ""
        ).strip() or None
        obs.merged_receipts.append(
            TerminalReceiptEntry(
                ticket_id=norm_ticket,
                receipt_ref=receipt_ref or f"receipt:terminal-sha:{terminal_sha}",
                terminal_sha=terminal_sha,
                head_sha=head_sha,
                target_branch=target_branch,
                pull_request=pr_num,
                planfile_ticket_id=pf_ticket,
            )
        )


def _is_git_ancestor(obs: TargetRepoObservation, ancestor_sha: str, target_ref: str) -> bool:
    if obs.primary_checkout is None or not _GIT_SHA_RE.fullmatch(ancestor_sha):
        return False
    cache_key = (ancestor_sha.lower(), target_ref)
    cached = obs._ancestry_cache.get(cache_key)
    if cached is not None:
        return cached
    rc, _ = _run_git(
        obs.primary_checkout,
        "merge-base",
        "--is-ancestor",
        ancestor_sha,
        target_ref,
    )
    result = rc == 0
    obs._ancestry_cache[cache_key] = result
    return result


def observe_target_repository(
    repo_dir: str | Path,
    *,
    now: datetime | None = None,
) -> TargetRepoObservation:
    """Inspect a local Git checkout for leases, worktrees, and merge receipts."""

    current_time = _utc_now(now)
    candidate = Path(repo_dir)
    if candidate.is_symlink():
        return TargetRepoObservation(
            repo_dir=candidate,
            observable=False,
            error="target_repository_symlink",
        )
    if not candidate.exists() or not candidate.is_dir():
        return TargetRepoObservation(
            repo_dir=candidate,
            observable=False,
            error="target_repository_missing",
        )
    resolved = candidate.resolve()
    git_marker = resolved / ".git"
    if git_marker.is_symlink() or not git_marker.exists():
        return TargetRepoObservation(
            repo_dir=resolved,
            observable=False,
            error="target_repository_not_git",
        )
    rc_common, raw_common = _run_git(
        resolved,
        "rev-parse",
        "--path-format=absolute",
        "--git-common-dir",
    )
    if rc_common != 0 or not raw_common.strip():
        return TargetRepoObservation(
            repo_dir=resolved,
            observable=False,
            error="target_repository_not_git",
        )
    git_common_dir = Path(raw_common.strip()).resolve()
    rc_wt, raw_wt = _run_git(resolved, "worktree", "list", "--porcelain", "-z")
    if rc_wt != 0 or not raw_wt:
        return TargetRepoObservation(
            repo_dir=resolved,
            observable=False,
            error="worktree_list_failed",
        )
    wt_records = _parse_worktree_porcelain(raw_wt)
    if not wt_records or not wt_records[0].get("worktree"):
        return TargetRepoObservation(
            repo_dir=resolved,
            observable=False,
            error="primary_checkout_unavailable",
        )
    primary = Path(wt_records[0]["worktree"])
    if primary.is_symlink() or not primary.is_dir():
        return TargetRepoObservation(
            repo_dir=resolved,
            observable=False,
            error="primary_checkout_symlink_or_missing",
        )
    primary = primary.resolve()

    rc_origin, origin_url = _run_git(primary, "config", "--get", "remote.origin.url")
    repo_slug = _parse_origin_slug(origin_url) if rc_origin == 0 else None
    target_branch, target_ref = _determine_target_branch_and_ref(primary)

    obs = TargetRepoObservation(
        repo_dir=resolved,
        observable=True,
        primary_checkout=primary,
        git_common_dir=git_common_dir,
        repository_slug=repo_slug,
        target_branch=target_branch,
        target_ref=target_ref,
    )
    _index_native_ticket_links(primary, obs.planfile_to_native, obs.issue_to_native)
    _scan_leases(primary, current_time, obs)
    if not obs.observable:
        return obs
    _scan_worktrees(primary, obs)
    if not obs.observable:
        return obs
    _scan_unmerged_ticket_branches(primary, obs)
    _scan_terminal_receipts(git_common_dir, obs)
    return obs


def discover_planfile_repositories(
    workspace_root: str | Path,
    *,
    max_depth: int = 2,
) -> list[Path]:
    """Discover non-symlinked local repositories containing a ``.planfile`` directory."""

    root = Path(workspace_root)
    if root.is_symlink() or not root.is_dir():
        return []
    found: list[Path] = []
    queue: list[tuple[Path, int]] = [(root.resolve(), 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth > 0:
            pf_dir = current / ".planfile"
            if pf_dir.is_dir() and not pf_dir.is_symlink():
                found.append(current)
                continue
        if depth < max_depth:
            try:
                children = sorted(current.iterdir())
            except OSError:
                continue
            for entry in children:
                if entry.name.startswith(".") or entry.is_symlink():
                    continue
                if entry.is_dir():
                    queue.append((entry, depth + 1))
    return found


def _ticket_dict_view(ticket: Ticket | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(ticket, Ticket):
        return ticket.model_dump(mode="python", exclude_none=False)
    return dict(ticket)


def _extract_repo_hints(data: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Return ``(explicit_repo_path, explicit_repo_slug)`` declared on a ticket."""

    path_keys = ("repo_path", "target_repo_path", "project_dir", "repository_path")
    slug_keys = ("repository", "repo", "target_repository")

    containers: list[Mapping[str, Any]] = []
    source = data.get("source")
    if isinstance(source, Mapping) and isinstance(source.get("context"), Mapping):
        containers.append(source["context"])
    inputs = data.get("inputs")
    if isinstance(inputs, Mapping) and isinstance(inputs.get("process_manifest"), Mapping):
        containers.append(inputs["process_manifest"])
    outputs = data.get("outputs")
    if isinstance(outputs, Mapping) and isinstance(outputs.get("result"), Mapping):
        containers.append(outputs["result"])

    for container in containers:
        for key in path_keys:
            val = container.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip(), None
    for container in containers:
        for key in slug_keys:
            val = container.get(key)
            if isinstance(val, str) and "/" in val and not val.startswith("/"):
                slug = _parse_origin_slug(val) or val.strip().lower()
                return None, slug

    sync = data.get("sync")
    if isinstance(sync, Mapping):
        gh = sync.get("github")
        if isinstance(gh, Mapping):
            for key in ("repo", "repository"):
                val = gh.get(key)
                if isinstance(val, str) and "/" in val:
                    return None, val.strip().lower()
            url = gh.get("url") or gh.get("html_url")
            if isinstance(url, str):
                url_slug = _parse_origin_slug(url)
                if url_slug:
                    return None, url_slug

    for raw_label in data.get("labels") or []:
        label = str(raw_label).strip()
        lower = label.lower()
        if lower.startswith(("repo:", "repository:")):
             candidate_slug = label.split(":", 1)[1].strip().lower()
             if "/" in candidate_slug:
                 return None, candidate_slug
    return None, None


def resolve_ticket_target_repo(
    ticket: Ticket | Mapping[str, Any],
    *,
    default_repo_dir: Path | None,
    workspace_root: Path | None = None,
    now: datetime | None = None,
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
    slug_index: Mapping[str, Path] | None = None,
) -> tuple[TargetRepoObservation | None, str | None]:
    """Resolve and observe the target repository checkout for ``ticket``.

    Returns ``(observation, unobserved_reason)``. When ``unobserved_reason`` is
    not ``None``, callers MUST treat the target repository as locally unobserved
    and preserve existing ``in_progress`` state rather than guessing.
    """

    cache = observations if observations is not None else {}

    def _observe(path: Path) -> TargetRepoObservation:
        key = path if path.is_symlink() else (path.resolve() if path.exists() else path)
        if key not in cache:
            cache[key] = observe_target_repository(path, now=now)
        return cache[key]

    data = _ticket_dict_view(ticket)
    explicit_path, explicit_slug = _extract_repo_hints(data)

    if explicit_path is not None:
        obs = _observe(Path(explicit_path))
        if not obs.observable:
            return obs, obs.error or "target_repository_unobserved"
        return obs, None

    default_obs = _observe(default_repo_dir) if default_repo_dir is not None else None

    if explicit_slug is not None:
        if (
            default_obs is not None
            and default_obs.observable
            and default_obs.repository_slug == explicit_slug
        ):
            return default_obs, None
        if slug_index and explicit_slug in slug_index:
            indexed_obs = _observe(slug_index[explicit_slug])
            if indexed_obs.observable:
                return indexed_obs, None
        if workspace_root is not None and not workspace_root.is_symlink():
            parts = explicit_slug.split("/", 1)
            candidates = (
                [workspace_root / parts[0] / parts[1], workspace_root / parts[1]]
                if len(parts) == 2
                else [workspace_root / explicit_slug]
            )
            for candidate in candidates:
                cand_obs = _observe(candidate)
                if cand_obs.observable and (
                    cand_obs.repository_slug in {None, explicit_slug}
                ):
                    return cand_obs, None
        return None, f"target_repository_unobserved:{explicit_slug}"

    if default_obs is None:
        return None, "target_repository_unspecified"
    if not default_obs.observable:
        return default_obs, default_obs.error or "target_repository_unobserved"
    return default_obs, None


@dataclass(frozen=True)
class TicketRepoBindings:
    """Extracted identity links between a Planfile ticket and a target repository."""

    ticket_id: str
    assigned_to: str | None
    native_tickets: frozenset[str]
    pr_numbers: frozenset[int]
    direct_merge_candidates: tuple[tuple[str, str], ...]


def _extract_ticket_bindings(
    ticket: Ticket | Mapping[str, Any],
    obs: TargetRepoObservation,
) -> TicketRepoBindings:
    data = _ticket_dict_view(ticket)
    ticket_id = str(data.get("id") or "").strip()
    execution = data.get("execution") if isinstance(data.get("execution"), Mapping) else {}
    assigned_raw = execution.get("assigned_to") if isinstance(execution, Mapping) else None
    assigned_to = str(assigned_raw).strip() if assigned_raw else None

    native_tickets: set[str] = set()
    pr_numbers: set[int] = set()
    direct_merges: list[tuple[str, str]] = []

    if ticket_id.upper() in obs.planfile_to_native:
        native_tickets.update(obs.planfile_to_native[ticket_id.upper()])
    norm_self = _normalize_native_ticket(ticket_id)
    if norm_self:
        native_tickets.add(norm_self)
    if assigned_to:
        norm_assigned = _normalize_native_ticket(assigned_to)
        if norm_assigned:
            native_tickets.add(norm_assigned)

    for raw_label in data.get("labels") or []:
        norm_lbl = _normalize_native_ticket(str(raw_label))
        if norm_lbl:
            native_tickets.add(norm_lbl)

    source = data.get("source")
    if isinstance(source, Mapping) and isinstance(source.get("context"), Mapping):
        for val in source["context"].values():
            if isinstance(val, str):
                norm = _normalize_native_ticket(val)
                if norm:
                    native_tickets.add(norm)

    sync = data.get("sync")
    if isinstance(sync, Mapping):
        gh = sync.get("github")
        if isinstance(gh, Mapping):
            issue_num = gh.get("issue_number") or gh.get("number")
            if isinstance(issue_num, int) and issue_num in obs.issue_to_native:
                native_tickets.update(obs.issue_to_native[issue_num])
            for pr_key in ("pr_number", "pull_request"):
                pr_val = gh.get(pr_key)
                if isinstance(pr_val, int) and pr_val > 0:
                    pr_numbers.add(pr_val)
            merge_sha = str(gh.get("merge_commit_sha") or "").strip()
            if gh.get("merged") is True and _GIT_SHA_RE.fullmatch(merge_sha):
                direct_merges.append((merge_sha, f"receipt:github-merge:{merge_sha}"))

    outputs = data.get("outputs")
    if isinstance(outputs, Mapping):
        for sub_key in ("completion_receipt", "result"):
            sub = outputs.get(sub_key)
            if not isinstance(sub, Mapping):
                continue
            for t_key in ("nativeTicketId", "native_ticket", "ticket", "ticketId"):
                t_val = sub.get(t_key)
                if isinstance(t_val, str):
                    norm_t = _normalize_native_ticket(t_val)
                    if norm_t:
                        native_tickets.add(norm_t)
            pr_val = sub.get("pullRequest") or sub.get("pr_number")
            if isinstance(pr_val, int) and pr_val > 0:
                pr_numbers.add(pr_val)
            term_sha = str(
                sub.get("terminalSha") or sub.get("merge_commit_sha") or ""
            ).strip()
            outcome = str(sub.get("outcome") or "").strip().lower()
            if (outcome == "merged" or sub.get("merged") is True) and _GIT_SHA_RE.fullmatch(
                term_sha
            ):
                ref = str(
                    sub.get("terminalReceiptRef")
                    or sub.get("receiptRef")
                    or f"receipt:completion:{term_sha}"
                ).strip()
                direct_merges.append((term_sha, ref))

    return TicketRepoBindings(
        ticket_id=ticket_id,
        assigned_to=assigned_to,
        native_tickets=frozenset(native_tickets),
        pr_numbers=frozenset(pr_numbers),
        direct_merge_candidates=tuple(direct_merges),
    )


def find_verified_merge_evidence(
    ticket: Ticket | Mapping[str, Any],
    obs: TargetRepoObservation,
) -> VerifiedMergeEvidence | None:
    """Return Git-ancestry-verified merge evidence for ``ticket``, if any."""

    if not obs.observable or not obs.target_ref or obs.primary_checkout is None:
        return None
    bindings = _extract_ticket_bindings(ticket, obs)

    for receipt in reversed(obs.merged_receipts):
        matched = (
            receipt.ticket_id == bindings.ticket_id
            or receipt.ticket_id in bindings.native_tickets
            or (
                receipt.planfile_ticket_id is not None
                and receipt.planfile_ticket_id.upper() == bindings.ticket_id.upper()
            )
            or (
                receipt.pull_request is not None
                and receipt.pull_request in bindings.pr_numbers
            )
        )
        if not matched:
            continue
        if receipt.ticket_id in obs.unmerged_ticket_nums:
            continue
        if _is_git_ancestor(obs, receipt.terminal_sha, obs.target_ref):
            return VerifiedMergeEvidence(
                terminal_receipt_ref=receipt.receipt_ref,
                terminal_sha=receipt.terminal_sha,
                head_sha=receipt.head_sha or None,
                target_branch=receipt.target_branch or obs.target_branch,
                native_ticket_id=(
                    receipt.ticket_id if receipt.ticket_id.startswith("ticket-") else None
                ),
            )

    for cand_sha, cand_ref in bindings.direct_merge_candidates:
        if _is_git_ancestor(obs, cand_sha, obs.target_ref):
            return VerifiedMergeEvidence(
                terminal_receipt_ref=cand_ref,
                terminal_sha=cand_sha,
                head_sha=None,
                target_branch=obs.target_branch,
                native_ticket_id=next(iter(sorted(bindings.native_tickets)), None),
            )

    for native_id in sorted(bindings.native_tickets):
        if native_id in obs.unmerged_ticket_nums:
            continue
        has_active_wt = any(
            wt.ticket_id == native_id and wt.active for wt in obs.worktrees
        )
        if has_active_wt:
            continue
        cat_rc, _ = _run_git(
            obs.primary_checkout,
            "cat-file",
            "-e",
            f"{obs.target_ref}:project/{native_id}/README.md",
        )
        if cat_rc != 0:
            continue
        log_rc, log_out = _run_git(
            obs.primary_checkout,
            "log",
            "-n",
            "1",
            "--format=%H",
            obs.target_ref,
            "--",
            f"project/{native_id}",
        )
        landed_sha = log_out.strip()
        if log_rc == 0 and _GIT_SHA_RE.fullmatch(landed_sha):
            return VerifiedMergeEvidence(
                terminal_receipt_ref=f"receipt:git-landed:{native_id}:{landed_sha}",
                terminal_sha=landed_sha,
                head_sha=None,
                target_branch=obs.target_branch,
                native_ticket_id=native_id,
            )

    return None


@dataclass(frozen=True)
class LiveBindingStatus:
    """Live lease, active worktree, or ambiguous observation result for a ticket."""

    is_live: bool
    ambiguous_error: str | None = None
    reason: str = ""
    lease_id: str | None = None
    worktree_id: str | None = None


def find_live_ticket_binding(
    ticket: Ticket | Mapping[str, Any],
    obs: TargetRepoObservation,
    *,
    now: datetime | None = None,
) -> LiveBindingStatus:
    """Check whether ``ticket`` is bound to a live non-expired lease or active worktree."""

    current_time = _utc_now(now)
    data = _ticket_dict_view(ticket)
    bindings = _extract_ticket_bindings(ticket, obs)
    ticket_key = bindings.ticket_id.lower()

    if obs.corrupt_lease_files:
        for corrupt_name in obs.corrupt_lease_files:
            corrupt_markers = _extract_tokens(corrupt_name)
            if (
                (ticket_key and ticket_key in corrupt_markers)
                or bool(bindings.native_tickets & corrupt_markers)
                or (
                    bindings.assigned_to is not None
                    and bindings.assigned_to.lower() in corrupt_markers
                )
            ):
                return LiveBindingStatus(
                    is_live=False,
                    ambiguous_error=f"corrupt_lease_file:{corrupt_name}",
                )

    for wt in obs.worktrees:
        wt_matches = (
            (wt.ticket_id is not None and wt.ticket_id == bindings.ticket_id)
            or (wt.ticket_id is not None and wt.ticket_id in bindings.native_tickets)
            or (ticket_key and ticket_key in wt.tokens)
            or (bindings.assigned_to is not None and bindings.assigned_to == wt.worktree_id)
        )
        if wt_matches and wt.observation_failed:
            return LiveBindingStatus(
                is_live=False,
                ambiguous_error=f"worktree_observation_failed:{wt.worktree_id}",
            )

    for lease in obs.live_leases:
        lease_matches = (
            lease.ticket_id == bindings.ticket_id
            or lease.ticket_id in bindings.native_tickets
            or (ticket_key and ticket_key in lease.tokens)
            or (
                bindings.assigned_to is not None
                and bindings.assigned_to
                in {lease.lease_id, lease.worktree_id, lease.owner_session}
            )
        )
        if lease_matches:
            return LiveBindingStatus(
                is_live=True,
                reason=f"active_lease:{lease.lease_id}",
                lease_id=lease.lease_id,
                worktree_id=lease.worktree_id,
            )

    for wt in obs.worktrees:
        wt_matches = (
            (wt.ticket_id is not None and wt.ticket_id == bindings.ticket_id)
            or (wt.ticket_id is not None and wt.ticket_id in bindings.native_tickets)
            or (ticket_key and ticket_key in wt.tokens)
            or (bindings.assigned_to is not None and bindings.assigned_to == wt.worktree_id)
        )
        if wt_matches and wt.active:
            return LiveBindingStatus(
                is_live=True,
                reason=f"active_worktree:{wt.worktree_id}",
                worktree_id=wt.worktree_id,
            )

    execution = data.get("execution")
    if isinstance(execution, Mapping):
        lease_exp = _parse_iso_datetime(execution.get("lease_expires_at"))
        if lease_exp is not None and lease_exp > current_time:
            return LiveBindingStatus(
                is_live=True,
                reason=f"active_lease:planfile:{bindings.ticket_id}",
                lease_id=f"planfile:{bindings.ticket_id}",
            )

    return LiveBindingStatus(is_live=False)


def iter_sprint_tickets(pf: Planfile, sprint: str = "active") -> list[Ticket]:
    """Return deduplicated tickets for ``sprint`` (``'active'`` excludes ``history-*``/``archive-*``)."""

    if sprint == "active":
        sprint_ids = [
            sid
            for sid in pf.store._all_sprint_ids()
            if not sid.startswith(("history-", "archive-"))
        ]
        if "current" in sprint_ids:
            sprint_ids = ["current", *[s for s in sprint_ids if s != "current"]]
        history_locs = pf.store._history_locations()
        seen: set[str] = set()
        collected: list[Ticket] = []
        for sid in sprint_ids:
            for ticket in pf.list_tickets(sprint=sid):
                if ticket.id in seen:
                    continue
                if history_locs.get(ticket.id) not in {None, sid}:
                    continue
                seen.add(ticket.id)
                collected.append(ticket)
        return collected
    return pf.list_tickets(sprint=sprint)


def _apply_merge_transition(
    pf: Planfile,
    ticket: Ticket,
    evidence: VerifiedMergeEvidence,
    *,
    now_iso: str,
    actor: str,
) -> tuple[bool, str]:
    from planfile.core.store import (
        ImmutableTerminalReopenError,
        TicketUpdatedAtConflictError,
    )

    expected_updated_at = (
        ticket.updated_at.isoformat()
        if isinstance(ticket.updated_at, datetime)
        else str(ticket.updated_at)
    )
    receipt_payload: dict[str, Any] = {
        "schema": RECONCILE_MERGE_EVIDENCE_SCHEMA,
        "outcome": "merged",
        "terminalReceiptRef": evidence.terminal_receipt_ref,
        "terminalSha": evidence.terminal_sha,
        "targetBranch": evidence.target_branch,
        "reconciledAt": now_iso,
    }
    if evidence.head_sha:
        receipt_payload["headSha"] = evidence.head_sha
    if evidence.native_ticket_id:
        receipt_payload["nativeTicketId"] = evidence.native_ticket_id

    try:
        updated = pf.complete_ticket(
            ticket.id,
            note=(
                f"Reconciled verified merge ({evidence.terminal_receipt_ref} "
                f"@ {evidence.terminal_sha})"
            ),
            completion_receipt=receipt_payload,
            reason="reconcile:verified_merge_receipt",
            actor=actor,
            expected_updated_at=expected_updated_at,
        )
        if updated is None:
            return False, "not_found"
        pf.append_ticket_evidence(
            ticket.id,
            idempotency_key=f"reconcile-merged:{ticket.id}:{evidence.terminal_sha}",
            collection="reconciliation_receipts",
            evidence=receipt_payload,
            reason="reconcile:verified_merge_receipt",
            actor=actor,
        )
        return True, "applied"
    except (TicketUpdatedAtConflictError, ImmutableTerminalReopenError):
        return False, "cas_conflict"


def _apply_reopen_transition(
    pf: Planfile,
    ticket: Ticket,
    *,
    actor: str,
) -> tuple[bool, str]:
    from planfile.core.store import (
        ImmutableTerminalReopenError,
        TicketUpdatedAtConflictError,
    )

    expected_updated_at = (
        ticket.updated_at.isoformat()
        if isinstance(ticket.updated_at, datetime)
        else str(ticket.updated_at)
    )
    exec_data = (
        ticket.execution.model_dump(mode="python", exclude_none=False)
        if ticket.execution
        else {}
    )
    exec_data.update(
        state="ready",
        assigned_to=None,
        lease_expires_at=None,
        started_at=None,
        finished_at=None,
    )
    execution = TicketExecution(**exec_data)
    try:
        updated = pf.update_ticket(
            ticket.id,
            status="open",
            execution=execution,
            reason="reconcile:abandoned_in_progress_without_live_lease_or_worktree",
            actor=actor,
            expected_updated_at=expected_updated_at,
        )
        if updated is None:
            return False, "not_found"
        return True, "applied"
    except (TicketUpdatedAtConflictError, ImmutableTerminalReopenError):
        return False, "cas_conflict"


def _build_slug_index(
    workspace_root: Path | None,
    observations: MutableMapping[Path, TargetRepoObservation],
    now: datetime,
) -> dict[str, Path]:
    if workspace_root is None:
        return {}
    index: dict[str, Path] = {}
    for repo_path in discover_planfile_repositories(workspace_root):
        obs = observations.get(repo_path)
        if obs is None:
            obs = observe_target_repository(repo_path, now=now)
            observations[repo_path] = obs
        if obs.observable and obs.repository_slug:
            index[obs.repository_slug] = repo_path
    return index


def reconcile_in_progress(
    pf_or_path: Planfile | str | Path = ".",
    *,
    apply: bool = False,
    sprint: str = "active",
    workspace_root: str | Path | None = None,
    now: datetime | None = None,
    actor: str = "planfile.reconcile",
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
) -> dict[str, Any]:
    """Reconcile Planfile ``in_progress`` tickets against live leases, worktrees, and merge receipts.

    Defaults to dry-run reporting (``apply=False``). When ``apply=True``, verified
    merged tickets transition atomically to ``done`` with ``terminalReceiptRef`` and
    ``terminalSha``, abandoned tickets without a live lease or active worktree
    return to ``open``, and locally unobservable target repositories are preserved
    as ``unobserved`` without guessing.
    """

    from planfile import Planfile as PlanfileCls

    pf = (
        pf_or_path
        if isinstance(pf_or_path, PlanfileCls)
        else PlanfileCls(str(pf_or_path))
    )
    current_time = _utc_now(now)
    now_iso = current_time.isoformat().replace("+00:00", "Z")
    default_repo = pf.store.primary_project_dir
    ws_root = Path(workspace_root) if workspace_root is not None else None
    obs_cache: MutableMapping[Path, TargetRepoObservation] = (
        observations if observations is not None else {}
    )
    slug_index = _build_slug_index(ws_root, obs_cache, current_time)

    tickets = iter_sprint_tickets(pf, sprint=sprint)
    in_progress_tickets = [
        t
        for t in tickets
        if (t.status.value if hasattr(t.status, "value") else str(t.status)) == "in_progress"
    ]

    counts = {
        "scanned_in_progress": len(in_progress_tickets),
        "merged_to_done": 0,
        "abandoned_to_open": 0,
        "active_retained": 0,
        "unobserved_preserved": 0,
        "applied": 0,
        "cas_conflicts": 0,
    }
    decisions: list[dict[str, Any]] = []

    for ticket in in_progress_tickets:
        obs, unobserved_reason = resolve_ticket_target_repo(
            ticket,
            default_repo_dir=default_repo,
            workspace_root=ws_root,
            now=current_time,
            observations=obs_cache,
            slug_index=slug_index,
        )
        if obs is None or unobserved_reason is not None:
            counts["unobserved_preserved"] += 1
            decisions.append(
                {
                    "id": ticket.id,
                    "sprint": ticket.sprint,
                    "classification": "unobserved",
                    "action": "preserve_unobserved",
                    "previous_status": "in_progress",
                    "proposed_status": "in_progress",
                    "applied": False,
                    "reason": unobserved_reason or "target_repository_unobserved",
                    "repo_path": str(obs.repo_dir) if obs is not None else None,
                }
            )
            continue

        bindings = _extract_ticket_bindings(ticket, obs)
        if obs.receipt_registry_corrupt and bindings.native_tickets:
            counts["unobserved_preserved"] += 1
            decisions.append(
                {
                    "id": ticket.id,
                    "sprint": ticket.sprint,
                    "classification": "unobserved",
                    "action": "preserve_unobserved",
                    "previous_status": "in_progress",
                    "proposed_status": "in_progress",
                    "applied": False,
                    "reason": "terminal_receipt_registry_corrupt",
                    "repo_path": str(obs.repo_dir),
                }
            )
            continue

        merge_evidence = find_verified_merge_evidence(ticket, obs)
        if merge_evidence is not None:
            counts["merged_to_done"] += 1
            applied = False
            outcome = "dry_run"
            if apply:
                applied, outcome = _apply_merge_transition(
                    pf,
                    ticket,
                    merge_evidence,
                    now_iso=now_iso,
                    actor=actor,
                )
                if applied:
                    counts["applied"] += 1
                elif outcome == "cas_conflict":
                    counts["cas_conflicts"] += 1
            decisions.append(
                {
                    "id": ticket.id,
                    "sprint": ticket.sprint,
                    "classification": "merged",
                    "action": "close_merged",
                    "previous_status": "in_progress",
                    "proposed_status": "done",
                    "applied": applied,
                    "outcome": outcome,
                    "reason": "verified_merge_receipt",
                    "repo_path": str(obs.repo_dir),
                    "terminalReceiptRef": merge_evidence.terminal_receipt_ref,
                    "terminalSha": merge_evidence.terminal_sha,
                    "nativeTicketId": merge_evidence.native_ticket_id,
                }
            )
            continue

        live_status = find_live_ticket_binding(ticket, obs, now=current_time)
        if live_status.ambiguous_error is not None:
            counts["unobserved_preserved"] += 1
            decisions.append(
                {
                    "id": ticket.id,
                    "sprint": ticket.sprint,
                    "classification": "unobserved",
                    "action": "preserve_unobserved",
                    "previous_status": "in_progress",
                    "proposed_status": "in_progress",
                    "applied": False,
                    "reason": live_status.ambiguous_error,
                    "repo_path": str(obs.repo_dir),
                }
            )
            continue

        if live_status.is_live:
            counts["active_retained"] += 1
            decisions.append(
                {
                    "id": ticket.id,
                    "sprint": ticket.sprint,
                    "classification": "active",
                    "action": "keep_in_progress",
                    "previous_status": "in_progress",
                    "proposed_status": "in_progress",
                    "applied": False,
                    "reason": live_status.reason,
                    "repo_path": str(obs.repo_dir),
                    "leaseId": live_status.lease_id,
                    "worktreeId": live_status.worktree_id,
                }
            )
            continue

        counts["abandoned_to_open"] += 1
        applied = False
        outcome = "dry_run"
        if apply:
            applied, outcome = _apply_reopen_transition(pf, ticket, actor=actor)
            if applied:
                counts["applied"] += 1
            elif outcome == "cas_conflict":
                counts["cas_conflicts"] += 1
        decisions.append(
            {
                "id": ticket.id,
                "sprint": ticket.sprint,
                "classification": "abandoned",
                "action": "reopen_abandoned",
                "previous_status": "in_progress",
                "proposed_status": "open",
                "applied": applied,
                "outcome": outcome,
                "reason": "no_live_lease_or_active_worktree",
                "repo_path": str(obs.repo_dir),
            }
        )

    default_obs = obs_cache.get(default_repo.resolve()) if default_repo.exists() else None
    return {
        "schema": RECONCILE_REPORT_SCHEMA,
        "generated_at": now_iso,
        "mode": "apply" if apply else "dry_run",
        "project_dir": str(default_repo),
        "repository": default_obs.repository_slug if default_obs else None,
        "sprint": sprint,
        "counts": counts,
        "decisions": decisions,
    }


reconcile = reconcile_in_progress


def reconcile_fleet_in_progress(
    workspace_root: str | Path,
    *,
    apply: bool = False,
    sprint: str = "active",
    now: datetime | None = None,
    actor: str = "planfile.reconcile",
    max_depth: int = 2,
) -> dict[str, Any]:
    """Reconcile ``in_progress`` tickets across all ``.planfile`` repositories under ``workspace_root``."""

    current_time = _utc_now(now)
    now_iso = current_time.isoformat().replace("+00:00", "Z")
    ws_path = Path(workspace_root)
    obs_cache: dict[Path, TargetRepoObservation] = {}
    repos = discover_planfile_repositories(ws_path, max_depth=max_depth)

    totals = {
        "repositories_scanned": len(repos),
        "scanned_in_progress": 0,
        "merged_to_done": 0,
        "abandoned_to_open": 0,
        "active_retained": 0,
        "unobserved_preserved": 0,
        "applied": 0,
        "cas_conflicts": 0,
    }
    repo_reports: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []

    for repo_dir in repos:
        report = reconcile_in_progress(
            repo_dir,
            apply=apply,
            sprint=sprint,
            workspace_root=ws_path,
            now=current_time,
            actor=actor,
            observations=obs_cache,
        )
        repo_reports.append(report)
        for key in (
            "scanned_in_progress",
            "merged_to_done",
            "abandoned_to_open",
            "active_retained",
            "unobserved_preserved",
            "applied",
            "cas_conflicts",
        ):
            totals[key] += int(report["counts"][key])
        all_decisions.extend(report["decisions"])

    return {
        "schema": RECONCILE_REPORT_SCHEMA,
        "generated_at": now_iso,
        "mode": "apply" if apply else "dry_run",
        "workspace_root": str(ws_path),
        "sprint": sprint,
        "counts": totals,
        "repositories": repo_reports,
        "decisions": all_decisions,
    }


__all__ = [
    "RECONCILE_MERGE_EVIDENCE_SCHEMA",
    "RECONCILE_REPORT_SCHEMA",
    "TERMINAL_LEASE_PHASES",
    "LiveBindingStatus",
    "LiveLeaseInfo",
    "TargetRepoObservation",
    "TerminalReceiptEntry",
    "VerifiedMergeEvidence",
    "WorktreeInfo",
    "discover_planfile_repositories",
    "find_live_ticket_binding",
    "find_verified_merge_evidence",
    "iter_sprint_tickets",
    "observe_target_repository",
    "reconcile",
    "reconcile_fleet_in_progress",
    "reconcile_in_progress",
    "resolve_ticket_target_repo",
]


class _CallableReconcileModule(types.ModuleType):
    def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return reconcile_in_progress(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableReconcileModule
