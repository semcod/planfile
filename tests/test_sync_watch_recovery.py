"""Recovery scenarios for explicitly authorized file-watch delivery."""
import os

import pytest
import typer
from typer.testing import CliRunner

from planfile.cli.groups.sync import commands
from planfile.integrations.config import IntegrationConfig


@pytest.fixture
def watcher(tmp_path, monkeypatch):
    root = tmp_path / '.planfile'
    root.mkdir()
    ticket = root / 'ticket.yaml'
    ticket.write_text('name: original\n')
    state = {'clock': 0, 'ticks': 0, 'calls': [], 'limit': 25, 'on_tick': None, 'on_sync': None}
    monkeypatch.setattr(IntegrationConfig, 'load_configs', lambda self: None)
    monkeypatch.setattr(commands.time, 'monotonic', lambda: state['clock'])

    def sleep(seconds):
        state['clock'] += seconds
        state['ticks'] += 1
        if state['on_tick']:
            state['on_tick'](state['ticks'])
        if state['ticks'] >= state['limit']:
            raise KeyboardInterrupt

    def sync(integration, directory, dry_run, direction, **kwargs):
        assert dry_run is False
        assert integration == 'github'
        assert directory == str(tmp_path)
        assert direction == 'to'
        state['calls'].append((state['clock'], ticket.read_text()))
        if state['on_sync']:
            state['on_sync'](len(state['calls']))

    monkeypatch.setattr(commands.time, 'sleep', sleep)
    monkeypatch.setattr(commands, 'sync_integration', sync)
    state['run'] = lambda: commands.watch_cmd(str(tmp_path), 5, ['github'], 'to', False)
    state['ticket'] = ticket
    state['root'] = root
    return state


def test_reconcile_existing_changes_on_startup(watcher):
    watcher['run']()
    assert watcher['calls'] == [(0, 'name: original\n')]


def test_retry_startup_failure_without_another_file_edit(watcher):
    def fail_first(number):
        if number == 1:
            raise RuntimeError('controlled outage')
    watcher['on_sync'] = fail_first
    watcher['run']()
    assert [clock for clock, _ in watcher['calls']] == [0, 30]


def test_changed_batch_failure_does_not_acknowledge_files(watcher):
    def edit(tick):
        if tick == 1:
            watcher['ticket'].write_text('name: changed\n')
    def fail_second(number):
        if number == 2:
            raise RuntimeError('controlled outage')
    watcher.update(on_tick=edit, on_sync=fail_second)
    watcher['run']()
    assert watcher['calls'] == [(0, 'name: original\n'), (5, 'name: changed\n'), (35, 'name: changed\n')]


def test_provider_cooldown_survives_wrapped_exception(watcher, capsys):
    class ProviderError(Exception):
        retry_after = 90
    def fail_first(number):
        if number == 1:
            try:
                raise ProviderError('credential-must-not-appear')
            except ProviderError as error:
                raise RuntimeError('credential-must-not-appear') from error
    watcher['on_sync'] = fail_first
    watcher['run']()
    assert [clock for clock, _ in watcher['calls']] == [0, 90]
    assert 'credential-must-not-appear' not in capsys.readouterr().out


def test_edit_during_delivery_remains_pending_with_preserved_mtime(watcher):
    def edit_during_sync(number):
        if number == 1:
            stamp = watcher['ticket'].stat()
            watcher['ticket'].write_text('name: changed!\n')
            os.utime(watcher['ticket'], ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    watcher['on_sync'] = edit_during_sync
    watcher['run']()
    assert watcher['calls'] == [(0, 'name: original\n'), (5, 'name: changed!\n')]


def test_yml_content_change_detected_with_preserved_mtime(tmp_path):
    path = tmp_path / 'ticket.yml'
    path.write_text('name: before\n')
    before = commands._get_planfile_dir_states(tmp_path)
    stamp = path.stat()
    path.write_text('name: after!\n')
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert commands._detect_changes(before, commands._get_planfile_dir_states(tmp_path))


def test_watch_interval_cannot_busy_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(commands, "sync_integration", lambda *args, **kwargs: None)
    (tmp_path / '.planfile').mkdir()
    app = typer.Typer()
    app.command('watch')(commands.watch_cmd)
    result = CliRunner().invoke(app, [str(tmp_path), '--interval', '0', '--once'])
    assert result.exit_code == 2


def test_failed_partial_batch_retries_even_if_local_content_reverts(watcher):
    def edit(tick):
        if tick == 1:
            watcher['ticket'].write_text('name: changed\n')
        elif tick == 2:
            watcher['ticket'].write_text('name: original\n')
    def fail_second(number):
        if number == 2:
            raise RuntimeError('one remote may already have accepted changed content')
    watcher.update(on_tick=edit, on_sync=fail_second)
    watcher['run']()
    assert watcher['calls'] == [(0, 'name: original\n'), (5, 'name: changed\n'), (35, 'name: original\n')]
