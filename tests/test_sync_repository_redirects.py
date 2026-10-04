"""Provider identity, rather than local aliases, owns redirect migration."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
import yaml

from planfile import Planfile
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import _backend_repository, _validate_ticket_binding
from planfile.sync.outbound import sync_to_external
from planfile.sync.state import SyncState, SyncStateRepositoryMismatch


class MetadataRequester:
    def __init__(self):
        self.data = {
            '/repos/owner/old': {'id': 123, 'full_name': 'owner/new'},
            '/repos/owner/new': {'id': 123, 'full_name': 'owner/new'},
            '/repositories/123': {'id': 123, 'full_name': 'owner/new'},
            '/repos/other/repo': {'id': 999, 'full_name': 'other/repo'},
            '/repositories/999': {'id': 999, 'full_name': 'other/repo'},
        }
        self.calls = []

    def requestJsonAndCheck(self, verb, path):
        assert verb == 'GET'
        self.calls.append(path)
        value = self.data[path]
        if isinstance(value, Exception):
            raise value
        return {}, deepcopy(value)


class RedirectBackend(GitHubBackend):
    def __init__(self, configured='owner/old'):
        self.config = {'repo': configured}
        self._identity_requester = MetadataRequester()
        self.repo = SimpleNamespace(full_name='owner/new')
        self.mutations = []

    def update_ticket(self, ticket_id, **kwargs):
        self.mutations.append(str(ticket_id))

    def create_ticket(self, ticket):
        raise AssertionError('A renamed repository must retain its existing mapping')

    def get_ticket(self, remote_id):
        return SimpleNamespace(id=str(remote_id), name='Original', status='open',
                               key=f'owner/new#{remote_id}', url=f'https://github.com/owner/new/issues/{remote_id}')


def bound_state(tmp_path, **extra):
    s = SyncState(tmp_path / '.planfile', 'github', repository='owner/old')
    s.save_sync({'PLF-001': '42'})
    if extra:
        raw = yaml.safe_load(s.state_file.read_text())
        raw.update(extra)
        s.state_file.write_text(yaml.safe_dump(raw))
    return s


def test_verified_redirect_migrates_legacy_binding_and_keeps_mapping(tmp_path):
    old = bound_state(tmp_path, token='test')
    b = RedirectBackend()
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    raw = s.get_last_sync()
    assert raw['repository'] == 'owner/new'
    assert raw['repository_id'] == '123'
    assert raw['repository_aliases'] == ['owner/old']
    assert raw['ticket_map'] == {'PLF-001': '42'}
    assert 'token' not in raw
    assert _backend_repository(b) == 'owner/new'
    _validate_ticket_binding({'id': 'PLF-001', 'sync': {'github': {'repository': 'owner/old'}}}, 'github', b)
    assert old.state_file == s.state_file


def test_config_changed_to_canonical_requires_previous_name_proof(tmp_path):
    bound_state(tmp_path)
    b = RedirectBackend(configured='owner/new')
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert s.get_remote_id('PLF-001') == '42'
    assert '/repos/owner/old' in b._identity_requester.calls


@pytest.mark.parametrize('recorded_id', ['999', 'invalid'])
def test_repository_id_conflict_retains_original_bytes(tmp_path, recorded_id):
    old = bound_state(tmp_path, repository_id=recorded_id)
    before = old.state_file.read_bytes()
    b = RedirectBackend()
    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert old.state_file.read_bytes() == before
    assert b.mutations == []


def test_reused_old_name_cannot_migrate_legacy_state(tmp_path):
    old = bound_state(tmp_path)
    before = old.state_file.read_bytes()
    b = RedirectBackend('owner/new')
    b._identity_requester.data['/repos/owner/old'] = {'id': 999, 'full_name': 'other/repo'}
    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert old.state_file.read_bytes() == before
    assert b.mutations == []


def test_local_alias_is_not_proof_of_an_unrelated_repository(tmp_path):
    old = bound_state(tmp_path, repository_aliases=['other/repo'])
    b = RedirectBackend('other/repo')
    before = old.state_file.read_bytes()
    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert old.state_file.read_bytes() == before


def test_unverified_alias_does_not_authorize_ticket_reference(tmp_path):
    bound_state(tmp_path, repository_aliases=['other/repo'])
    b = RedirectBackend()
    SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    with pytest.raises(ValueError):
        _validate_ticket_binding({'id': 'PLF-001', 'sync': {'github': {'repository': 'other/repo'}}}, 'github', b)


def test_metadata_failure_retains_original_bytes(tmp_path):
    old = bound_state(tmp_path)
    b = RedirectBackend()
    b._identity_requester.data['/repos/owner/old'] = RuntimeError('metadata unavailable')
    before = old.state_file.read_bytes()
    with pytest.raises(RuntimeError, match='metadata unavailable'):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert old.state_file.read_bytes() == before
    assert not b.mutations


def test_numeric_readback_conflict_is_rejected(tmp_path):
    bound_state(tmp_path)
    b = RedirectBackend()
    b._identity_requester.data['/repositories/123']['id'] = 999
    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)


def test_dry_run_does_not_verify_or_migrate(tmp_path):
    old = bound_state(tmp_path)
    b = RedirectBackend()
    before = old.state_file.read_bytes()
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b, dry_run=True)
    assert s.get_remote_id('PLF-001') == '42'
    assert old.state_file.read_bytes() == before
    assert b._identity_requester.calls == []
    assert b.mutations == []


def test_concurrent_mapping_write_survives_migration(tmp_path):
    old = bound_state(tmp_path)
    b = RedirectBackend()
    original = b._identity_requester.requestJsonAndCheck
    wrote = False

    def request(verb, path):
        nonlocal wrote
        if not wrote:
            wrote = True
            old.save_sync({'PLF-002': '43'})
        return original(verb, path)

    b._identity_requester.requestJsonAndCheck = request
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert s.get_last_sync()['ticket_map'] == {'PLF-001': '42', 'PLF-002': '43'}


def test_outbound_updates_same_issue_and_records_canonical_reference(tmp_path):
    pf = Planfile(str(tmp_path))
    t = pf.create_ticket('Original', integration=['github'], sync={'github': {'id': '42', 'repository': 'owner/old', 'url': 'https://github.com/owner/old/issues/42'}})
    bound_state(tmp_path)
    b = RedirectBackend()
    result = sync_to_external(b, [(t.id, t.model_dump(mode='json'))], False, pf.store, 'github')
    assert result.updated == (t.id,)
    assert result.created == ()
    assert b.mutations == ['42']
    current = pf.get_ticket(t.id)
    assert current.sync['github']['repository'] == 'owner/new'
    assert current.sync['github']['id'] == '42'


def test_factory_without_identity_capability_keeps_existing_backend_contract(tmp_path):
    b = SimpleNamespace(config={'repo': 'owner/old'})
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert s.repository == 'owner/old'
    assert not s.state_file.exists()


def test_read_only_reconciliation_verifies_without_rewriting(tmp_path):
    old = bound_state(tmp_path)
    before = old.state_file.read_bytes()
    b = RedirectBackend()
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', b, persist=False)
    assert s.get_remote_id('PLF-001') == '42'
    assert s.repository == 'owner/new'
    assert old.state_file.read_bytes() == before
    assert b._identity_requester.calls


def test_identity_is_retained_by_subsequent_mapping_save(tmp_path):
    bound_state(tmp_path)
    s = SyncState.from_backend(tmp_path / '.planfile', 'github', RedirectBackend())
    s.save_sync({'PLF-002': '43'})
    raw = s.get_last_sync()
    assert raw['repository_id'] == '123'
    assert raw['repository_aliases'] == ['owner/old']
    assert raw['ticket_map'] == {'PLF-001': '42', 'PLF-002': '43'}


@pytest.mark.parametrize('bad', [None, True, 0, '123'])
def test_invalid_provider_id_is_not_redirect_proof(tmp_path, bad):
    old = bound_state(tmp_path)
    b = RedirectBackend()
    b._identity_requester.data['/repos/owner/old']['id'] = bad
    before = old.state_file.read_bytes()
    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert old.state_file.read_bytes() == before


def test_binding_change_during_verification_is_not_overwritten(tmp_path):
    old = bound_state(tmp_path)
    b = RedirectBackend()
    original = b._identity_requester.requestJsonAndCheck
    newer = {'repository': 'other/repo', 'repository_id': '999', 'ticket_map': {'PLF-008': '99'}}
    changed = False

    def request(verb, path):
        nonlocal changed
        if not changed:
            changed = True
            old.state_file.write_text(yaml.safe_dump(newer))
        return original(verb, path)

    b._identity_requester.requestJsonAndCheck = request
    with pytest.raises(SyncStateRepositoryMismatch, match='binding changed'):
        SyncState.from_backend(tmp_path / '.planfile', 'github', b)
    assert yaml.safe_load(old.state_file.read_text()) == newer
