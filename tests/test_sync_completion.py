"""Opted-in local completion events feed the existing authorized retry worker."""

import os

import pytest
from fastapi.testclient import TestClient

from planfile import Planfile
from planfile.api import server
from planfile.core.store import TicketUpdatedAtConflictError
from planfile.sync.outbound import OutboundSyncResult
from planfile.sync.retry import RetryQueue, drain_retries


def enable(pf, value=True):
    pf.configuration.set_many({
        'integrations.github.repo': 'owner/repo',
        'integrations.github.sync.enqueue_on_done': value,
    })


@pytest.fixture(params=['yaml', 'sharded-yaml'])
def context(tmp_path, request):
    pf = Planfile(str(tmp_path))
    if request.param == 'sharded-yaml':
        pf.store.migrate_to_sharded_yaml(shard_size=100)
    return pf, RetryQueue(pf.store.base_dir)


def test_sdk_completion_enqueues_locally_without_loading_credentials(context, monkeypatch):
    pf, queue = context
    enable(pf)
    name = 'PLANFILE_COMPLETION_TEST_ENV'
    monkeypatch.delenv(name, raising=False)
    (pf.store.project_dir / '.env').write_text(f'{name}=changed\n')
    from planfile.sync.github import GitHubBackend
    monkeypatch.setattr(GitHubBackend, '__init__', lambda *a, **k: pytest.fail('network'))
    ticket = pf.create_ticket('Complete', integration=['github'])
    completed = pf.update_ticket(ticket.id, status='done', expected_updated_at=ticket.updated_at)
    assert completed.status == 'done'
    assert os.environ.get(name) is None
    assert queue.entries(ticket.id)[0]['state'] == 'pending'
    assert queue.entries(ticket.id)[0]['repository'] == 'owner/repo'


def test_api_completion_uses_same_queue(context, monkeypatch):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('API completion', integration=['github'])
    monkeypatch.setattr(server, 'get_planfile', lambda: pf)
    response = TestClient(server.app).post(f'/tickets/{ticket.id}/complete', json={})
    assert response.status_code == 200
    assert queue.entries(ticket.id)[0]['state'] == 'pending'


@pytest.mark.parametrize('policy', [False, None])
def test_disabled_or_absent_policy_never_creates_queue(context, policy):
    pf, queue = context
    if policy is not None:
        enable(pf, policy)
    ticket = pf.create_ticket('Local only', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    assert not queue.path.exists()


@pytest.mark.parametrize('integration,status', [([], 'done'), (['github'], 'blocked'), (['github'], 'canceled')])
def test_only_explicitly_routed_done_tickets_enqueue(context, integration, status):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('Not a completion', integration=integration)
    pf.update_ticket(ticket.id, status=status)
    assert not queue.path.exists()


def test_stale_cas_cannot_enqueue_completion(context):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('CAS guarded', integration=['github'])
    pf.update_ticket(ticket.id, priority='high')
    with pytest.raises(TicketUpdatedAtConflictError):
        pf.update_ticket(ticket.id, status='done', expected_updated_at=ticket.updated_at)
    assert not queue.path.exists()


def test_worker_recovers_missed_event_after_restart(context):
    pf, queue = context
    ticket = pf.create_ticket('Missed event', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    enable(pf)
    restarted = Planfile(str(pf.store.project_dir))
    calls = []
    def deliver(pf, current, repo):
        calls.append((current.id, repo))
        return OutboundSyncResult(succeeded=(current.id,))
    result = drain_retries(restarted, max_tickets=1, deliver=deliver)
    assert result['succeeded'] == [ticket.id]
    assert calls == [(ticket.id, 'owner/repo')]
    assert queue.entries(ticket.id)[0]['state'] == 'succeeded'
    assert not drain_retries(restarted, max_tickets=1, deliver=lambda *a: pytest.fail('duplicate'))['succeeded']


def test_recovery_dry_run_plans_missing_event_without_writes(context):
    pf, queue = context
    ticket = pf.create_ticket('Dry run recovery', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    enable(pf)
    result = drain_retries(pf, dry_run=True, deliver=lambda *a: pytest.fail('network'))
    assert result['planned'] == [ticket.id]
    assert not queue.path.exists()


def test_recovery_does_not_reset_failed_cooldown(context):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('Retry later', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    job = queue.claim(now=10**12)
    assert queue.finish(job, error='TimeoutError', retry_after=240, now=10**12)
    result = drain_retries(pf, now=10**12 + 1, deliver=lambda *a: pytest.fail('cooldown'))
    assert not result['succeeded']
    entry = queue.entries(ticket.id)[0]
    assert entry['next_attempt_at'] == 10**12 + 240
    assert entry['attempts'] == 1


def test_older_ack_cannot_clear_completion_edit(context):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('Newer edit', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    job = queue.claim(now=10**12)
    pf.update_ticket(ticket.id, description='Edited after completion')
    assert not queue.finish(job, now=10**12 + 1)
    assert queue.entries(ticket.id)[0]['revision'] == 2
    assert queue.entries(ticket.id)[0]['state'] == 'pending'


def test_enqueue_failure_warns_local_commit_and_worker_recovers(context, monkeypatch):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('Durable crash gap', integration=['github'])
    enqueue = RetryQueue.enqueue
    def fail(*args, **kwargs):
        raise OSError('private error detail')
    monkeypatch.setattr(RetryQueue, 'enqueue', fail)
    with pytest.warns(RuntimeWarning, match='local ticket committed') as warning:
        completed = pf.update_ticket(ticket.id, status='done')
    assert completed.status == 'done'
    assert 'private error detail' not in str(warning[0].message)
    assert pf.get_ticket(ticket.id).status == 'done'
    monkeypatch.setattr(RetryQueue, 'enqueue', enqueue)
    result = drain_retries(pf, deliver=lambda pf, t, repo: OutboundSyncResult(succeeded=(t.id,)))
    assert result['succeeded'] == [ticket.id]
    assert queue.entries(ticket.id)[0]['state'] == 'succeeded'


def test_worker_reconciliation_failure_is_visible_and_sanitized(context, monkeypatch):
    pf, _ = context
    ticket = pf.create_ticket('Worker failure', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    enable(pf)
    def fail(*args, **kwargs):
        raise OSError('private error detail')
    monkeypatch.setattr(RetryQueue, 'enqueue', fail)
    with pytest.raises(RuntimeError, match='^sync_completion_reconcile_failed$'):
        drain_retries(pf, deliver=lambda *a: pytest.fail('network'))
    assert pf.get_ticket(ticket.id).status == 'done'


def test_recovery_scan_cannot_replace_newer_completion_revision(context, monkeypatch):
    pf, queue = context
    ticket = pf.create_ticket('Scan race', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    enable(pf)
    original = pf.list_tickets
    def race(**kwargs):
        stale = original(**kwargs)
        pf.update_ticket(ticket.id, description='New revision after snapshot')
        return stale
    monkeypatch.setattr(pf, 'list_tickets', race)
    seen = []
    def deliver(pf, current, repo):
        seen.append(current.description)
        return OutboundSyncResult(succeeded=(current.id,))
    result = drain_retries(pf, max_tickets=1, deliver=deliver)
    assert result['succeeded'] == [ticket.id]
    assert seen == ['New revision after snapshot']
    assert queue.entries(ticket.id)[0]['revision'] == 1


def test_typed_policy_rejects_non_boolean_values(context):
    pf, _ = context
    with pytest.raises(ValueError, match='boolean_required'):
        enable(pf, ['not a boolean'])


def test_new_content_cannot_bypass_existing_provider_cooldown(context, monkeypatch):
    pf, queue = context
    enable(pf)
    ticket = pf.create_ticket('Changed during provider cooldown', integration=['github'])
    pf.update_ticket(ticket.id, status='done')
    job = queue.claim(now=10**12)
    assert queue.finish(job, error='RuntimeError', retry_after=240, now=10**12)
    monkeypatch.setattr('planfile.sync.retry.time.time', lambda: 10**12 + 1)
    pf.update_ticket(ticket.id, description='New accepted content')
    row = queue.entries(ticket.id)[0]
    assert row['revision'] == 2
    assert row['next_attempt_at'] == 10**12 + 240
    assert row['attempts'] == 1
    assert row['last_error'] == 'RuntimeError'
    pf.update_ticket(ticket.id, description='Another accepted content edit')
    assert queue.entries(ticket.id)[0]['revision'] == 3
    assert queue.entries(ticket.id)[0]['next_attempt_at'] == 10**12 + 240
    assert queue.claim(now=10**12 + 239) is None
    retry = queue.claim(now=10**12 + 240)
    assert retry['revision'] == 3 and retry['attempts'] == 2
