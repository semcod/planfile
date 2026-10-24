from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from planfile.core.store import PlanfileStore, Store, Ticket
from planfile.sync import operations
from planfile.sync.base import TicketState
from planfile.sync.generic import GenericBackend
from planfile.sync.outbound import OutboundSyncError
from planfile.sync.priority import normalize_inbound_priority


class PartialBackend:
    config = {"repo": "owner/repo"}

    def __init__(self):
        self.created: list[str] = []

    def create_ticket(self, payload):
        local_id = payload["metadata"]["planfile_id"]
        self.created.append(local_id)
        if local_id.endswith(":bad"):
            raise RuntimeError("controlled provider failure")
        return SimpleNamespace(
            id=local_id,
            url=f"https://github.com/owner/repo/issues/{local_id}",
            key=f"owner/repo#{local_id}",
        )


class LostResponseBackend:
    config = {"repo": "owner/repo"}

    def __init__(self, matches):
        self.matches = matches
        self.create_calls = 0
        self.search_calls: list[str] = []

    def create_ticket(self, payload):
        self.create_calls += 1
        raise RuntimeError("connection lost after provider commit")

    def search_tickets(self, query):
        self.search_calls.append(query)
        return self.matches


class ReadbackBackend(PartialBackend):
    def __init__(self, title: str = "PLF-1"):
        super().__init__()
        self.readbacks = 0
        self.title = title

    def create_ticket(self, payload):
        local_id = payload["metadata"]["planfile_id"]
        self.created.append(local_id)
        return SimpleNamespace(
            id="42",
            url="https://github.com/owner/repo/issues/42",
            key="owner/repo#42",
        )

    def get_ticket(self, remote_id):
        self.readbacks += 1
        return SimpleNamespace(
            id=str(remote_id),
            name=self.title,
            url="https://github.com/owner/repo/issues/42",
            key="owner/repo#42",
        )


def _store(tmp_path):
    store = Store(tmp_path)
    store.init()
    return store


def _ticket(ticket_id: str) -> dict:
    return {
        "id": ticket_id,
        "name": ticket_id,
        "description": "safe body",
        "status": "open",
        "integration": ["github"],
    }


def test_legacy_operations_uses_fail_closed_batch_result(tmp_path):
    store = _store(tmp_path)
    backend = PartialBackend()

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("good", _ticket("good")), ("bad", _ticket("bad"))],
            False,
            store,
            "github",
        )

    result = caught.value.result
    assert result.succeeded == ("good",)
    assert result.created == ("good",)
    assert result.failed == ("bad",)
    assert result.to_dict() == {
        "created": ["good"],
        "reused": [],
        "updated": [],
        "failed": ["bad"],
        "planned": [],
        "succeeded": ["good"],
    }


def test_lost_create_response_recovers_one_marker_without_retrying_create(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket("PLF-1")
    remote = SimpleNamespace(
        id="42",
        url="https://github.com/owner/repo/issues/42",
        key="owner/repo#42",
    )
    backend = LostResponseBackend([remote])

    result = operations.sync_to_external(
        backend,
        [("PLF-1", ticket)],
        False,
        store,
        "github",
    )

    assert result.reused == ("PLF-1",)
    assert result.created == ()
    assert backend.create_calls == 1
    assert backend.search_calls == ["PLF-1"]
    assert ticket["sync"]["github"]["id"] == "42"
    receipt = tmp_path / ".planfile" / "sync" / "github.receipts.jsonl"
    assert '"outcome": "succeeded"' in receipt.read_text()


def test_ambiguous_lost_create_is_failed_and_never_retried(tmp_path):
    store = _store(tmp_path)
    backend = LostResponseBackend(
        [
            {"id": "41", "url": "https://github.com/owner/repo/issues/41"},
            {"id": "42", "url": "https://github.com/owner/repo/issues/42"},
        ]
    )

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("PLF-1", _ticket("PLF-1"))],
            False,
            store,
            "github",
        )

    assert caught.value.result.failed == ("PLF-1",)
    assert backend.create_calls == 1
    assert backend.search_calls == ["PLF-1"]


def test_successful_create_requires_matching_provider_readback_when_available(tmp_path):
    store = _store(tmp_path)
    backend = ReadbackBackend()

    result = operations.sync_to_external(
        backend,
        [("PLF-1", _ticket("PLF-1"))],
        False,
        store,
        "github",
    )

    assert result.created == ("PLF-1",)
    assert backend.readbacks == 1


def test_readback_mismatch_is_failed_closed(tmp_path):
    store = _store(tmp_path)
    backend = ReadbackBackend(title="unexpected remote title")

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("PLF-1", _ticket("PLF-1"))],
            False,
            store,
            "github",
        )

    assert caught.value.result.failed == ("PLF-1",)
    assert len(backend.created) == 1


def test_find_local_ticket_deduplicates_same_local_id_across_sprints(tmp_path):
    ticket_payload = {
        "sync": {
            "github": {"id": "174", "key": "semcod/koru#174"}
        }
    }
    sections = {
        "history-2026-09-02": {"tickets": {"STARTER-601": ticket_payload}},
        "history-2026-09-16": {"tickets": {"STARTER-601": ticket_payload}},
        "current": {"tickets": {}},
    }
    sync_state = operations.SyncState(tmp_path, "github", repository="semcod/koru")

    sprint_id, planfile_id, ticket = operations._find_local_ticket(
        sections, "174", sync_state, "github"
    )

    assert planfile_id == "STARTER-601"
    assert sprint_id in ("history-2026-09-02", "history-2026-09-16")
    assert ticket == ticket_payload


def test_find_local_ticket_prefers_current_sprint(tmp_path):
    ticket_payload = {
        "sync": {
            "github": {"id": "174", "key": "semcod/koru#174"}
        }
    }
    sections = {
        "history-2026-09-02": {"tickets": {"STARTER-601": ticket_payload}},
        "current": {"tickets": {"STARTER-601": ticket_payload}},
    }
    sync_state = operations.SyncState(tmp_path, "github", repository="semcod/koru")

    sprint_id, planfile_id, ticket = operations._find_local_ticket(
        sections, "174", sync_state, "github"
    )

    assert planfile_id == "STARTER-601"
    assert sprint_id == "current"


def test_find_local_ticket_raises_on_genuinely_ambiguous_local_ids(tmp_path):
    sections = {
        "history-2026-09-02": {"tickets": {"STARTER-601": {"sync": {"github": {"id": "174"}}}}},
        "history-2026-09-16": {"tickets": {"STARTER-602": {"sync": {"github": {"id": "174"}}}}},
    }
    sync_state = operations.SyncState(tmp_path, "github", repository="semcod/koru")

    with pytest.raises(ValueError, match="ambiguous local mapping for remote ticket 174"):
        operations._find_local_ticket(sections, "174", sync_state, "github")


class UpdateReadbackBackend(ReadbackBackend):
    def update_ticket(self, ticket_id, **kwargs):
        pass


def test_failed_update_readback_does_not_count_as_succeeded(tmp_path):
    store = _store(tmp_path)
    backend = UpdateReadbackBackend(title='unexpected remote title')
    ticket = _ticket('PLF-1')
    ticket['sync'] = {'github': {'id': '42', 'repository': 'owner/repo'}}
    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(backend, [('PLF-1', ticket)], False, store, 'github')
    assert caught.value.result.failed == ('PLF-1',)
    assert caught.value.result.succeeded == ()
    assert caught.value.result.updated == ()
    assert caught.value.result.created == ()


def test_preserved_title_policy_cannot_waive_create_readback(tmp_path):
    backend = ReadbackBackend(title='unexpected remote title')
    backend.preserves_remote_titles = True
    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(backend, [('PLF-1', _ticket('PLF-1'))], False,
                                    _store(tmp_path), 'github')
    assert caught.value.result.failed == ('PLF-1',)
    assert caught.value.result.succeeded == ()
    assert caught.value.result.updated == ()
    assert caught.value.result.created == ()


def test_missing_mapping_replacement_still_checks_create_title(tmp_path):
    class MissingUpdateBackend(ReadbackBackend):
        preserves_remote_titles = True

        def update_ticket(self, ticket_id, **kwargs):
            raise RuntimeError('404 Not Found')

    backend = MissingUpdateBackend(title='unexpected replacement title')
    ticket = _ticket('PLF-1')
    ticket['sync'] = {'github': {'id': '19', 'repository': 'owner/repo'}}
    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(backend, [('PLF-1', ticket)], False,
                                    _store(tmp_path), 'github')
    assert caught.value.result.failed == ('PLF-1',)
    assert caught.value.result.succeeded == ()
    assert caught.value.result.updated == ()
    assert caught.value.result.created == ()
    assert len(backend.created) == 1


def test_preserved_title_update_still_rejects_wrong_remote_identity(tmp_path):
    class WrongIdentityBackend(UpdateReadbackBackend):
        preserves_remote_titles = True

        def get_ticket(self, remote_id):
            state = super().get_ticket(remote_id)
            state.id = '999'
            return state

    ticket = _ticket('PLF-1')
    ticket['sync'] = {'github': {'id': '42', 'repository': 'owner/repo'}}
    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(WrongIdentityBackend(), [('PLF-1', ticket)], False,
                                    _store(tmp_path), 'github')
    assert caught.value.result.failed == ('PLF-1',)
    assert caught.value.result.succeeded == ()
    assert caught.value.result.updated == ()
    assert caught.value.result.created == ()


# Synthetic reproduction of semcod/planfile#278 observed during intake of
# https://github.com/paxlet-com/willman/issues/298. No operational backlog used.
PRIORITY_CASES = [
    ({'priority': 'critical'}, 'critical'),
    ({'priority': 'high'}, 'high'),
    ({'priority': 'normal'}, 'normal'),
    ({'priority': 'low'}, 'low'),
    ({'priority': ' MeDiUm '}, 'normal'),
    ({'priority': 'med'}, 'normal'),
    ({'labels': ['priority-high']}, 'high'),
    ({'labels': ['priority:high']}, 'high'),
    ({'labels': ['priority: high']}, 'high'),
    ({'labels': ['priority::high']}, 'high'),
    ({'labels': [' PRIORITY:: MeDiuM ']}, 'normal'),
    ({'labels': ['priority-med']}, 'normal'),
    ({'labels': ['unrelated']}, 'normal'),
    ({}, 'normal'),
    ({'priority': 'HIGH', 'labels': ['priority-high', 'priority: high']}, 'high'),
    ({'priority': 'normal', 'labels': ['priority-medium', 'priority::med']}, 'normal'),
]
INVALID_PRIORITIES = [
    {'priority': 'urgent'}, {'priority': ''}, {'priority': '  '},
    {'priority': None}, {'priority': 3}, {'priority': False},
    {'priority': ['high']}, {'priority': {'name': 'high'}},
    {'labels': ['priority-urgent']}, {'labels': ['priority::']},
    {'labels': ['priority:high', 'priority-low']},
    {'priority': 'normal', 'labels': ['priority-high']},
    {'labels': 'priority-high'}, {'labels': [None]},
]


def inbound_record(**evidence):
    return dict(id='298', name='synthetic inbound reproduction', status='open',
                assignee=None, description='semcod/planfile#278 / paxlet-com/willman#298',
                labels=[], **{k: v for k, v in evidence.items() if k != 'labels'}) | (
                    {'labels': evidence['labels']} if 'labels' in evidence else {})


@pytest.mark.parametrize('evidence,expected', PRIORITY_CASES)
def test_shared_priority_normalization(evidence, expected):
    assert normalize_inbound_priority(inbound_record(**evidence)) == expected


@pytest.mark.parametrize('evidence', INVALID_PRIORITIES)
def test_priority_diagnostic_names_ticket_and_evidence(evidence):
    with pytest.raises(ValueError, match=r'inbound_priority_(invalid|conflict): ticket 298:'):
        normalize_inbound_priority(inbound_record(**evidence))


def inbound_fixture(tmp_path, mode, record):
    store = PlanfileStore(tmp_path)
    store.init()
    if mode == 'sharded':
        store.migrate_to_sharded_yaml()
    backend = SimpleNamespace(config={'repo': 'fixture/repo'},
                              list_tickets=lambda **_: [record])
    source = tmp_path / 'source.yaml'
    v1 = {'sprint': {'tickets': {}}, 'backlog': {'tickets': {}}}
    kwargs = {}
    target = store
    if mode == 'legacy':
        # Compatibility adapter with no typed create/update SDK.
        target = SimpleNamespace(base_dir=store.base_dir,
                                 load_sprint=store.load_sprint,
                                 load_backlog=store.load_backlog,
                                 save_sprint=store.save_sprint,
                                 save_backlog=store.save_backlog)
    elif mode == 'v1':
        source.write_text(yaml.safe_dump(v1))
        kwargs = {"v1_source_file": source, "v1_data": v1}
    return store, target, backend, source, kwargs


def physical_import(store, mode, source):
    if mode == 'v1':
        return yaml.safe_load(source.read_text())['backlog']['tickets'].get('GITHUB-298')
    path = (store._sharded_storage().shard_path('backlog', 'GITHUB-298')
            if mode == 'sharded' else store._sprint_file('backlog'))
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text())
    return data.get('sprint', data).get('tickets', {}).get('GITHUB-298')


@pytest.mark.parametrize('mode', ['legacy', 'v1', 'yaml', 'sharded'])
@pytest.mark.parametrize('evidence,expected', PRIORITY_CASES)
def test_fresh_import_persists_priority_before_typed_readback(tmp_path, mode, evidence, expected):
    store, target, backend, source, kwargs = inbound_fixture(
        tmp_path, mode, inbound_record(**evidence))
    operations.sync_from_external(backend, target, False, 'github', **kwargs)
    raw = physical_import(store, mode, source)
    assert raw is not None
    assert 'priority' in raw  # Model defaults must never hide an omitted field.
    assert raw['priority'] == expected
    assert raw['status'] == 'open'
    typed = (Ticket.model_validate(raw) if mode == 'v1' else
             PlanfileStore(tmp_path).get_ticket('GITHUB-298', repair_index=False))
    assert typed.priority == expected
    assert typed.description == raw['description']
    assert typed.description.splitlines()[0] == 'semcod/planfile#278 / paxlet-com/willman#298'


@pytest.mark.parametrize('mode', ['legacy', 'v1', 'yaml', 'sharded'])
@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('evidence', INVALID_PRIORITIES)
def test_rejected_import_has_diagnostic_and_no_record_or_mapping(
    tmp_path, mode, dry_run, evidence, monkeypatch,
):
    store, target, backend, source, kwargs = inbound_fixture(
        tmp_path, mode, inbound_record(**evidence))
    messages = []
    monkeypatch.setattr(operations.console, 'print', lambda *args, **_: messages.append(str(args)))
    if mode in {'yaml', 'sharded'}:
        with pytest.raises(ValueError, match='inbound_priority_'):
            operations.sync_from_external(backend, target, dry_run, 'github', **kwargs)
    else:
        operations.sync_from_external(backend, target, dry_run, 'github', **kwargs)
    assert any('inbound_priority_' in message and '298' in message for message in messages)
    assert not any('Would import:' in message for message in messages)
    assert physical_import(store, mode, source) is None
    state = operations.SyncState(store.base_dir, 'github', 'fixture/repo')
    assert state.get_local_id('298') is None


@pytest.mark.parametrize('evidence', [{}, {'priority': 'high'}, {'priority': None},
                                       {'priority': ['malformed']},
                                       {'priority': {'name': 'high'}}])
def test_priority_evidence_survives_generic_typed_and_dictionary_transport(evidence):
    backend = GenericBackend('https://example.invalid', session=Mock())
    record = inbound_record(**evidence)
    backend._make_request = Mock(return_value=record)
    state = backend.get_ticket('298')
    assert isinstance(state, TicketState)
    for transported in [record, state, TicketState.model_validate(state.model_dump())]:
        extracted = operations._extract_ticket_data(transported)
        assert ('priority' in extracted) == ('priority' in evidence)
        if 'priority' in evidence:
            assert extracted['priority'] == evidence['priority']
        else:
            assert normalize_inbound_priority(extracted) == 'normal'


@pytest.mark.parametrize('evidence', [
    {'priority': 'high'}, {'priority': None},
    {'labels': ['priority-high']}, {},
    {'priority': 'low', 'labels': ['priority-high']},
])
@pytest.mark.parametrize('duplicate', [False, True])
def test_legacy_update_and_duplicate_import_preserve_local_priority(evidence, duplicate):
    record = inbound_record(**evidence)
    backlog = {'tickets': {'GITHUB-298': dict(inbound_record(), id='GITHUB-298',
                                            priority='critical', sprint='backlog')}}
    state = SimpleNamespace(save_sync=Mock())
    if duplicate:
        assert operations._import_new_ticket(backlog, record, 'github', state, 0) == 0
        state.save_sync.assert_called_once_with({'GITHUB-298': '298'})
    else:
        operations._update_local_ticket(backlog, {}, 'GITHUB-298', record, 0, 'github', None)
    assert backlog['tickets']['GITHUB-298']['priority'] == 'critical'
