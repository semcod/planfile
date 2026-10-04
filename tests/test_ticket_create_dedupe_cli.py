"""CLI occurrence capture must share the store's atomic dedupe boundary."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.groups.ticket import register_ticket_commands
from planfile.sync.retry import RetryQueue


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    root = typer.Typer()
    register_ticket_commands(root)
    return pf, root


def create(root, name, *options):
    return CliRunner().invoke(root, ['ticket', 'create', name, *options])


def test_reuse_appends_description_without_overwriting_original(cli):
    pf, root = cli
    assert create(root, 'Original', '--dedupe-key', 'gate:build', '-d', 'First', '--no-sync').exit_code == 0
    result = create(root, 'Another occurrence', '--dedupe-key', 'gate:build', '-d', 'Second failure', '--no-sync')
    assert result.exit_code == 0, result.output
    assert 'Reused PLF-001' in result.output
    ticket = pf.get_ticket('PLF-001')
    assert ticket.name == 'Original'
    assert ticket.description == 'First'
    assert ticket.labels == ['dedupe:gate:build']
    assert ticket.outputs.notes == ['Second failure']
    assert len(pf.list_tickets(sprint='all')) == 1


def test_reuse_uses_name_when_description_is_empty(cli):
    pf, root = cli
    assert create(root, 'First', '--dedupe-key', 'gate', '--no-sync').exit_code == 0
    assert create(root, 'New occurrence', '--dedupe-key', 'gate', '--no-sync').exit_code == 0
    assert pf.get_ticket('PLF-001').outputs.notes == ['New occurrence']


@pytest.mark.parametrize('terminal', ['done', 'canceled'])
def test_terminal_owner_releases_key(cli, terminal):
    pf, root = cli
    first = pf.create_ticket_deduplicated('Old', dedupe_key='gate')[0]
    pf.update_ticket(first.id, status=terminal)
    result = create(root, 'New incident', '--dedupe-key', 'gate', '--no-sync')
    assert result.exit_code == 0, result.output
    assert 'Created PLF-002' in result.output
    assert pf.get_ticket(first.id).outputs is None


def test_reuse_preserves_original_sprint_and_integration(cli):
    pf, root = cli
    first = pf.create_ticket_deduplicated('Original', dedupe_key='gate', sprint='previous', integration=['github'])[0]
    pf.create_ticket('Unrelated')
    (pf.store.base_dir / 'github.planfile.yaml').write_text('integrations:\n  github:\n    repo: owner/repo\n')
    with patch('planfile.cli.groups.ticket.commands._auto_sync') as sync:
        result = create(root, 'Repeat', '--dedupe-key', 'gate', '--sync-dry-run', '-s', 'current', '-i', 'markdown')
    assert result.exit_code == 0, result.output
    assert sync.call_args.args[1] == ['github']
    assert sync.call_args.kwargs['ticket_ids'] == [first.id]
    assert sync.call_args.kwargs['sprint_ids'] == ['previous']
    ticket = pf.get_ticket(first.id)
    assert ticket.integration == ['github']
    assert ticket.sprint == 'previous'
    assert not RetryQueue(pf.store.base_dir).path.exists()


def test_reuse_local_ticket_does_not_inherit_new_remote_config(cli):
    pf, root = cli
    first = pf.create_ticket_deduplicated('Local', dedupe_key='gate')[0]
    (pf.store.base_dir / 'github.planfile.yaml').write_text('integrations:\n  github:\n    repo: owner/repo\n')
    with patch('planfile.cli.groups.ticket.commands._auto_sync') as sync:
        result = create(root, 'Repeat', '--dedupe-key', 'gate')
    assert result.exit_code == 0, result.output
    sync.assert_not_called()
    assert pf.get_ticket(first.id).integration is None
    assert not RetryQueue(pf.store.base_dir).path.exists()


@pytest.mark.parametrize('key', ['', '   '])
def test_empty_key_fails_without_creating_ticket(cli, key):
    pf, root = cli
    result = create(root, 'Invalid', '--dedupe-key', key, '--no-sync')
    assert result.exit_code == 2
    assert pf.list_tickets(sprint='all') == []


def test_parallel_cli_processes_preserve_every_occurrence(tmp_path):
    Planfile(str(tmp_path))
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))

    def invoke(index):
        return subprocess.run([sys.executable, '-m', 'planfile.cli', 'ticket', 'create',
                               f'Occurrence {index}', '--dedupe-key', 'shared', '--no-sync'],
                              cwd=tmp_path, env=env, text=True, capture_output=True, timeout=60)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(invoke, range(4)))
    assert all(r.returncode == 0 for r in results), [(r.stdout, r.stderr) for r in results]
    tickets = Planfile(str(tmp_path)).list_tickets(sprint='all')
    assert len(tickets) == 1
    ticket = tickets[0]
    assert sorted([ticket.name, *ticket.outputs.notes]) == [f'Occurrence {i}' for i in range(4)]


def test_api_note_append_preserves_other_outputs(cli):
    pf, _ = cli
    first, _ = pf.create_ticket_deduplicated('First', dedupe_key='key', outputs={'notes': ['prior'], 'artifacts': ['build.log'], 'result': {'ok': True}})
    reused, created = pf.create_ticket_deduplicated('Second', dedupe_key='key', dedupe_note='new occurrence')
    assert not created
    assert reused.id == first.id
    assert reused.outputs.notes == ['prior', 'new occurrence']
    assert reused.outputs.artifacts == ['build.log']
    assert reused.outputs.result == {'ok': True}
