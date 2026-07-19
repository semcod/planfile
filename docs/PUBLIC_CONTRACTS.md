# Public automation contracts

Planfile exposes versioned Python contracts for analyzers and autonomous
orchestrators. These contracts separate a tool's proposal from the authority to
create, schedule or execute a ticket.

## Ticket proposal v1

`planfile.contracts.TicketProposalV1` is a strict, side-effect-free proposal.
Unknown fields are rejected. In particular it has no queue, sprint, executor,
capability, approval, transport or URI field.

```python
from planfile.contracts import TicketProposalV1

proposal = TicketProposalV1.model_validate({
    "schema": "planfile.ticket-proposal.v1",
    "proposal_id": "code2llm:src/service.py:Service",
    "dedupe_key": "symbol:src/service.py:Service",
    "name": "Split Service responsibilities",
    "priority": "high",
    "source": {
        "tool": "code2llm",
        "tool_version": "0.9.0",
        "finding_id": "src/service.py:Service",
    },
    "files": ["src/service.py"],
    "acceptance_criteria": ["Focused tests pass"],
})

canonical_payload = proposal.canonical_json()
proposal_hash = proposal.proposal_hash
safe_ticket_fields = proposal.to_ticket_kwargs()
```

Set-like fields are stripped, deduplicated and sorted before hashing. Ordered
acceptance criteria are stripped and deduplicated without changing their order.
The consumer remains responsible for deduplication, queue selection and
authorization before passing the safe fields to `Planfile.create_ticket`.

The JSON Schema for non-Python producers can be obtained from
`TicketProposalV1.model_json_schema(by_alias=True)`.

## Ticket lifecycle result v1

`planfile.client.PlanfileClient` wraps lifecycle mutations and returns
`TicketTransitionResult` with a stable code:

- `ok`
- `ticket_not_found`
- `invalid_transition`
- `lock_timeout`
- `store_error`

```python
from planfile.client import PlanfileClient

client = PlanfileClient("/workspace/project")
result = client.start("PLF-42", assigned_to="koru", actor="koru")
if result.code == "ok":
    ticket = result.ticket
elif result.retryable:
    schedule_retry(result.code)
```

The client owns the bounded storage-lock retry. The caller owns the decision to
perform a transition, its capability/grant checks and its retry budget outside
the storage transport.

Compatibility policy: add a new version instead of weakening strict validation
or changing the meaning of an existing result code.
