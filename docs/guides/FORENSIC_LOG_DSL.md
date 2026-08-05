# Public forensic log DSL

Planfile exposes a compact, append-only event timeline for applications,
operators, autonomous reviewers, and LLM diagnostics. The current UTC day is
stored in:

```text
.planfile/events/logs.dsl.txt
```

Older days are moved to
`.planfile/events/history/logs-YYYY-MM-DD.dsl.txt`. Consumers should normally
use the public HTTP interface rather than require access to Planfile's volume:

```bash
curl http://localhost:8000/logs.dsl.txt
curl 'http://localhost:8000/logs.dsl.txt?ticket_id=PLF-3775&limit=200'
curl 'http://localhost:8000/logs?event_type=ticket.status_change&limit=100'
curl http://localhost:8000/logs/days
curl 'http://localhost:8000/logs.dsl.txt?day=2026-08-04&limit=5000'
```

Both text and JSON reads are bounded to at most 5000 records. Text responses
declare `X-Planfile-Log-Format: PLOG/1`, the selected UTC date, and the result
count. `/logs/days` lists the available partitions and byte sizes without
exposing server filesystem paths.

## PLOG/1 format

Each physical line is one event. Fields are separated by tabs, and every value
is canonical JSON. This keeps values unambiguous while leaving reasons and
decisions directly readable without decoding a payload:

```text
PLOG/1 timestamp="2026-08-05T10:51:37Z" event_id="evt_..." event_hash="2ae..." type="ticket.status_change" kind="task" ticket_id="PLF-3774" actor="codex" source="planfile.history" mode="apply" status="done" correlation_id="PLF-3774" causation_id="-" receipt_ref="-" replayable=true logic={"reason":"All checks passed.","changes":["status"],"previous_status":"open","status":"done","execution_state":"done"}
```

The actual file uses tab separators. The fixed fields are:

- `timestamp`, `event_id`, and `event_hash` for ordering and verification;
- `type` for the OQL operation, such as `ticket.create`, `ticket.update`,
  `ticket.status_change`, `ticket.evidence.append`, or a management event;
- `ticket_id`, `actor`, `source`, `mode`, and `status` for attribution;
- `correlation_id`, `causation_id`, and `receipt_ref` for tracing;
- `replayable` to distinguish commands from observations;
- `logic`, a bounded projection of fields useful for diagnosis: name,
  priority, reason, decision, changes, previous/current lifecycle states,
  outcome, error, message, queue, evidence collection, and idempotency key.

Secret-like keys and credential-looking strings are redacted by SODL before
the PLOG projection is created. Large descriptions, raw tool output, and full
evidence payloads are deliberately excluded so one noisy event cannot make LLM
context unbounded.

Management producers may send `actor`, `correlation_id`, `causation_id`,
`receipt_ref`, `reason`, `decision`, `outcome`, `error`, and `idempotency_key`
to `/events/ingest`. These trace fields survive the API → SODL → PLOG path;
secret-like values are still redacted before persistence.

## Relationship to SODL and OQL

PLOG does not replace the existing audit contract:

- OQL describes the operation or decision being applied.
- SODL/1 in `.planfile/events/operations.jsonl` is the complete canonical,
  hashed event and retains the redacted source payload.
- PLOG/1 is the compact forensic index. Its `event_id` and `event_hash` point
  back to the full SODL event.
- Per-ticket evidence JSONL remains the durable source of external receipts;
  PLOG records that a receipt was appended, why, by whom, and under which
  idempotency key.

On first use, existing `operations.jsonl` is streamed line by line into daily
PLOG partitions. The migration does not load the complete journal into memory.
New operational events write PLOG first and then the backwards-compatible JSONL
projection. Daily rotation and both appends run under the existing Planfile
mutation lock.

## Event coverage

The durable log covers ticket creation, updates, lifecycle transitions, moves,
deletions, evidence appends, configuration decisions, externally observed
ticket changes, API startup, daily-history maintenance, management-event
ingestion, and synthetic diagnostic events. WebSocket messages derived from an
already recorded ticket mutation are not duplicated; their source mutation is
the forensic event.
