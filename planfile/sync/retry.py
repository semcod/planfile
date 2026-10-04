"""Durable, opt-in GitHub delivery retries; queue records never grant authority."""

from __future__ import annotations

import math
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from planfile.sync.receipts import publish_intent
from planfile.sync.state import normalize_repository


class RetryQueue:
    """One current payload per store/repository/ticket, with fenced acknowledgements."""

    def __init__(self, planfile_dir: Path):
        self.path = Path(planfile_dir).resolve() / 'sync' / 'github.retry.sqlite3'

    @contextmanager
    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.row_factory = sqlite3.Row
            db.execute('''CREATE TABLE IF NOT EXISTS retry_jobs (
                repository TEXT NOT NULL, ticket_id TEXT NOT NULL,
                payload_digest TEXT NOT NULL, revision INTEGER NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL,
                next_attempt_at REAL NOT NULL, lease_until REAL,
                worker_token TEXT, last_error TEXT,
                PRIMARY KEY(repository, ticket_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS retry_pauses (
                repository TEXT PRIMARY KEY, next_attempt_at REAL NOT NULL)''')
            db.execute('BEGIN IMMEDIATE')
            yield db

    def entries(self, ticket_id: str | None = None) -> list[dict]:
        """Read status without creating a database or modifying its contents."""
        if not self.path.exists():
            return []
        with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5) as db:
            db.row_factory = sqlite3.Row
            query = 'SELECT * FROM retry_jobs'
            args = ()
            if ticket_id is not None:
                query += ' WHERE ticket_id=?'
                args = (ticket_id,)
            rows = db.execute(query + ' ORDER BY next_attempt_at, repository, ticket_id', args)
            # Worker tokens are internal fencing data, not a public capability.
            return [{k: row[k] for k in row.keys() if k != 'worker_token'} for row in rows]

    def enqueue(self, repository: str, ticket_id: str, payload: dict, *, now: float | None = None, force: bool = False):
        repository = normalize_repository(repository)
        digest = publish_intent(ticket_id, payload, 'github', repository)['payload_digest']
        now = time.time() if now is None else now
        with self._write() as db:
            old = db.execute('SELECT * FROM retry_jobs WHERE repository=? AND ticket_id=?',
                             (repository, ticket_id)).fetchone()
            if old is not None and old['payload_digest'] == digest and not (force and old['state'] == 'succeeded'):
                return old['revision']
            revision = old['revision'] + 1 if old else 1
            # A replacement payload stays pending, so later edits must retain
            # the same cooldown/attempt history too until a worker succeeds.
            cooling = old is not None and old['state'] in {'pending', 'failed'} and old['attempts'] > 0
            next_attempt = max(now, old['next_attempt_at']) if cooling else now
            attempts = old['attempts'] if cooling else 0
            last_error = old['last_error'] if cooling else None
            db.execute('''INSERT INTO retry_jobs VALUES(?,?,?,?, 'pending',?,?,NULL,NULL,?)
                ON CONFLICT(repository,ticket_id) DO UPDATE SET
                payload_digest=excluded.payload_digest, revision=excluded.revision,
                state='pending', attempts=excluded.attempts,
                next_attempt_at=excluded.next_attempt_at,
                lease_until=NULL, worker_token=NULL, last_error=excluded.last_error''',
                       (repository, ticket_id, digest, revision, attempts, next_attempt, last_error))
            return revision

    def cooldowns(self) -> dict[str, float]:
        """Read repository deadlines without migrating an old journal."""
        if not self.path.exists():
            return {}
        with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='retry_pauses'").fetchone():
                return {}
            return dict(db.execute('SELECT repository, next_attempt_at FROM retry_pauses'))

    def pause(self, repository: str, *, delay: float, now: float | None = None) -> None:
        """Extend this repository's provider deadline; never sleep in the worker."""
        repository = normalize_repository(repository)
        now = time.time() if now is None else now
        if not math.isfinite(delay) or delay < 0 or not math.isfinite(now + delay):
            raise ValueError('sync_retry_pause_invalid')
        with self._write() as db:
            db.execute('INSERT INTO retry_pauses VALUES(?,?) '
                       'ON CONFLICT(repository) DO UPDATE SET '
                       'next_attempt_at=MAX(retry_pauses.next_attempt_at,excluded.next_attempt_at)',
                       (repository, now + delay))

    def claim(self, *, repository: str | None = None, ticket_id: str | None = None,
              now: float | None = None, lease_seconds: float = 300,
              ticket_ids: list[str] | None = None) -> dict | None:
        if not self.path.exists() or ticket_ids == []:
            return None
        if not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError('sync_retry_lease_invalid')
        now = time.time() if now is None else now
        with self._write() as db:
            query = '''SELECT * FROM retry_jobs WHERE
                ((state IN ('pending','failed') AND next_attempt_at<=?)
                OR (state='running' AND lease_until<=?))
                AND NOT EXISTS (SELECT 1 FROM retry_pauses p
                    WHERE p.repository=retry_jobs.repository AND p.next_attempt_at>?)'''
            args = [now, now, now]
            if repository is not None:
                query += ' AND repository=?'
                args.append(normalize_repository(repository))
            if ticket_id is not None:
                query += ' AND ticket_id=?'
                args.append(ticket_id)
            if ticket_ids is not None:
                query += ' AND ticket_id IN (' + ','.join('?' for _ in ticket_ids) + ')'
                args.extend(ticket_ids)
            row = db.execute(query + ' ORDER BY next_attempt_at, ticket_id LIMIT 1', args).fetchone()
            if row is None:
                return None
            job = dict(row)
            job.update(state='running', worker_token=uuid.uuid4().hex,
                       lease_until=now + lease_seconds, attempts=row['attempts'] + 1)
            db.execute('''UPDATE retry_jobs SET state='running', worker_token=?,
                lease_until=?, attempts=? WHERE repository=? AND ticket_id=?''',
                       (job['worker_token'], job['lease_until'], job['attempts'],
                        job['repository'], job['ticket_id']))
            return job

    def finish(self, job: dict, *, error: str | None = None,
               retry_after: float | None = None, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if error is not None and not re.fullmatch(r'[A-Za-z0-9_]{1,80}', error):
            raise ValueError('sync_retry_error_code_invalid')
        delay = min(3600, 30 * 2 ** min(job['attempts'] - 1, 7))
        if retry_after is not None and math.isfinite(retry_after) and retry_after >= 0:
            delay = max(delay, retry_after)
        with self._write() as db:
            result = db.execute('''UPDATE retry_jobs SET state=?, next_attempt_at=?,
                lease_until=NULL, worker_token=NULL, last_error=?
                WHERE repository=? AND ticket_id=? AND revision=?
                AND worker_token=? AND state='running' AND lease_until>?''',
                                ('failed' if error else 'succeeded', now + delay if error else now,
                                 error, job['repository'], job['ticket_id'], job['revision'],
                                 job['worker_token'], now))
            return result.rowcount == 1


def retry_hint(error: Exception) -> float | None:
    """Retain a provider cooldown through CLI exception wrapping, without raw errors."""
    seen = set()
    for _ in range(8):
        if error is None or id(error) in seen:
            break
        seen.add(id(error))
        value = getattr(error, 'retry_after', None)
        if value is None:
            from planfile.sync.operations import _is_rate_limit_error
            from planfile.sync.outbound import _retry_after_seconds
            if _is_rate_limit_error(error):
                value = _retry_after_seconds(error)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value >= 0:
                return value
        error = error.__cause__ or error.__context__
    return None


def rate_limited(error: Exception) -> bool:
    """Recognize wrapped provider rate limits without treating permissions as quota."""
    from planfile.sync.operations import _is_rate_limit_error
    seen = set()
    for _ in range(8):
        if error is None or id(error) in seen:
            break
        seen.add(id(error))
        if getattr(error, 'rate_limited', False) is True or _is_rate_limit_error(error):
            return True
        error = error.__cause__ or error.__context__
    return False


def drain_retries(pf, *, max_tickets: int = 2, dry_run: bool = False,
                  now: float | None = None, deliver=None,
                  ticket_ids: list[str] | None = None, repository_override: str | None = None,
                  recover_completions: bool = True) -> dict:
    """Drain a bounded batch only when explicitly invoked by an authorized worker."""
    if not 1 <= max_tickets <= 100:
        raise ValueError('sync_retry_batch_invalid')
    from planfile.integrations.config import IntegrationConfig

    config = IntegrationConfig(str(pf.store.project_dir))
    config.load_configs()
    repository = config.get_integration_config('github').get('repo')
    repository = normalize_repository(repository_override or repository) if repository_override or repository else None
    queue = RetryQueue(Path(pf.store.base_dir))
    clock = time.time() if now is None else now
    from planfile.sync.completion import reconcile_completions

    try:
        recovered = reconcile_completions(pf, queue, repository, dry_run=dry_run, now=now) if recover_completions else []
    except Exception:
        # Local commit/enqueue recovery failed. Do not expose config/SQL errors
        # or claim that any remote ticket completed.
        raise RuntimeError('sync_completion_reconcile_failed') from None
    pauses = queue.cooldowns()
    due = [j for j in queue.entries() if (
        (ticket_ids is None or j['ticket_id'] in ticket_ids and j['repository'] == repository)
        and pauses.get(j['repository'], 0) <= clock
    ) and ((
        j['state'] in {'pending', 'failed'} and j['next_attempt_at'] <= clock
    ) or (j['state'] == 'running' and j['lease_until'] <= clock))]
    if dry_run:
        planned = list(dict.fromkeys([j['ticket_id'] for j in due] + recovered))
        return {'planned': planned[:max_tickets],
                'succeeded': [], 'failed': [], 'refreshed': []}
    result = {'planned': [], 'succeeded': [], 'failed': [], 'refreshed': []}
    backend = None
    for _ in range(max_tickets):
        job = queue.claim(now=now, ticket_ids=ticket_ids,
                          repository=repository if ticket_ids is not None else None)
        if job is None:
            break
        ident = job['ticket_id']
        try:
            if repository != job['repository']:
                raise ValueError('sync_retry_repository_changed')
            ticket = pf.get_ticket(ident)
            if ticket is None or 'github' not in (ticket.integration or []):
                raise ValueError('sync_retry_ticket_route_missing')
            payload = ticket.model_dump(mode='json')
            digest = publish_intent(ident, payload, 'github', repository)['payload_digest']
            if digest != job['payload_digest']:
                queue.enqueue(repository, ident, payload, now=now)
                result['refreshed'].append(ident)
                continue
            if deliver is None:
                from planfile.cli.groups.sync.core import _initialize_backend
                from planfile.sync.outbound import sync_to_external

                if backend is None:
                    if repository_override:
                        config.config.setdefault('integrations', {}).setdefault('github', {})['repo'] = repository
                    backend = _initialize_backend('github', config, False)
                outcome = sync_to_external(backend, [(ident, payload)], False, pf.store, 'github')
            else:
                outcome = deliver(pf, ticket, repository)
            if ident not in outcome.succeeded or ident in outcome.failed:
                raise RuntimeError('sync_retry_publication_unverified')
            current = pf.get_ticket(ident)
            current_payload = current.model_dump(mode='json') if current else None
            if current_payload is None or publish_intent(
                ident, current_payload, 'github', repository
            )['payload_digest'] != job['payload_digest']:
                if current_payload is not None:
                    queue.enqueue(repository, ident, current_payload, now=now)
                result['refreshed'].append(ident)
            elif queue.finish(job, now=now):
                result['succeeded'].append(ident)
            else:
                result['refreshed'].append(ident)
        except Exception as exc:
            limited = rate_limited(exc)
            hint = retry_hint(exc)
            if limited:
                hint = hint if hint is not None else min(3600, 60 * 2 ** min(job['attempts'] - 1, 6))
                queue.pause(job['repository'], delay=hint, now=now)
            queue.finish(job, error=type(exc).__name__, retry_after=hint, now=now)
            result['failed'].append(ident)
            if limited:
                break
    return result
