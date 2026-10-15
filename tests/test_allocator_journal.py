import json
from pathlib import Path

import pytest

from planfile import Planfile
from planfile.core.allocator_journal import JournalHighwater


def append(path, number):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps({'event': {'ticket_id': 'PLF-' + str(number)}}) + '\n')


def test_cache_survives_new_instance_and_invalidates_external_changes(tmp_path, monkeypatch):
    path = tmp_path / 'events/operations.jsonl'
    append(path, 900)
    cache = JournalHighwater(path)
    assert cache.highwater('PLF') == 900
    original = Path.open
    def guarded(self, *args, **kwargs):
        if self == path:
            raise AssertionError('warm cache reread journal')
        return original(self, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        assert JournalHighwater(path).highwater('PLF') == 900
    append(path, 950)
    assert cache.highwater('PLF') == 950
    path.write_text(json.dumps({'event': {'ticket_id': 'PLF-975'}}) + '\n')
    assert cache.highwater('PLF') == 975
    replacement = path.with_suffix('.new')
    append(replacement, 999)
    replacement.replace(path)
    assert cache.highwater('PLF') == 999


def test_corrupt_cache_rebuilt_and_full_journal_not_row_capped(tmp_path):
    path = tmp_path / 'events/operations.jsonl'
    append(path, 1000001)
    path.write_text(path.read_text() + 'not json\n[]\nnull\n')
    cache = JournalHighwater(path)
    assert cache.highwater('PLF') == 1000001
    cache.cache.write_text('{broken')
    assert cache.highwater('PLF') == 1000001
    data = json.loads(cache.cache.read_text())
    data['highs']['PLF'] = 0
    cache.cache.write_text(json.dumps(data))
    assert cache.highwater('PLF') == 1000001


def test_locked_appends_maintain_cache_without_journal_scan(tmp_path, monkeypatch):
    pf = Planfile(tmp_path)
    pf.store.init()
    first = pf.create_ticket('first')
    journal = pf.store._operations_path
    assert JournalHighwater(journal).highwater('PLF') == int(first.id.split('-')[-1])
    original = Path.open
    def guarded(self, mode='r', *args, **kwargs):
        if self == journal and mode == 'r':
            raise AssertionError('allocation reread operations journal')
        return original(self, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    second = Planfile(tmp_path).create_ticket('second')
    assert second.id != first.id
    assert JournalHighwater(journal).highwater('PLF') == int(second.id.split('-')[-1])


def test_failed_cache_publication_is_reconstructed(tmp_path, monkeypatch):
    path = tmp_path / 'events/operations.jsonl'
    append(path, 45)
    cache = JournalHighwater(path)
    assert cache.highwater('PLF') == 45
    before = cache.current()
    line = json.dumps({'event': {'ticket_id': 'PLF-77'}}) + '\n'
    with path.open('a') as stream:
        stream.write(line)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', lambda *a, **k: (_ for _ in ()).throw(OSError('disk failure')))
        cache.appended(before, [{'ticket_id': 'PLF-77'}], len(line.encode()))
    assert JournalHighwater(path).highwater('PLF') == 77


def test_changed_journal_during_scan_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / 'events/operations.jsonl'
    append(path, 45)
    cache = JournalHighwater(path)
    original = cache.signature
    calls = []
    def changed():
        calls.append(1)
        value = original()
        if len(calls) > 1:
            value[2] += 1
        return value
    monkeypatch.setattr(cache, 'signature', changed)
    with pytest.raises(RuntimeError, match='changed'):
        cache.highwater('PLF')


def test_deleted_id_stays_reserved_after_cache_and_config_rollback(tmp_path):
    pf = Planfile(tmp_path)
    pf.store.init()
    append(pf.store._operations_path, 800)
    assert JournalHighwater(pf.store._operations_path).highwater('PLF') == 800
    config = pf.store._read_config()
    config['next_id'] = 1
    pf.store._write_config(config)
    assert Planfile(tmp_path).create_ticket('after rollback').id == 'PLF-801'


def test_multiple_prefixes_and_non_ascii_append(tmp_path):
    path = tmp_path / 'events/operations.jsonl'
    cache = JournalHighwater(path)
    assert cache.highwater('PLF') == 0
    cached = cache.current()
    event = {'ticket_id': 'MY-PREFIX-90', 'text': 'zażółć'}
    payload = json.dumps({'event': event}, ensure_ascii=False) + '\n'
    path.parent.mkdir(parents=True)
    path.write_text(payload)
    cache.appended(cached, [event], len(payload.encode()))
    assert cache.highwater('MY-PREFIX') == 90
    assert cache.highwater('PLF') == 0


def test_same_size_rewrite_with_restored_mtime_invalidates_cache(tmp_path):
    import os

    path = tmp_path / 'events/operations.jsonl'
    append(path, 100)
    cache = JournalHighwater(path)
    assert cache.highwater('PLF') == 100
    stat = path.stat()
    path.write_text(path.read_text().replace('PLF-100', 'PLF-999'))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size
    assert cache.highwater('PLF') == 999
