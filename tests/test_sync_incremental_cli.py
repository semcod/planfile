"""Explicit incremental CLI authority and provider-free previews."""

import json
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.groups.sync import register_sync_commands


def app():
    root = typer.Typer()
    register_sync_commands(root)
    return root


def test_incremental_dry_run_scopes_exact_ticket_without_backend(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.configuration.set_many({'integrations.github.repo': 'owner/repo'})
    ticket = pf.create_ticket('Preview', integration=['github'])
    pf.create_ticket('Other', integration=['github'])
    with patch('planfile.cli.groups.sync.core._initialize_backend') as backend:
        result = CliRunner().invoke(app(), ['sync', 'github', str(tmp_path), '--incremental', '--direction', 'to', '--ticket', ticket.id, '--dry-run'])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output[result.output.index('{'):])
    assert data['planned'] == [ticket.id]
    backend.assert_not_called()
    assert not (pf.store.base_dir / 'sync/github.retry.sqlite3').exists()


@pytest.mark.parametrize('direction', ['both', 'from', 'invalid'])
def test_incremental_rejects_unsupported_direction_before_backend(tmp_path, direction):
    with patch('planfile.cli.groups.sync.core._initialize_backend') as backend:
        result = CliRunner().invoke(app(), ['sync', 'github', str(tmp_path), '--incremental', '--direction', direction])
    assert result.exit_code == 1
    backend.assert_not_called()
    assert not (tmp_path / '.planfile').exists()


def test_incremental_is_explicit_bounded_and_reports_failure(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.configuration.set_many({'integrations.github.repo': 'owner/repo'})
    pf.create_ticket('Queued', integration=['github'])
    with patch('planfile.sync.incremental.sync_incremental', return_value={'failed': ['PLF-001']}) as worker:
        result = CliRunner().invoke(app(), ['sync', 'github', str(tmp_path), '--incremental', '--direction', 'to', '--max-tickets', '3'])
    assert result.exit_code == 1
    assert worker.call_args.kwargs['max_tickets'] == 3


def test_legacy_v1_incremental_fails_without_creating_store(tmp_path):
    (tmp_path / 'legacy.planfile.yaml').write_text('sprint:\n  tickets: {}\n')
    with patch('planfile.cli.groups.sync.core._initialize_backend') as backend:
        result = CliRunner().invoke(app(), ['sync', 'github', str(tmp_path), '--incremental', '--direction', 'to'])
    assert result.exit_code == 1
    backend.assert_not_called()
    assert not (tmp_path / '.planfile').exists()
