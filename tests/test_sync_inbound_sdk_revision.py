from types import SimpleNamespace

import pytest

from planfile.core.store import PlanfileStore, Ticket, TicketUpdatedAtConflictError
from planfile.sync.operations import sync_from_external


@pytest.fixture(params=[False, True], ids=['yaml', 'sharded'])
def store(tmp_path, request):
    result = PlanfileStore(tmp_path)
    result.init()
    result.create_ticket(Ticket(id='PLF-001', name='fixture', description='old',
                               status='open', sprint='backlog', integration=['github'],
                               sync={'github': {'id': '123', 'url': 'https://github.com/fixture/repo/issues/123',
                                                'repository': 'fixture/repo'}}))
    if request.param:
        result.migrate_to_sharded_yaml()
    return result


def pull(store, callback=None, **scope):
    class Backend:
        config = {'repo': 'fixture/repo'}
        def list_tickets(self, **kwargs):
            if callback:
                callback()
            return [SimpleNamespace(id='123', name='fixture', description='remote update',
                                    status='closed', assignee=None, labels=[],
                                    metadata={'state_reason': 'completed'}, key=None,
                                    url='https://github.com/fixture/repo/issues/123')]
    sync_from_external(Backend(), store, False, 'github', **scope)


def read(store, ident='PLF-001'):
    return PlanfileStore(store.project_dir).get_ticket(ident, repair_index=False)


def test_public_inbound_change_advances_sdk_revision(store):
    before = read(store)
    pull(store)
    after = read(store)
    assert after.status == 'done'
    assert after.description == 'remote update'
    assert after.updated_at != before.updated_at


def test_pre_inbound_sdk_cas_cannot_overwrite_remote_description(store):
    before = read(store)
    pull(store)
    with pytest.raises(TicketUpdatedAtConflictError):
        store.update_ticket('PLF-001', expected_updated_at=before.updated_at,
                            description='stale local writer')
    assert read(store).description == 'remote update'


def test_selected_concurrent_update_rejected_instead_of_silent_bulk_overwrite(store):
    def concurrent():
        store.update_ticket('PLF-001', description='concurrent writer',
                            execution={'state': 'running', 'assigned_to': 'other',
                                       'lease_expires_at': '2099-01-01T00:00:00Z'})
    with pytest.raises(ValueError):
        pull(store, concurrent)
    after = read(store)
    assert after.description == 'concurrent writer'
    assert after.execution.state == 'running'
    assert after.execution.assigned_to == 'other'
    assert after.execution.lease_expires_at


def test_snapshot_guard_also_rejects_raw_mutation_with_unchanged_revision(store):
    def concurrent():
        data = store.load_backlog()
        data['tickets']['PLF-001']['description'] = 'same timestamp writer'
        store.save_backlog(data)
    with pytest.raises(ValueError):
        pull(store, concurrent)
    assert read(store).description == 'same timestamp writer'


def test_unselected_concurrent_update_is_preserved(store):
    store.create_ticket(Ticket(id='PLF-002', name='unselected', sprint='backlog'))
    def concurrent():
        store.update_ticket('PLF-002', description='concurrent unselected',
                            execution={'state': 'running', 'assigned_to': 'other',
                                       'lease_expires_at': '2099-01-01T00:00:00Z'})
    pull(store, concurrent, ticket_ids=['PLF-001'])
    assert read(store).status == 'done'
    other = read(store, 'PLF-002')
    assert other.description == 'concurrent unselected'
    assert other.execution.assigned_to == 'other'


def test_deleted_selected_ticket_cannot_be_resurrected_from_import_snapshot(store):
    with pytest.raises(ValueError):
        pull(store, lambda: store.delete_ticket('PLF-001'))
    assert read(store) is None


def test_identical_import_preserves_revision_and_history(store):
    pull(store)
    before = read(store).model_dump(mode='json')
    pull(store)
    assert read(store).model_dump(mode='json') == before


def test_remote_closure_cannot_release_live_execution_lease(store):
    store.update_ticket('PLF-001', status='in_progress',
                        execution={'state': 'running', 'assigned_to': 'other',
                                   'lease_expires_at': '2099-01-01T00:00:00Z'})
    before = read(store).model_dump(mode='json')
    with pytest.raises(ValueError, match='execution_reconciliation'):
        pull(store)
    assert read(store).model_dump(mode='json') == before


def test_new_custom_sprint_import_gets_native_sdk_revision_without_bulk_save(store):
    store.save_sprint('custom-review', {'id': 'custom-review', 'tickets': {}})
    original = read(store).model_dump(mode='json')
    pull(store, sprint_ids=['custom-review'])
    imported = read(store, 'GITHUB-123')
    assert imported is not None
    assert imported.sprint == 'custom-review'
    assert imported.updated_at
    assert imported.sync['github']['id'] == '123'
    assert read(store).model_dump(mode='json') == original


@pytest.mark.parametrize('destination', ['custom-review', 'backlog'])
def test_new_import_cannot_overwrite_concurrent_identity_in_any_sprint(store, destination):
    store.save_sprint('custom-review', {'id': 'custom-review', 'tickets': {}})
    concurrent_record = {}
    def concurrent():
        other = PlanfileStore(store.project_dir)
        other.create_ticket(Ticket(id='GITHUB-123', name='other owner', sprint=destination,
                                   description='preserve this identity',
                                   execution={'state': 'running', 'assigned_to': 'other',
                                              'lease_expires_at': '2099-01-01T00:00:00Z'}))
        concurrent_record.update(read(other, 'GITHUB-123').model_dump(mode='json'))
    with pytest.raises(ValueError, match='ticket_already_exists'):
        pull(store, concurrent, sprint_ids=['custom-review'])
    after = read(store, 'GITHUB-123')
    assert after.name == 'other owner'
    # Creation may append an optional ticket-radar advisory. Compare the full
    # persisted record to the pre-import observation, including that advisory.
    assert after.model_dump(mode='json') == concurrent_record
    assert after.sprint == destination
    assert after.execution.assigned_to == 'other'


def physical_ticket(store, ticket_id='GITHUB-298'):
    """Bypass typed defaults and YAML mirrors when asserting persistence."""
    import yaml
    path = (store._sharded_storage().shard_path('backlog', ticket_id)
            if store._uses_sharded_storage() else store._sprint_file('backlog'))
    data = yaml.safe_load(path.read_text())
    return data.get('sprint', data)['tickets'][ticket_id]


def seed_missing_priority(store, *, labels=None, status='in_progress'):
    """Synthetic legacy imported record; never touches an operational backlog."""
    from copy import deepcopy
    raw = {'id': 'GITHUB-298', 'name': 'willman#298 synthetic legacy repair',
               'description': 'semcod/planfile#278; backlog repair is not execution',
               'status': status, 'sprint': 'backlog', 'assignee': 'original-owner',
               'backend': 'github', 'external_id': '298', 'integration': ['github'],
               'labels': ['priority-high'] if labels is None else labels,
               'sync': {'github': {'id': '298', 'repository': 'fixture/repo'}},
               'execution': {'state': 'running', 'assigned_to': 'lease-owner',
                          'lease_expires_at': '2099-01-01T00:00:00Z', 'attempt': 2},
               'history': [{'event': 'previous audit event'}]}
    data = store.load_backlog()
    data['tickets']['GITHUB-298'] = deepcopy(raw)
    store.save_backlog(data)
    return deepcopy(physical_ticket(store))


def project_files(store):
    return {str(path.relative_to(store.project_dir)): path.read_bytes()
            for path in store.project_dir.rglob('*') if path.is_file()}


def test_selected_repair_preview_raw_cas_audit_and_idempotence(store, monkeypatch):
    from contextlib import contextmanager
    from unittest.mock import Mock

    from planfile.sync import completion
    from planfile.sync.priority import apply_priority_repair, preview_priority_repair
    before = seed_missing_priority(store)
    assert 'priority' not in before
    assert read(store, 'GITHUB-298').priority == 'normal'  # The original masking bug.
    files_before = project_files(store)
    plan = preview_priority_repair(store, ['GITHUB-298'])
    assert project_files(store) == files_before
    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.ticket_id == 'GITHUB-298'
    assert item.priority == 'high'
    assert item.evidence == {'labels': ['priority-high']}
    assert item.expected_snapshot == before
    assert item.diagnostic is None
    assert read(store).priority == 'normal'  # Unselected record untouched.

    original_lock = store.mutation_lock
    lock_observations = []
    @contextmanager
    def observed_lock(**kwargs):
        with original_lock(**kwargs):
            lock_observations.append(True)
            yield
    monkeypatch.setattr(store, 'mutation_lock', observed_lock)
    original_update = store.update_ticket
    updates = Mock(wraps=original_update)
    monkeypatch.setattr(store, 'update_ticket', updates)
    enqueue = Mock(side_effect=AssertionError('running repair must not enqueue completion'))
    monkeypatch.setattr(completion, 'enqueue_completion', enqueue)
    assert apply_priority_repair(store, plan, actor='repair:test', reason='issue #278') == ['GITHUB-298']
    assert lock_observations
    updates.assert_called_once_with('GITHUB-298', expected_snapshot=before,
                                    priority='high', actor='repair:test', reason='issue #278')
    after = physical_ticket(store)
    assert after['priority'] == 'high'
    assert read(store, 'GITHUB-298').priority == 'high'
    for key in before:
        if key not in {'history', 'updated_at'}:
            assert after[key] == before[key], key
    assert after['history'][:-1] == before['history']
    assert after['history'][-1]['actor'] == 'repair:test'
    assert after['history'][-1]['reason'] == 'issue #278'
    assert after['history'][-1]['changes'] == ['priority']
    enqueue.assert_not_called()
    files_after = project_files(store)
    again = preview_priority_repair(store, ['GITHUB-298'])
    assert again.items[0].priority is None
    assert apply_priority_repair(store, again, actor='repair:test', reason='repeat') == []
    assert project_files(store) == files_after
    with pytest.raises(ValueError, match='stale_ticket_snapshot'):
        apply_priority_repair(store, plan, actor='repair:test', reason='stale retry')


@pytest.mark.parametrize('mutation', ['description', 'priority', 'execution', 'deleted'])
def test_repair_rejects_stale_raw_snapshot_without_overwriting(store, mutation):
    from planfile.sync.priority import apply_priority_repair, preview_priority_repair
    seed_missing_priority(store)
    plan = preview_priority_repair(store, ['GITHUB-298'])
    if mutation == 'deleted':
        store.delete_ticket('GITHUB-298')
    else:
        raw = store.load_backlog()
        raw['tickets']['GITHUB-298'][mutation] = {
            'description': 'another writer', 'priority': 'low',
            'execution': {'state': 'running', 'assigned_to': 'new owner'},
        }[mutation]
        store.save_backlog(raw)  # Intentionally leaves updated_at unchanged.
    before = project_files(store)
    with pytest.raises(ValueError, match='stale_ticket_snapshot|ticket_disappeared'):
        apply_priority_repair(store, plan, actor='repair:test', reason='stale preview')
    # A rejected mutation may refresh an index but cannot rewrite any ticket.
    if mutation == 'deleted':
        assert read(store, 'GITHUB-298') is None
    else:
        expected = store.load_backlog()['tickets']['GITHUB-298']
        assert physical_ticket(store) == expected
    for path, data in before.items():
        if path.endswith('.yaml'):
            assert (store.project_dir / path).read_bytes() == data


@pytest.mark.parametrize('labels', [[], ['priority-medium'], ['priority::med'],
                                    ['priority-unknown'], ['priority-high', 'priority-low']])
def test_selected_repair_uses_shared_boundary_and_blocks_diagnostics(store, labels):
    from planfile.sync.priority import apply_priority_repair, preview_priority_repair
    seed_missing_priority(store, labels=labels)
    before = project_files(store)
    plan = preview_priority_repair(store, ['GITHUB-298'])
    item = plan.items[0]
    if labels and ('unknown' in labels[0] or len(labels) > 1):
        assert 'inbound_priority_' in item.diagnostic
        with pytest.raises(ValueError, match='priority_repair_diagnostics'):
            apply_priority_repair(store, plan, actor='repair:test', reason='invalid')
        assert project_files(store) == before
    else:
        assert item.priority == 'normal'
        apply_priority_repair(store, plan, actor='repair:test', reason='default or alias')
        assert physical_ticket(store)['priority'] == 'normal'


def test_repair_requires_selection_and_diagnoses_unknown_native_and_duplicate_ids(store):
    from planfile.sync.priority import apply_priority_repair, preview_priority_repair
    for selection in [[], None, 'GITHUB-298', ['']]:
        with pytest.raises(ValueError, match='selection_required'):
            preview_priority_repair(store, selection)
    seed_missing_priority(store)
    data = store.load_backlog()
    data['tickets']['PLF-native'] = {'id': 'PLF-native', 'name': 'not imported', 'status': 'open'}
    store.save_backlog(data)
    plan = preview_priority_repair(store, ['missing', 'PLF-native', 'GITHUB-298'])
    assert plan.items[0].diagnostic
    assert 'not_imported' in plan.items[1].diagnostic
    with pytest.raises(ValueError, match='priority_repair_diagnostics'):
        apply_priority_repair(store, plan, actor='repair:test', reason='blocked selection')
    assert 'priority' not in physical_ticket(store)
    store.save_sprint('duplicate', {'id': 'duplicate', 'tickets': {
        'GITHUB-298': dict(physical_ticket(store))}})
    assert 'matches=2' in preview_priority_repair(store, ['GITHUB-298']).items[0].diagnostic


@pytest.mark.parametrize('evidence', [
    {'priority': 'high'}, {'priority': None}, {'labels': ['priority-high']}, {},
    {'priority': 'low', 'labels': ['priority-high']},
])
@pytest.mark.parametrize('duplicate', [False, True])
def test_typed_update_and_duplicate_preserve_local_priority_and_audit(store, evidence, duplicate):
    from unittest.mock import Mock

    from planfile.sync.operations import _import_new_ticket
    store.update_ticket('PLF-001', priority='critical', actor='fixture', reason='local schedule')
    local = store.load_backlog()['tickets']['PLF-001']
    remote = {'id': '123', 'name': 'fixture', 'description': 'remote update', 'status': 'open',
                  'assignee': None, 'labels': []}
    remote.update(evidence)
    if duplicate:
        remote['id'] = '001'
        backend_state = SimpleNamespace(save_sync=Mock())
        store.create_ticket(Ticket(id='GITHUB-001', name='duplicate', priority='critical',
                                   sprint='backlog'))
        backlog = store.load_backlog()
        _import_new_ticket(backlog, remote, 'github', backend_state, 0, store=store)
        assert read(store, 'GITHUB-001').priority == 'critical'
    else:
        backend = SimpleNamespace(config={'repo': 'fixture/repo'},
                                  list_tickets=lambda **_: [SimpleNamespace(**remote)])
        sync_from_external(backend, store, False, 'github')
        after = read(store)
        assert after.priority == 'critical'
        assert all('priority' not in event.get('changes', [])
                   for event in after.history[len(local['history']):])


@pytest.mark.parametrize('status', ['open', 'in_progress', 'review', 'done', 'canceled', 'failed', 'blocked'])
def test_priority_only_repair_preserves_terminal_and_execution_fields_without_remote_calls(
    store, status, monkeypatch,
):
    from unittest.mock import Mock

    import requests

    from planfile.sync import completion
    from planfile.sync.priority import apply_priority_repair, preview_priority_repair

    before = seed_missing_priority(store, status=status)
    remote = Mock(side_effect=AssertionError('repair must remain local'))
    monkeypatch.setattr(requests.Session, 'request', remote)
    monkeypatch.setattr(completion, 'reconcile_completions', remote)
    plan = preview_priority_repair(store, ['GITHUB-298'])
    assert plan.items[0].diagnostic is None
    apply_priority_repair(store, plan, actor='repair:test', reason='priority only')
    after = physical_ticket(store)
    assert after['priority'] == 'high'
    assert after['status'] == before['status']
    assert after['execution'] == before['execution']
    assert after['assignee'] == before['assignee']
    assert after['sync'] == before['sync']
    remote.assert_not_called()


def test_repair_preview_does_not_create_missing_indexes_or_yaml_mirrors(store):
    from planfile.sync.priority import preview_priority_repair

    seed_missing_priority(store)
    for path in store.project_dir.rglob('*.fast.json'):
        path.unlink()
    fresh = PlanfileStore(store.project_dir)
    before = project_files(fresh)
    plan = preview_priority_repair(fresh, ['GITHUB-298'])
    assert plan.items[0].priority == 'high'
    assert project_files(fresh) == before


def test_pre_existing_append_only_evidence_does_not_block_inbound_update(store):
    store.append_ticket_evidence(
        'PLF-001',
        idempotency_key='pre-sync-ev-1',
        collection='receipts',
        evidence={'ok': True},
        reason='pre-sync evidence',
        actor='agent:test',
    )
    pull(store)
    after = read(store)
    assert after.status == 'done'
    assert after.description == 'remote update'
    assert after.outputs.result['receipts'][0]['idempotency_key'] == 'pre-sync-ev-1'


def test_concurrent_append_only_evidence_during_fetch_still_rejected(store):
    before = read(store)

    def concurrent():
        store.append_ticket_evidence(
            'PLF-001',
            idempotency_key='during-fetch-ev-1',
            collection='receipts',
            evidence={'ok': True},
            reason='concurrent evidence during fetch',
            actor='agent:test',
        )

    with pytest.raises(TicketUpdatedAtConflictError):
        pull(store, concurrent)
    after = read(store)
    assert after.status == 'open'
    assert after.description == before.description
    assert 'remote update' not in after.description
    assert after.outputs.result['receipts'][0]['idempotency_key'] == 'during-fetch-ev-1'


def test_duplicate_history_ticket_id_with_evidence_freezes_canonical_sprint(tmp_path, monkeypatch):
    store = PlanfileStore(tmp_path)
    store.init()
    older = {
        'id': 'history-2026-10-03',
        'tickets': {
            'TEST-001-REPAIR': {
                'id': 'TEST-001-REPAIR',
                'name': 'Older repair snapshot',
                'status': 'done',
                'sprint': 'history-2026-10-03',
                'description': 'older snapshot',
                'sync': {'github': {'id': '777', 'repository': 'fixture/repo'}},
                'updated_at': '2026-10-03T10:35:33+00:00',
            }
        },
    }
    newer = {
        'id': 'history-2026-10-05',
        'tickets': {
            'TEST-001-REPAIR': {
                'id': 'TEST-001-REPAIR',
                'name': 'Newer repair snapshot',
                'status': 'done',
                'sprint': 'history-2026-10-05',
                'description': 'newer snapshot',
                'sync': {'github': {'id': '777', 'repository': 'fixture/repo'}},
                'updated_at': '2026-10-05T19:44:25+00:00',
            }
        },
    }
    store.save_sprint('history-2026-10-03', older)
    store.save_sprint('history-2026-10-05', newer)
    store.append_ticket_evidence(
        'TEST-001-REPAIR',
        idempotency_key='ev-dup-1',
        collection='receipts',
        evidence={'ok': True},
        reason='pre-sync evidence on duplicated ticket',
        actor='agent:test',
    )
    monkeypatch.setattr(
        store,
        '_ticket_lookup_sprints',
        lambda _tid: ['current', 'history-2026-10-05', 'history-2026-10-03'],
    )

    class Backend:
        config = {'repo': 'fixture/repo'}

        def list_tickets(self, **_kwargs):
            return [SimpleNamespace(
                id='777',
                name='Newer repair snapshot',
                description='updated via canonical sprint',
                status='closed',
                assignee=None,
                labels=[],
                metadata={'state_reason': 'completed'},
                key=None,
                url='https://github.com/fixture/repo/issues/777',
            )]

    sync_from_external(Backend(), store, False, 'github')
    refreshed = store.load_sprint('history-2026-10-05')
    assert refreshed['tickets']['TEST-001-REPAIR']['description'] == 'updated via canonical sprint'


def test_isolate_ticket_conflicts_quarantines_lease_and_preserves_across_empty_incremental(store):
    import yaml

    store.update_ticket(
        'PLF-001',
        status='in_progress',
        execution={'state': 'running', 'assigned_to': 'other', 'lease_expires_at': '2099-01-01T00:00:00Z'},
    )
    store.create_ticket(
        Ticket(
            id='PLF-002',
            name='sibling open ticket',
            description='ready to close',
            status='open',
            sprint='backlog',
            integration=['github'],
            sync={'github': {'id': '124', 'url': 'https://github.com/fixture/repo/issues/124',
                             'repository': 'fixture/repo'}},
        )
    )

    responses = [
        [
            SimpleNamespace(
                id='123', name='fixture', description='remote update', status='closed',
                assignee=None, labels=[], metadata={'state_reason': 'completed'}, key=None,
                url='https://github.com/fixture/repo/issues/123',
            ),
            SimpleNamespace(
                id='124', name='sibling open ticket', description='sibling closed remotely', status='closed',
                assignee=None, labels=[], metadata={'state_reason': 'completed'}, key=None,
                url='https://github.com/fixture/repo/issues/124',
            ),
        ],
        [],
    ]

    class Backend:
        config = {'repo': 'fixture/repo'}

        def list_tickets(self, since=None, **_kwargs):
            return responses.pop(0)

    backend = Backend()
    sync_from_external(backend, store, False, 'github', isolate_ticket_conflicts=True)

    # Leased PLF-001 untouched; sibling PLF-002 closed; cursor + quarantine persisted.
    plf1 = read(store, 'PLF-001')
    plf2 = read(store, 'PLF-002')
    assert plf1.status == 'in_progress'
    assert plf1.execution.assigned_to == 'other'
    assert plf2.status == 'done'

    state_file = store.project_dir / '.planfile' / 'sync' / 'github.state.yaml'
    st1 = yaml.safe_load(state_file.read_text(encoding='utf-8'))
    assert st1.get('inbound_cursor_at')
    assert len(st1.get('quarantined_inbound_tickets') or []) == 1
    assert st1['quarantined_inbound_tickets'][0]['local_id'] == 'PLF-001'
    assert st1['quarantined_inbound_tickets'][0]['remote_id'] == '123'

    # Follow-up incremental 0-delta run MUST preserve unresolved quarantine reminders.
    sync_from_external(backend, store, False, 'github', isolate_ticket_conflicts=True)
    st2 = yaml.safe_load(state_file.read_text(encoding='utf-8'))
    assert len(st2.get('quarantined_inbound_tickets') or []) == 1
    assert st2['quarantined_inbound_tickets'][0]['local_id'] == 'PLF-001'


def test_isolate_ticket_conflicts_quarantines_invalid_priority_while_default_fails_closed(store):
    import yaml

    issues = [
        SimpleNamespace(
            id='901', name='bad priority', description='invalid label', status='open',
            assignee=None, labels=['priority:urgent'], metadata={}, key=None,
            url='https://github.com/fixture/repo/issues/901',
        ),
        SimpleNamespace(
            id='902', name='valid sibling', description='valid priority', status='open',
            assignee=None, labels=['priority:P1'], metadata={}, key=None,
            url='https://github.com/fixture/repo/issues/902',
        ),
    ]

    class Backend:
        config = {'repo': 'fixture/repo'}

        def list_tickets(self, since=None, **_kwargs):
            return list(issues)

    with pytest.raises(ValueError, match='inbound_priority_invalid'):
        sync_from_external(Backend(), store, False, 'github')

    sync_from_external(Backend(), store, False, 'github', isolate_ticket_conflicts=True)

    assert read(store, 'GITHUB-901') is None
    imported = read(store, 'GITHUB-902')
    assert imported is not None
    assert imported.priority == 'high'

    state_file = store.project_dir / '.planfile' / 'sync' / 'github.state.yaml'
    st = yaml.safe_load(state_file.read_text(encoding='utf-8'))
    assert st.get('inbound_cursor_at')
    quarantined = st.get('quarantined_inbound_tickets') or []
    assert len(quarantined) == 1
    assert quarantined[0]['remote_id'] == '901'
    assert 'inbound_priority_invalid' in quarantined[0]['reason']
