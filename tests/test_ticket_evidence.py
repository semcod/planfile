"""Opaque result values are valid until object-only evidence is appended."""
import pytest
from planfile import Planfile


@pytest.mark.parametrize('sharded', [False, True])
@pytest.mark.parametrize('result', ['deployed-and-verified', 23, [1, 2], False, None, {'status': 'ok'}])
def test_result_roundtrip_and_cas_update_without_evidence(tmp_path, sharded, result):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Valid opaque result', outputs={'result': result})
    if sharded:
        pf.store.migrate_to_sharded_yaml()
    for repair in [False, True]:
        found = pf.get_ticket(ticket.id, repair_index=repair)
        assert found is not None
        assert found.outputs.result == result
    located = pf.store._locate_ticket_source(ticket.id)
    source = pf.store._ticket_from_data(located[1])
    assert source is not None and source.outputs.result == result
    found = pf.get_ticket(ticket.id)
    updated = pf.update_ticket(ticket.id, expected_updated_at=found.updated_at.isoformat(), description='Guarded update')
    assert updated is not None and updated.outputs.result == result


def test_scalar_result_evidence_rejection_preserves_ticket(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Scalar result', outputs={'result': 'deployed-and-verified'})
    with pytest.raises(ValueError, match='ticket_output_result_not_object'):
        pf.append_ticket_evidence(ticket.id, idempotency_key='example-receipt', collection='checks',
                                  evidence={'status': 'passed'}, reason='Observed check', actor='test')
    assert pf.get_ticket(ticket.id).outputs.result == 'deployed-and-verified'


def test_object_result_accepts_idempotent_evidence(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Object result', outputs={'result': {'status': 'ok'}})
    args = dict(idempotency_key='example-receipt', collection='checks', evidence={'status': 'passed'},
                reason='Observed check', actor='test')
    first, added = pf.append_ticket_evidence(ticket.id, **args)
    assert added and first.outputs.result['status'] == 'ok'
    repeated, added = pf.append_ticket_evidence(ticket.id, **args)
    assert not added and len(repeated.outputs.result['checks']) == 1
