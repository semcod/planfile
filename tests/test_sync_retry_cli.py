"""Operator-visible retry state and explicit, bounded worker activation."""

import json
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.groups.sync import register_sync_commands
from planfile.cli.groups.ticket import register_ticket_commands
from planfile.sync.retry import RetryQueue


def app():
    root = typer.Typer()
    register_sync_commands(root)
    register_ticket_commands(root)
    return root


def test_implicit_failure_is_visible_after_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    (pf.store.base_dir / 'github.planfile.yaml').write_text(
        'integrations:\n  github:\n    repo: owner/repo\n'
    )
    with patch('planfile.cli.groups.ticket.commands._auto_sync',
               side_effect=RuntimeError('private-provider-token')):
        result = CliRunner().invoke(app(), ['ticket', 'create', 'Offline'])
    assert result.exit_code == 0
    shown = CliRunner().invoke(app(), ['ticket', 'show', 'PLF-001', '--format', 'json'])
    data = json.loads(shown.stdout)
    assert data['sync_retry'][0]['state'] == 'failed'
    assert data['sync_retry'][0]['last_error'] == 'RuntimeError'
    assert 'private-provider-token' not in shown.stdout
    assert data['status'] == 'open'
    with patch('planfile.cli.groups.sync.core._initialize_backend') as backend:
        status = CliRunner().invoke(app(), ['sync', 'retry', '--status'])
    assert status.exit_code == 0
    assert json.loads(status.stdout)['jobs'][0]['state'] == 'failed'
    backend.assert_not_called()


def test_no_sync_and_sync_dry_run_do_not_enqueue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    (pf.store.base_dir / 'github.planfile.yaml').write_text(
        'integrations:\n  github:\n    repo: owner/repo\n'
    )
    with patch('planfile.cli.groups.ticket.commands._auto_sync'):
        runner = CliRunner()
        assert runner.invoke(app(), ['ticket', 'create', 'Local', '--no-sync']).exit_code == 0
        assert runner.invoke(app(), ['ticket', 'create', 'Preview', '--sync-dry-run']).exit_code == 0
    assert not RetryQueue(pf.store.base_dir).path.exists()


def test_worker_failure_exits_nonzero_and_batches_are_bounded(tmp_path):
    with patch('planfile.sync.retry.drain_retries', return_value={
        'planned': [], 'succeeded': [], 'failed': ['PLF-001'], 'refreshed': []
    }) as drain:
        result = CliRunner().invoke(app(), ['sync', 'retry', str(tmp_path), '--max-tickets', '3'])
    assert result.exit_code == 1
    assert drain.call_args.kwargs == {'max_tickets': 3, 'dry_run': False}


def test_dry_run_does_not_sleep_or_deliver(tmp_path):
    with patch('planfile.sync.retry.drain_retries', return_value={
        'planned': ['PLF-001'], 'succeeded': [], 'failed': [], 'refreshed': []
    }) as drain, patch('planfile.cli.groups.sync.commands.time.sleep') as sleep:
        result = CliRunner().invoke(app(), ['sync', 'retry', str(tmp_path), '--dry-run', '--cycles', '2'])
    assert result.exit_code == 0
    assert drain.call_count == 2
    assert all(call.kwargs['dry_run'] for call in drain.call_args_list)
    sleep.assert_not_called()
