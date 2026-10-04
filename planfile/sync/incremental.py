"""Explicit, repository-scoped incremental outbound delivery."""

from __future__ import annotations

import time
from contextlib import nullcontext
from types import SimpleNamespace

from planfile.sync.operations import _validate_ticket_binding
from planfile.sync.receipts import latest_ticket_receipts, publish_intent
from planfile.sync.retry import RetryQueue, drain_retries
from planfile.sync.state import normalize_repository


def _acknowledged(payload: dict, digest: str, receipt: dict | None, repository: str) -> bool:
    if not receipt or receipt.get('outcome') != 'succeeded' or receipt.get('payload_digest') != digest:
        return False
    reference = (payload.get('sync') or {}).get('github') or {}
    if str(reference.get('id') or '') != str(receipt.get('remote_id') or ''):
        return False
    if '/pull/' in str(reference.get('url') or ''):
        return False
    try:
        _validate_ticket_binding(payload, 'github', SimpleNamespace(config={'repo': repository}))
    except ValueError:
        return False
    return True


def sync_incremental(pf, *, ticket_ids: list[str] | None = None, repository: str | None = None,
                     max_tickets: int = 2, dry_run: bool = False, now: float | None = None,
                     deliver=None) -> dict:
    """Persist dirty revisions and deliver a bounded batch from exactly this scope.

    This is outbound local-content synchronization. Tracker-side drift and
    comments retain their separately authorized reconciliation paths.
    """
    if not 1 <= max_tickets <= 100:
        raise ValueError('sync_retry_batch_invalid')
    if repository is None:
        from planfile.core.configuration import ConfigurationManager
        config = ConfigurationManager(SimpleNamespace(store=pf.store))._integration_values()
        repository = (config.get('github') or {}).get('repo')
    if not repository:
        raise ValueError('sync_incremental_repository_required')
    repository = normalize_repository(repository)
    clock = time.time() if now is None else now
    queue = RetryQueue(pf.store.base_dir)
    receipts = latest_ticket_receipts(pf.store.base_dir, 'github', repository)
    jobs = {j['ticket_id']: j for j in queue.entries() if j['repository'] == repository}
    selected = ticket_ids if ticket_ids is not None else [t.id for t in pf.list_tickets(sprint='all')]
    selected = list(dict.fromkeys(selected))
    dirty, unchanged, ready = [], [], []
    pauses = queue.cooldowns()
    for ident in selected:
        with nullcontext() if dry_run else pf.store.mutation_lock():
            ticket = pf.get_ticket(ident, repair_index=False)
            if ticket is None or 'github' not in (ticket.integration or []):
                continue
            payload = ticket.model_dump(mode='json')
            digest = publish_intent(ident, payload, 'github', repository)['payload_digest']
            job, receipt = jobs.get(ident), receipts.get(ident)
            same_job = job is not None and job['payload_digest'] == digest
            # A job already in flight or failed remains dirty until that exact
            # revision is acknowledged. Historical receipts never clear it.
            acknowledged = _acknowledged(payload, digest, receipt, repository)
            if (same_job and job['state'] == 'succeeded' and (receipt is None or acknowledged)
                    or job is None and acknowledged):
                unchanged.append(ident)
                continue
            dirty.append(ident)
            eligible = not job or job['state'] == 'succeeded' or (
                job['state'] == 'running' and (not same_job or job['lease_until'] <= clock)
            ) or (
                job['state'] in {'pending', 'failed'} and (
                    job['next_attempt_at'] <= clock or not same_job and job['attempts'] == 0
                )
            )
            if eligible and pauses.get(repository, 0) <= clock:
                ready.append(ident)
            if not dry_run:
                queue.enqueue(repository, ident, payload, now=now,
                              force=bool(same_job and job['state'] == 'succeeded'))
    if dry_run:
        result = {'planned': ready[:max_tickets], 'succeeded': [], 'failed': [], 'refreshed': []}
    elif dirty:
        result = drain_retries(pf, max_tickets=max_tickets, now=now, deliver=deliver,
                               ticket_ids=dirty, repository_override=repository,
                               recover_completions=False)
    else:
        result = {'planned': [], 'succeeded': [], 'failed': [], 'refreshed': []}
    return {**result, 'dirty': dirty, 'unchanged': unchanged,
            'resume_at': queue.cooldowns().get(repository)}
