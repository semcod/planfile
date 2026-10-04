"""Crash/restart, repository routing and worker fencing for durable delivery."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from planfile import Planfile
from planfile.sync.outbound import OutboundSyncResult
from planfile.sync.retry import RetryQueue, drain_retries, retry_hint


@pytest.fixture()
def queued(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.store.init()
    (tmp_path / '.planfile/github.planfile.yaml').write_text(
        'integrations:\n  github:\n    repo: owner/repo\n'
    )
    ticket = pf.create_ticket('Deliver', integration=['github'])
    queue = RetryQueue(pf.store.base_dir)
    queue.enqueue('owner/repo', ticket.id, ticket.model_dump(mode='json'), now=100)
    return pf, ticket, queue


def test_read_only_projection_never_creates_journal(tmp_path):
    queue = RetryQueue(tmp_path)
    assert queue.entries() == []
    assert not queue.path.exists()


def test_failure_survives_restart_and_retry_after_is_not_shortened(queued):
    _, ticket, queue = queued
    job = queue.claim(now=100)
    assert queue.finish(job, error='NetworkError', retry_after=240, now=101)
    restarted = RetryQueue(queue.path.parent.parent)
    entry = restarted.entries(ticket.id)[0]
    assert entry['state'] == 'failed'
    assert entry['next_attempt_at'] == 341
    assert entry['last_error'] == 'NetworkError'
    assert 'worker_token' not in entry
    assert restarted.claim(now=340) is None
    assert restarted.claim(now=341)['attempts'] == 2


def test_same_payload_cannot_reset_cooldown_or_attempts(queued):
    _, ticket, queue = queued
    job = queue.claim(now=100)
    queue.finish(job, error='RuntimeError', now=101)
    assert queue.enqueue('owner/repo', ticket.id, ticket.model_dump(mode='json'), now=102) == 1
    assert queue.claim(now=102) is None
    assert queue.entries()[0]['attempts'] == 1


def test_old_worker_cannot_clear_a_new_revision(queued):
    _, ticket, queue = queued
    old = queue.claim(now=100)
    payload = ticket.model_dump(mode='json')
    payload['description'] = 'New accepted content'
    assert queue.enqueue('owner/repo', ticket.id, payload, now=101) == 2
    assert not queue.finish(old, now=102)
    assert queue.entries()[0]['state'] == 'pending'


def test_expired_and_reclaimed_workers_are_fenced(queued):
    _, _, queue = queued
    old = queue.claim(now=100, lease_seconds=10)
    assert not queue.finish(old, now=110)
    assert queue.claim(now=109) is None
    replacement = queue.claim(now=110)
    assert replacement['worker_token'] != old['worker_token']
    assert not queue.finish(old, now=111)
    assert queue.finish(replacement, now=111)


def test_two_workers_claim_exactly_one_job(queued):
    _, _, queue = queued
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: queue.claim(now=100), range(2)))
    assert sum(job is not None for job in jobs) == 1


def test_raw_errors_and_credentials_cannot_be_persisted(queued):
    _, _, queue = queued
    job = queue.claim(now=100)
    with pytest.raises(ValueError, match='error_code_invalid'):
        queue.finish(job, error='https://provider.invalid/credential-sample', now=101)
    assert b'credential-sample' not in queue.path.read_bytes()


def test_wrapped_cooldown_remains_available():
    cause = RuntimeError('Do not persist raw provider response')
    cause.retry_after = 45
    outer = RuntimeError('CLI wrapper')
    outer.__cause__ = cause
    assert retry_hint(outer) == 45
    cause.__cause__ = outer
    cause.retry_after = float('nan')
    assert retry_hint(outer) is None


def test_dry_run_preserves_database_bytes_and_does_not_deliver(queued):
    pf, ticket, queue = queued
    before = queue.path.read_bytes()
    result = drain_retries(pf, now=100, dry_run=True, deliver=lambda *args: pytest.fail('network'))
    assert result['planned'] == [ticket.id]
    assert queue.path.read_bytes() == before


def test_changed_repository_is_rejected_before_network(queued):
    pf, ticket, queue = queued
    (pf.store.base_dir / 'github.planfile.yaml').write_text(
        'integrations:\n  github:\n    repo: other/repo\n'
    )
    result = drain_retries(pf, now=100, deliver=lambda *args: pytest.fail('wrong repository'))
    assert result['failed'] == [ticket.id]
    assert queue.entries()[0]['state'] == 'failed'


def test_changed_payload_is_refreshed_before_delivery(queued):
    pf, ticket, queue = queued
    pf.update_ticket(ticket.id, description='Current version')
    result = drain_retries(pf, max_tickets=1, now=100,
                           deliver=lambda *args: pytest.fail('stale payload'))
    assert result['refreshed'] == [ticket.id]
    assert queue.entries()[0]['revision'] == 2
    assert queue.entries()[0]['state'] == 'pending'


def test_bounded_delivery_retains_newer_edits_and_unrelated_jobs(queued):
    pf, ticket, queue = queued
    other = pf.create_ticket('Unrelated', integration=['github'])
    queue.enqueue('owner/repo', other.id, other.model_dump(mode='json'), now=101)
    def deliver(pf, current, repo):
        assert current.id == ticket.id and repo == 'owner/repo'
        pf.update_ticket(current.id, description='Edited during request')
        return OutboundSyncResult(succeeded=(current.id,))
    result = drain_retries(pf, max_tickets=1, now=101, deliver=deliver)
    assert not result['succeeded']
    assert result['refreshed'] == [ticket.id]
    assert all(row['state'] == 'pending' for row in queue.entries())


def test_missing_success_proof_cannot_acknowledge_job(queued):
    pf, ticket, queue = queued
    result = drain_retries(pf, now=100, deliver=lambda *args: OutboundSyncResult())
    assert result['failed'] == [ticket.id]
    assert queue.entries()[0]['state'] == 'failed'


def test_verified_result_clears_only_that_job(queued):
    pf, ticket, queue = queued
    result = drain_retries(pf, now=100,
                           deliver=lambda pf, t, repo: OutboundSyncResult(succeeded=(t.id,)))
    assert result['succeeded'] == [ticket.id]
    assert queue.entries()[0]['state'] == 'succeeded'
    assert queue.claim(now=500) is None


@pytest.mark.parametrize('count', [0, 101, -1])
def test_batch_limit_is_mandatory(queued, count):
    with pytest.raises(ValueError, match='batch_invalid'):
        drain_retries(queued[0], max_tickets=count)


def test_lost_creation_response_replays_same_issue_with_native_backend(queued, monkeypatch):
    from test_sync_lifecycle_readback import backend

    pf, ticket, queue = queued
    remote = backend()
    create = remote.repo.create_issue
    def lost_response(**fields):
        create(**fields)
        raise RuntimeError("response lost after provider accepted create")
    remote.repo.create_issue = lost_response
    monkeypatch.setattr('planfile.cli.groups.sync.core._initialize_backend', lambda *args: remote)
    first = drain_retries(pf, max_tickets=1, now=100)
    assert first['failed'] == [ticket.id]
    assert remote.repo.creates == 1
    remote.repo.create_issue = create
    assert drain_retries(pf, max_tickets=1, now=129)['succeeded'] == []
    recovered = drain_retries(pf, max_tickets=1, now=131)
    assert recovered['succeeded'] == [ticket.id]
    assert remote.repo.creates == 1
    assert queue.entries()[0]['state'] == 'succeeded'
