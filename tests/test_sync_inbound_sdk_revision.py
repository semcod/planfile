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
    def concurrent():
        other = PlanfileStore(store.project_dir)
        other.create_ticket(Ticket(id='GITHUB-123', name='other owner', sprint=destination,
                                   description='preserve this identity',
                                   execution={'state': 'running', 'assigned_to': 'other',
                                              'lease_expires_at': '2099-01-01T00:00:00Z'}))
    with pytest.raises(ValueError, match='ticket_already_exists'):
        pull(store, concurrent, sprint_ids=['custom-review'])
    after = read(store, 'GITHUB-123')
    assert after.name == 'other owner'
    assert after.description == 'preserve this identity'
    assert after.sprint == destination
    assert after.execution.assigned_to == 'other'
