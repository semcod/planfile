"""Local completion enqueue; only an explicitly invoked worker may publish."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from planfile.core.configuration import ConfigurationManager
from planfile.sync.receipts import publish_intent
from planfile.sync.state import normalize_repository


def _completion_repository(store) -> str | None:
    # Reuse the safe config reader: no dotenv/environment mutation or credentials.
    manager = ConfigurationManager(SimpleNamespace(store=store))
    github = manager._integration_values().get('github') or {}
    policy = github.get('sync') or {}
    if not isinstance(policy, dict) or policy.get('enqueue_on_done') is not True:
        return None
    repository = normalize_repository(github.get('repo'))
    if not repository:
        raise ValueError('sync_completion_repository_missing')
    return repository


def enqueue_completion(store, ticket) -> bool:
    """Coalesce a committed done payload into the existing local retry journal."""
    if ticket is None or ticket.status != 'done' or 'github' not in (ticket.integration or []):
        return False
    repository = _completion_repository(store)
    if repository is None:
        return False
    from planfile.sync.retry import RetryQueue

    RetryQueue(store.base_dir).enqueue(repository, ticket.id, ticket.model_dump(mode='json'))
    return True


def reconcile_completions(pf, queue, repository, *, dry_run=False, now=None) -> list[str]:
    """Recover commit/enqueue crash gaps within one opted-in project.

    Same-digest pending, failed, running and succeeded records are untouched.
    Delivery is still bounded/fenced by the retry worker. This local recovery
    scan does not itself authorize a network operation.
    """
    configured = _completion_repository(pf.store)
    if configured is None:
        return []
    if configured != repository:
        raise ValueError('sync_completion_repository_changed')
    pending = []
    for observed in pf.list_tickets(sprint='all', status='done'):
        # Read the current revision under the same lock as completion enqueue.
        # A stale scan must not replace a newer queued edit or reset its retry.
        with nullcontext() if dry_run else pf.store.mutation_lock():
            ticket = pf.get_ticket(observed.id, repair_index=False)
            if ticket is None or ticket.status != 'done' or 'github' not in (ticket.integration or []):
                continue
            payload = ticket.model_dump(mode='json')
            digest = publish_intent(ticket.id, payload, 'github', repository)['payload_digest']
            old = next((j for j in queue.entries(ticket.id) if j['repository'] == repository), None)
            if old is not None and old['payload_digest'] == digest:
                continue
            pending.append(ticket.id)
            if not dry_run:
                queue.enqueue(repository, ticket.id, payload, now=now)
    return pending
