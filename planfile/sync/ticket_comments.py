"""Explicit public results for one mapped ticket, independent of backlog sync.

Only text passed to ``queue_comment`` is published. Ticket descriptions, private
execution notes and command output are never copied to GitHub implicitly.
The caller owns public-text review; this module is a transport, not a sanitizer.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_ISSUE = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)")


def _binding(store, ticket_id: str) -> tuple[str, int, str]:
    ticket = store.get_ticket(ticket_id)
    if ticket is None:
        raise ValueError("ticket does not exist")
    mapping = ticket.sync.get("github", {})
    match = _ISSUE.fullmatch(str(mapping.get("url", "")))
    if not match or str(mapping.get("id", "")) != match[2]:
        raise ValueError("ticket needs an exact GitHub issue URL and id mapping")
    return match[1], int(match[2]), match[0]


@contextmanager
def _outbox(store):
    root = Path(store.project_dir)
    folder = root / ".subactor/cache/planfile-comments"
    for part in (folder, *folder.parents):
        if part.is_symlink():
            raise ValueError("comment storage must not contain symlinks")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = folder / "outbox.sqlite3"
    if path.is_symlink():
        raise ValueError("comment storage must not be a symlink")
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY, ticket TEXT NOT NULL, repository TEXT NOT NULL,
            issue INTEGER NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL,
            comment_url TEXT, attempts INTEGER NOT NULL DEFAULT 0)""")
        db.commit()
        yield db
    finally:
        db.close()


def queue_comment(store, ticket_id: str, *, event_id: str, public_body: str) -> str:
    """Durably queue deliberately public text; replay may not change its body."""
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", event_id):
        raise ValueError("invalid comment event id")
    if not isinstance(public_body, str) or not public_body.strip() or len(public_body) > 50_000:
        raise ValueError("public comment must contain 1..50000 characters")
    repository, issue, _ = _binding(store, ticket_id)
    identity = json.dumps([repository, issue, ticket_id, event_id], separators=(",", ":"))
    comment_id = hashlib.sha256(identity.encode()).hexdigest()
    body = public_body.rstrip() + f"\n\n<!-- planfile:comment={comment_id} -->"
    with _outbox(store) as db, db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT body FROM comments WHERE id=?", (comment_id,)).fetchone()
        if existing and existing["body"] != body:
            raise ValueError("comment event already binds different public text")
        db.execute(
            "INSERT OR IGNORE INTO comments(id,ticket,repository,issue,body,state) VALUES(?,?,?,?,?,'pending')",
            (comment_id, ticket_id, repository, issue, body),
        )
    return comment_id


def sync_comment(store, backend, comment_id: str) -> dict:
    """Send exactly one event. On transport failure it remains retryable.

    The transaction serializes local senders. A retry after an uncertain POST
    reconciles the exact remote body before sending. It never edits/closes the
    issue, invokes an executor, or drains another ticket's pending events.
    """
    if not re.fullmatch(r"[a-f0-9]{64}", comment_id):
        raise ValueError("invalid comment id")
    with _outbox(store) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM comments WHERE id=?", (comment_id,)).fetchone()
        if row is None:
            raise ValueError("unknown comment event")
        repository, issue_number, expected_url = _binding(store, row["ticket"])
        if (repository, issue_number) != (row["repository"], row["issue"]):
            raise ValueError("ticket mapping changed after queuing the comment")
        if backend.config.get("repo") != repository or backend.repo.full_name != repository:
            raise ValueError("GitHub backend targets a different repository")
        if row["state"] == "delivered":
            return {"id": comment_id, "state": "delivered", "url": row["comment_url"]}
        db.execute("UPDATE comments SET attempts=attempts+1 WHERE id=?", (comment_id,))
        try:
            issue = backend.repo.get_issue(issue_number)
            if issue.html_url != expected_url or getattr(issue, "pull_request", None):
                raise ValueError("remote target is not the mapped GitHub issue")
            comment = next((c for c in issue.get_comments() if c.body == row["body"]), None)
            if comment is None:
                comment = issue.create_comment(row["body"])
            db.execute(
                "UPDATE comments SET state='delivered', comment_url=? WHERE id=?",
                (comment.html_url, comment_id),
            )
        except Exception:
            db.commit()  # Preserve the attempt; no raw transport error is published.
            raise
        db.commit()
        return {"id": comment_id, "state": "delivered", "url": comment.html_url}
