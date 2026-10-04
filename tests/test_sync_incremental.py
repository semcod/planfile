"""Incremental selection, bounded scope and durable provider backoff."""

import sqlite3

import pytest
from github import GithubException

from planfile import Planfile
from planfile.sync.outbound import OutboundSyncResult
from planfile.sync.receipts import publish_intent, record_receipt
from planfile.sync.retry import RetryQueue, drain_retries


@pytest.fixture(params=['yaml', 'sharded-yaml'])
def context(tmp_path, request):
    pf = Planfile(str(tmp_path))
    if request.param == 'sharded-yaml':
        pf.store.migrate_to_sharded_yaml(shard_size=100)
    pf.configuration.set_many({'integrations.github.repo': 'owner/repo'})
    return pf, RetryQueue(pf.store.base_dir)


def run(pf, **kwargs):
    from planfile.sync.incremental import sync_incremental
    return sync_incremental(pf, **kwargs)


def success(calls):
    def deliver(pf, ticket, repository):
        calls.append(ticket.id)
        return OutboundSyncResult(succeeded=(ticket.id,))
    return deliver


def test_restart_skips_unchanged_then_selects_only_latest_edit(context):
    pf, queue = context
    ticket = pf.create_ticket('New', integration=['github'])
    calls = []
    assert run(pf, now=100, deliver=success(calls))['succeeded'] == [ticket.id]
    restarted = Planfile(str(pf.store.project_dir))
    assert run(restarted, now=101, deliver=lambda *a: pytest.fail('unchanged network'))['unchanged'] == [ticket.id]
    pf.update_ticket(ticket.id, description='changed')
    assert run(restarted, now=102, deliver=success(calls))['succeeded'] == [ticket.id]
    assert calls == [ticket.id, ticket.id]
    assert queue.entries()[0]['revision'] == 2


def test_exact_scope_never_drains_an_unselected_due_job(context):
    pf, queue = context
    other = pf.create_ticket('Earlier pending', integration=['github'])
    wanted = pf.create_ticket('Requested', integration=['github'])
    queue.enqueue('owner/repo', other.id, other.model_dump(mode='json'), now=1)
    calls = []
    result = run(pf, ticket_ids=[wanted.id], now=100, deliver=success(calls))
    assert result['succeeded'] == [wanted.id] and calls == [wanted.id]
    assert queue.entries(other.id)[0]['state'] == 'pending'


def test_dry_run_never_creates_or_changes_journal(context):
    pf, queue = context
    ticket = pf.create_ticket('Preview', integration=['github'])
    assert run(pf, dry_run=True, now=100)['planned'] == [ticket.id]
    assert not queue.path.exists()
    run(pf, now=100, deliver=success([]))
    before = queue.path.read_bytes()
    assert run(pf, dry_run=True, now=101)['unchanged'] == [ticket.id]
    assert queue.path.read_bytes() == before


def test_failure_and_concurrent_newer_edit_stay_dirty(context):
    pf, queue = context
    ticket = pf.create_ticket('Concurrent', integration=['github'])
    def deliver(pf, current, repository):
        pf.update_ticket(current.id, description='newer during request')
        return OutboundSyncResult(succeeded=(current.id,))
    result = run(pf, max_tickets=1, now=100, deliver=deliver)
    assert result['refreshed'] == [ticket.id] and not result['succeeded']
    assert queue.entries()[0]['state'] == 'pending'
    result = run(pf, now=101, deliver=lambda *a: (_ for _ in ()).throw(TimeoutError()))
    assert result['failed'] == [ticket.id]
    assert queue.entries()[0]['state'] == 'failed'
    assert run(pf, now=102, deliver=lambda *a: pytest.fail('cooldown'))['succeeded'] == []


def test_batch_is_bounded_and_excludes_unrouted_tickets(context):
    pf, queue = context
    pf.create_ticket('Local only', integration=[])
    tickets = [pf.create_ticket('Queued', integration=['github']) for _ in range(3)]
    calls = []
    result = run(pf, max_tickets=1, now=100, deliver=success(calls))
    assert len(result['succeeded']) == len(calls) == 1
    assert len(queue.entries()) == len(tickets)
    assert sum(j['state'] == 'pending' for j in queue.entries()) == 2


def test_existing_receipt_skips_without_creating_job(context):
    pf, queue = context
    ticket = pf.create_ticket('Existing', integration=['github'], sync={'github': {'id': '42', 'repository': 'owner/repo'}})
    intent = publish_intent(ticket.id, ticket.model_dump(mode='json'), 'github', 'owner/repo')
    record_receipt(pf.store.base_dir, intent, operation='update', outcome='succeeded', remote_id='42')
    result = run(pf, now=100, deliver=lambda *a: pytest.fail('already acknowledged'))
    assert result['unchanged'] == [ticket.id] and not queue.path.exists()


def test_latest_receipt_and_mapping_must_match(context):
    pf, queue = context
    ticket = pf.create_ticket('Existing', integration=['github'], sync={'github': {'id': '42', 'repository': 'owner/repo'}})
    payload = ticket.model_dump(mode='json')
    intent = publish_intent(ticket.id, payload, 'github', 'owner/repo')
    record_receipt(pf.store.base_dir, intent, operation='update', outcome='succeeded', remote_id='42')
    payload['description'] = 'a later remotely acknowledged version'
    record_receipt(pf.store.base_dir, publish_intent(ticket.id, payload, 'github', 'owner/repo'), operation='update', outcome='succeeded', remote_id='42')
    assert run(pf, dry_run=True, now=100)['planned'] == [ticket.id]
    pf.update_ticket(ticket.id, sync={'github': {'id': '43', 'repository': 'owner/repo'}})
    assert run(pf, dry_run=True, now=100)['planned'] == [ticket.id]


def test_rate_limit_stops_other_jobs_and_survives_restart(context):
    pf, queue = context
    tickets = [pf.create_ticket('Quota', integration=['github']) for _ in range(2)]
    for t in tickets:
        queue.enqueue('owner/repo', t.id, t.model_dump(mode='json'), now=100)
    calls = []
    def rate_limit(pf, ticket, repository):
        calls.append(ticket.id)
        raise GithubException(429, {'message': 'Secondary rate limit'}, {'Retry-After': '90'})
    result = drain_retries(pf, max_tickets=2, now=100, deliver=rate_limit)
    assert len(calls) == 1 and result['failed'] == [calls[0]]
    restarted = Planfile(str(pf.store.project_dir))
    assert not drain_retries(restarted, now=189, deliver=lambda *a: pytest.fail('provider paused'))['succeeded']
    assert len(drain_retries(restarted, now=190, deliver=success([]))['succeeded']) == 2


def test_pause_is_repository_bound_monotonic_and_read_only(tmp_path):
    queue = RetryQueue(tmp_path)
    queue.enqueue('one/repo', 'A', {'name': 'A'}, now=100)
    queue.enqueue('two/repo', 'B', {'name': 'B'}, now=100)
    queue.pause('one/repo', delay=90, now=100)
    queue.pause('one/repo', delay=1, now=101)
    before = queue.path.read_bytes()
    assert queue.cooldowns() == {'one/repo': 190}
    assert queue.path.read_bytes() == before
    assert queue.claim(now=102)['ticket_id'] == 'B'
    assert queue.claim(now=189) is None
    assert queue.claim(now=190)['ticket_id'] == 'A'


def test_old_schema_accepts_additive_pause_migration(tmp_path):
    queue = RetryQueue(tmp_path)
    queue.enqueue('one/repo', 'A', {'name': 'A'}, now=100)
    with sqlite3.connect(queue.path) as db:
        db.execute('DROP TABLE IF EXISTS retry_pauses')
    before = queue.path.read_bytes()
    assert queue.cooldowns() == {} and queue.path.read_bytes() == before
    queue.pause('one/repo', delay=60, now=100)
    assert queue.claim(now=159) is None
    assert queue.claim(now=160)['revision'] == 1


def test_secondary_limit_without_header_defers_at_least_a_minute(context):
    pf, queue = context
    ticket = pf.create_ticket('Secondary', integration=['github'])
    queue.enqueue('owner/repo', ticket.id, ticket.model_dump(mode='json'), now=100)
    def limited(*args):
        raise GithubException(403, {'message': 'You have exceeded a secondary rate limit'}, {})
    drain_retries(pf, now=100, deliver=limited)
    assert queue.claim(now=159) is None
    assert queue.claim(now=160) is not None


def test_reverting_payload_updates_same_native_issue(context, monkeypatch):
    from test_sync_lifecycle_readback import backend
    pf, queue = context
    remote = backend()
    monkeypatch.setattr('planfile.cli.groups.sync.core._initialize_backend', lambda *a: remote)
    ticket = pf.create_ticket('Revert', description='version-A', integration=['github'])
    run(pf)
    pf.update_ticket(ticket.id, description='version-B')
    run(pf)
    pf.update_ticket(ticket.id, description='version-A')
    result = run(pf)
    assert result['succeeded'] == [ticket.id]
    issue = remote.repo.get_issue(int(pf.get_ticket(ticket.id).sync['github']['id']))
    assert 'version-A' in issue.body and 'version-B' not in issue.body
    reads = remote.repo.reads
    assert run(pf)['unchanged'] == [ticket.id]
    assert remote.repo.reads == reads


def test_permission_denial_does_not_pause_unrelated_jobs(context):
    pf, queue = context
    tickets = [pf.create_ticket('Access', integration=['github']) for _ in range(2)]
    for t in tickets:
        queue.enqueue('owner/repo', t.id, t.model_dump(mode='json'), now=100)
    calls = []
    def deliver(pf, current, repository):
        calls.append(current.id)
        if current.id == tickets[0].id:
            raise GithubException(403, {'message': 'Resource not accessible by integration'}, {'X-RateLimit-Remaining': '42'})
        return OutboundSyncResult(succeeded=(current.id,))
    result = drain_retries(pf, now=100, deliver=deliver)
    assert result['failed'] == [tickets[0].id] and result['succeeded'] == [tickets[1].id]
    assert queue.cooldowns() == {}


def test_scoped_dry_run_retains_changed_payload_cooldown(context):
    pf, queue = context
    ticket = pf.create_ticket('Deferred', integration=['github'])
    queue.enqueue('owner/repo', ticket.id, ticket.model_dump(mode='json'), now=100)
    job = queue.claim(now=100)
    queue.finish(job, error='TimeoutError', retry_after=90, now=100)
    pf.update_ticket(ticket.id, description='Changed during cooldown')
    before = queue.path.read_bytes()
    result = run(pf, now=101, dry_run=True)
    assert result['dirty'] == [ticket.id] and result['planned'] == []
    assert queue.path.read_bytes() == before


def test_repository_override_binds_journal_and_delivery(context):
    pf, queue = context
    ticket = pf.create_ticket('Explicit override', integration=['github'])
    calls = []
    def deliver(pf, current, repository):
        calls.append(repository)
        return OutboundSyncResult(succeeded=(current.id,))
    assert run(pf, repository='override/repo', now=100, deliver=deliver)['succeeded'] == [ticket.id]
    assert calls == ['override/repo']
    assert queue.entries()[0]['repository'] == 'override/repo'


def test_stale_force_request_cannot_cancel_an_already_claimed_revision(tmp_path):
    queue = RetryQueue(tmp_path)
    payload = {'name': 'A'}
    queue.enqueue('owner/repo', 'A', payload, now=100)
    job = queue.claim(now=100)
    assert queue.enqueue('owner/repo', 'A', payload, now=101, force=True) == job['revision']
    assert queue.finish(job, now=102)


@pytest.mark.parametrize('hint', ['inf', 'nan', 'not-a-number'])
def test_invalid_provider_hint_falls_back_to_safe_pause(context, hint):
    pf, queue = context
    ticket = pf.create_ticket('Invalid header', integration=['github'])
    queue.enqueue('owner/repo', ticket.id, ticket.model_dump(mode='json'), now=100)
    def deliver(*args):
        raise GithubException(429, {'message': 'private'}, {'Retry-After': hint})
    result = drain_retries(pf, now=100, deliver=deliver)
    assert result['failed'] == [ticket.id]
    assert queue.claim(now=159) is None
    assert queue.claim(now=160) is not None


def test_mapping_conflict_stays_dirty_without_mutating_either_issue(context, monkeypatch):
    from test_sync_lifecycle_readback import backend
    pf, queue = context
    remote = backend()
    monkeypatch.setattr('planfile.cli.groups.sync.core._initialize_backend', lambda *a: remote)
    ticket = pf.create_ticket('Binding', integration=['github'])
    run(pf)
    reads = remote.repo.reads
    pf.update_ticket(ticket.id, sync={'github': {'id': '43', 'repository': 'owner/repo'}})
    result = run(pf)
    assert result['failed'] == [ticket.id]
    assert pf.get_ticket(ticket.id).sync['github']['id'] == '43'
    assert remote.repo.reads == reads
