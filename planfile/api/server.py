"""FastAPI server for planfile — REST + WebSocket + DSL API.

Run with: uvicorn planfile.api.server:app --reload
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

try:
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, Response
    from pydantic import BaseModel
except ImportError as exc:
    raise ImportError("FastAPI required: pip install 'fastapi[all]' uvicorn") from exc

from planfile.core.models import TicketExecution, TicketExecutor, TicketInputs, TicketOutputs
from planfile.server_common import get_planfile


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _start_planfile_watcher()
    try:
        yield
    finally:
        await _stop_planfile_watcher()


app = FastAPI(
    title="planfile",
    description="Universal ticket standard — REST + WebSocket + DSL API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NO_STORE_HEADERS = {"Cache-Control": "no-store, max-age=0"}


# ── Schemas ────────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    name: str
    priority: str = "normal"
    sprint: str = "current"
    description: str = ""
    labels: list[str] = []
    executor: TicketExecutor | None = None
    execution: TicketExecution | None = None
    inputs: TicketInputs | None = None
    outputs: TicketOutputs | None = None


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    name: str | None = None
    description: str | None = None
    labels: list[str] | None = None
    executor: TicketExecutor | None = None
    execution: TicketExecution | None = None
    inputs: TicketInputs | None = None
    outputs: TicketOutputs | None = None


class SprintCreate(BaseModel):
    name: str
    length_days: int = 14
    objectives: list[str] = []


class DSLRequest(BaseModel):
    command: str
    project_path: str = "."


class DSLResponse(BaseModel):
    ok: bool
    command: dict
    data: Any = None
    error: str | None = None
    message: str | None = None


class YAMLPatchRequest(BaseModel):
    path: str
    value: Any


class TicketClaimRequest(BaseModel):
    assigned_to: str | None = None
    lease_seconds: int | None = None


class TicketCompleteRequest(BaseModel):
    note: str | None = None
    result: Any = None
    artifacts: list[str] = []


class TicketFailRequest(BaseModel):
    error: str


class TicketInputRequest(BaseModel):
    prompt: str
    env_keys: list[str] = []


class TestEventRequest(BaseModel):
    queue: str = "default"
    message: str = "Synthetic dashboard error event"
    state: str = "failed"


class ManagementEventRequest(BaseModel):
    source: str = "koru"
    tool: str = "koru"
    action: str
    status: str = "info"
    message: str = ""
    queue: str = "default"
    level: str = "info"
    details: dict[str, Any] = {}


# ── Tickets ────────────────────────────────────────────────────────────────────

@app.get("/tickets", tags=["tickets"])
def list_tickets(
    response: Response,
    sprint: str = Query("current"),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    source: str | None = Query(None),
):
    response.headers.update(NO_STORE_HEADERS)
    pf = get_planfile()
    filters: dict = {}
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority
    if source:
        filters["source"] = source
    tickets = pf.list_tickets(sprint=sprint, **filters)
    return [t.model_dump(mode="json", exclude_none=True) for t in tickets]


@app.post("/tickets", status_code=201, tags=["tickets"])
async def create_ticket(body: TicketCreate):
    pf = get_planfile()
    from planfile import TicketSource
    ticket = pf.create_ticket(
        name=body.name,
        priority=body.priority,
        sprint=body.sprint,
        description=body.description,
        labels=body.labels,
        executor=body.executor,
        execution=body.execution,
        inputs=body.inputs,
        outputs=body.outputs,
        source=TicketSource(tool="api"),
    )
    await _broadcast_ticket_event("ticket.changed", "create", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.get("/tickets/next", tags=["tickets"])
def next_ticket(sprint: str = Query("current"), queue: str | None = Query(None)):
    pf = get_planfile()
    ticket = pf.next_ticket(sprint=sprint, queue=queue)
    if not ticket:
        return None
    return ticket.model_dump(mode="json", exclude_none=True)


@app.get("/tickets/{ticket_id}", tags=["tickets"])
def get_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.patch("/tickets/{ticket_id}", tags=["tickets"])
async def update_ticket(ticket_id: str, body: TicketUpdate):
    pf = get_planfile()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ticket = pf.update_ticket(ticket_id, **updates)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.changed", "update", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.delete("/tickets/{ticket_id}", status_code=204, tags=["tickets"])
async def delete_ticket(ticket_id: str):
    pf = get_planfile()
    ok = pf.store.delete_ticket(ticket_id)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.changed", "delete", ticket_id=ticket_id)


@app.post("/tickets/{ticket_id}/move", tags=["tickets"])
async def move_ticket(ticket_id: str, to_sprint: str = Query(...)):
    pf = get_planfile()
    ok = pf.store.move_ticket(ticket_id, to_sprint)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.changed", "move", ticket_id=ticket_id)
    return {"moved": ticket_id, "to": to_sprint}


@app.post("/tickets/{ticket_id}/done", tags=["tickets"])
async def done_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.complete_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "done", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/start", tags=["tickets"])
async def start_ticket(ticket_id: str, body: TicketClaimRequest | None = None):
    pf = get_planfile()
    assigned_to = body.assigned_to if body else None
    ticket = pf.start_ticket(ticket_id, assigned_to=assigned_to)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "start", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/claim", tags=["tickets"])
async def claim_ticket(ticket_id: str, body: TicketClaimRequest):
    pf = get_planfile()
    ticket = pf.claim_ticket(
        ticket_id,
        assigned_to=body.assigned_to,
        lease_seconds=body.lease_seconds,
    )
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "claim", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/complete", tags=["tickets"])
async def complete_ticket(ticket_id: str, body: TicketCompleteRequest):
    pf = get_planfile()
    ticket = pf.complete_ticket(
        ticket_id,
        note=body.note,
        result=body.result,
        artifacts=body.artifacts,
    )
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "complete", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/fail", tags=["tickets"])
async def fail_ticket(ticket_id: str, body: TicketFailRequest):
    pf = get_planfile()
    ticket = pf.fail_ticket(ticket_id, error=body.error)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "fail", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/input-required", tags=["tickets"])
async def wait_for_input(ticket_id: str, body: TicketInputRequest):
    pf = get_planfile()
    ticket = pf.wait_for_input(ticket_id, prompt=body.prompt, env_keys=body.env_keys)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "input_required", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/ready", tags=["tickets"])
async def ready_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.ready_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "ready", ticket)
    return ticket.model_dump(mode="json", exclude_none=True)


# ── Sprints ────────────────────────────────────────────────────────────────────

@app.get("/sprints", tags=["sprints"])
def list_sprints():
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        return []
    with open(pf_path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("sprints", [])


@app.post("/sprints", status_code=201, tags=["sprints"])
def create_sprint(body: SprintCreate):
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        raise HTTPException(404, "planfile.yaml not found")
    with open(pf_path) as f:
        data = yaml.safe_load(f) or {}
    sprints = data.get("sprints", [])
    new_id = max((s.get("id", 0) for s in sprints), default=0) + 1
    sprint = {"id": new_id, "name": body.name, "length_days": body.length_days, "objectives": body.objectives}
    sprints.append(sprint)
    data["sprints"] = sprints
    with open(pf_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return sprint


# ── YAML direct operations ─────────────────────────────────────────────────────

@app.get("/yaml", tags=["yaml"])
def get_yaml():
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        raise HTTPException(404, "planfile.yaml not found")
    with open(pf_path) as f:
        return yaml.safe_load(f) or {}


@app.patch("/yaml", tags=["yaml"])
def patch_yaml(body: YAMLPatchRequest):
    """Patch a top-level key in planfile.yaml. path=key, value=new_value."""
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        raise HTTPException(404, "planfile.yaml not found")
    with open(pf_path) as f:
        data = yaml.safe_load(f) or {}
    keys = body.path.split(".")
    node = data
    for key in keys[:-1]:
        if key not in node or not isinstance(node[key], dict):
            node[key] = {}
        node = node[key]
    node[keys[-1]] = body.value
    with open(pf_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return {"patched": body.path, "value": body.value}


# ── DSL endpoint ───────────────────────────────────────────────────────────────

@app.post("/dsl", response_model=DSLResponse, tags=["dsl"])
def dsl_command(body: DSLRequest) -> DSLResponse:
    """Execute a DSL / natural language command against planfile."""
    from planfile.dsl import DSLExecutor
    executor = DSLExecutor(project_path=body.project_path)
    result = executor.run(body.command)
    return DSLResponse(**result.to_dict())


@app.get("/dsl/help", tags=["dsl"])
def dsl_help():
    """Return DSL command reference."""
    from planfile.dsl import DSLCommand, DSLExecutor
    executor = DSLExecutor()
    result = executor.execute(DSLCommand(verb="help"))
    return {"help": result.message}


# ── WebSocket ──────────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


_manager = ConnectionManager()
_EVENT_HISTORY_LIMIT = 200
_event_history: deque[dict[str, Any]] = deque(maxlen=_EVENT_HISTORY_LIMIT)
_watch_task: asyncio.Task | None = None
_watch_snapshot: dict[str, str] = {}


def _event_queue(event: dict[str, Any]) -> str:
    if event.get("queue"):
        return str(event["queue"])
    ticket = event.get("ticket")
    if not isinstance(ticket, dict):
        return "default"
    execution = ticket.get("execution")
    if not isinstance(execution, dict):
        return "default"
    return str(execution.get("queue") or "default")


def _event_ticket_id(event: dict[str, Any]) -> str:
    ticket_id = event.get("ticket_id")
    if ticket_id and ticket_id != "-":
        return str(ticket_id)

    ticket = event.get("ticket")
    if isinstance(ticket, dict) and ticket.get("id"):
        return str(ticket["id"])

    details = event.get("details")
    if isinstance(details, dict) and details.get("ticket_id"):
        return str(details["ticket_id"])

    return ""


def _remember_event(event: dict[str, Any]) -> None:
    _event_history.append(event)


def _ticket_signature(ticket) -> str:
    data = ticket.model_dump(mode="json", exclude_none=True)
    execution = data.get("execution") or {}
    return json.dumps(
        {
            "status": data.get("status"),
            "priority": data.get("priority"),
            "name": data.get("name"),
            "updated_at": data.get("updated_at"),
            "execution_state": execution.get("state"),
            "execution_queue": execution.get("queue"),
            "execution_assigned_to": execution.get("assigned_to"),
            "execution_last_error": execution.get("last_error"),
            "execution_finished_at": execution.get("finished_at"),
        },
        sort_keys=True,
    )


def _current_ticket_snapshot() -> tuple[dict[str, str], dict[str, Any]]:
    tickets = get_planfile().list_tickets(sprint="all")
    snapshot = {ticket.id: _ticket_signature(ticket) for ticket in tickets}
    by_id = {ticket.id: ticket for ticket in tickets}
    return snapshot, by_id


async def _watch_planfile_changes(interval_seconds: float = 3.0) -> None:
    """Broadcast status changes made outside this API, such as CLI updates."""
    global _watch_snapshot
    try:
        _watch_snapshot, _ = _current_ticket_snapshot()
    except Exception as exc:  # pragma: no cover - defensive runtime telemetry
        _watch_snapshot = {}
        _remember_event(
            {
                "type": "dashboard",
                "action": "watch-error",
                "ticket_id": "-",
                "created_at": datetime.now(UTC).isoformat(),
                "ticket": {"execution": {"state": "failed", "last_error": str(exc)}},
            }
        )

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            current, by_id = _current_ticket_snapshot()
        except Exception as exc:  # pragma: no cover - defensive runtime telemetry
            payload = {
                "type": "dashboard",
                "action": "watch-error",
                "ticket_id": "-",
                "created_at": datetime.now(UTC).isoformat(),
                "ticket": {"execution": {"state": "failed", "last_error": str(exc)}},
            }
            _remember_event(payload)
            await _manager.broadcast(payload)
            continue

        previous = _watch_snapshot
        for ticket_id, signature in current.items():
            old_signature = previous.get(ticket_id)
            if old_signature is None:
                await _broadcast_ticket_event("ticket.external.changed", "external-create", by_id[ticket_id])
            elif old_signature != signature:
                await _broadcast_ticket_event("ticket.external.changed", "external-update", by_id[ticket_id])
        _watch_snapshot = current


async def _start_planfile_watcher() -> None:
    global _watch_task
    _remember_event(
        {
            "type": "management.event",
            "action": "started",
            "ticket_id": "-",
            "created_at": datetime.now(UTC).isoformat(),
            "source": "planfile",
            "tool": "planfile.api",
            "queue": "koru-management",
            "level": "info",
            "status": "running",
            "message": "planfile API server started",
            "details": {"watcher_enabled": os.environ.get("PLANFILE_DISABLE_WATCHER") != "1"},
        }
    )
    if os.environ.get("PLANFILE_DISABLE_WATCHER") == "1":
        return
    if _watch_task is None or _watch_task.done():
        _watch_task = asyncio.create_task(_watch_planfile_changes())


async def _stop_planfile_watcher() -> None:
    global _watch_task
    if _watch_task is None:
        return
    _watch_task.cancel()
    try:
        await _watch_task
    except asyncio.CancelledError:
        pass
    _watch_task = None


@app.get("/events", tags=["events"])
def list_events(
    response: Response,
    limit: int = Query(100, ge=1, le=500),
    queue: str | None = Query(None),
    ticket_id: str | None = Query(None),
):
    """Return recent ticket events for dashboards that reconnect late."""
    response.headers.update(NO_STORE_HEADERS)
    events = list(_event_history)
    if queue:
        events = [event for event in events if _event_queue(event) == queue]
    if ticket_id:
        events = [event for event in events if _event_ticket_id(event) == ticket_id]
    return events[-limit:]


@app.post("/events/test", tags=["events"])
async def create_test_event(body: TestEventRequest):
    """Broadcast a synthetic dashboard event without mutating a real ticket."""
    created_at = datetime.now(UTC).isoformat()
    payload = {
        "type": "dashboard.test",
        "action": "error",
        "ticket_id": "TEST",
        "created_at": created_at,
        "ticket": {
            "id": "TEST",
            "name": body.message,
            "execution": {
                "queue": body.queue,
                "state": body.state,
                "last_error": body.message,
                "updated_at": created_at,
            },
        },
    }
    _remember_event(payload)
    await _manager.broadcast(payload)
    return payload


@app.post("/events/ingest", tags=["events"])
async def ingest_management_event(body: ManagementEventRequest):
    """Ingest a management-layer event for dashboards and operators."""
    payload = {
        "type": "management.event",
        "action": body.action,
        "ticket_id": str(body.details.get("ticket_id") or "-"),
        "created_at": datetime.now(UTC).isoformat(),
        "source": body.source,
        "tool": body.tool,
        "queue": body.queue,
        "level": body.level,
        "status": body.status,
        "message": body.message,
        "details": body.details,
    }
    _remember_event(payload)
    await _manager.broadcast(payload)
    return payload


def _dashboard_html() -> str:
    """Return the small built-in queue dashboard."""
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>planfile queue</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101114;
      --panel: #181b20;
      --panel-2: #20242b;
      --text: #f4f6f8;
      --muted: #a8b0ba;
      --line: #303640;
      --ok: #53d18a;
      --warn: #f5c451;
      --err: #ff6b6b;
      --info: #7ab8ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: #14171c;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { font-size: 18px; margin: 0; font-weight: 650; }
    main {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(320px, 520px) minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    h2 { font-size: 14px; margin: 0; color: var(--muted); font-weight: 620; }
    button {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }
    button:hover { border-color: var(--info); }
    select {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 10px;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      white-space: nowrap;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--warn);
      display: inline-block;
    }
    .dot.ok { background: var(--ok); }
    .dot.err { background: var(--err); }
    .controls { display: flex; flex-wrap: wrap; gap: 8px; }
    .toolbar {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      padding: 14px;
    }
    .metric {
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }
    .metric strong { display: block; font-size: 24px; line-height: 1.1; }
    .metric span { color: var(--muted); }
    .list, .events, .detail { max-height: calc(100vh - 178px); overflow: auto; }
    .ticket, .event {
      border-bottom: 1px solid var(--line);
      padding: 10px 14px;
    }
    .ticket {
      cursor: pointer;
      outline: 0;
    }
    .ticket:hover, .ticket:focus-visible {
      background: #1c2026;
    }
    .ticket.selected {
      background: #202936;
      box-shadow: inset 3px 0 0 var(--info);
    }
    .ticket:last-child, .event:last-child { border-bottom: 0; }
    .title { font-weight: 620; word-break: break-word; }
    .meta { color: var(--muted); margin-top: 4px; display: flex; flex-wrap: wrap; gap: 8px; }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 1px 8px;
      color: var(--muted);
      background: #15181d;
    }
    .pill.failed, .pill.error { color: var(--err); border-color: #6a3333; }
    .pill.running { color: var(--info); border-color: #31516f; }
    .pill.done { color: var(--ok); border-color: #2b6040; }
    .pill.waiting_input { color: var(--warn); border-color: #715d2c; }
    .empty { color: var(--muted); padding: 14px; }
    .detail { padding: 14px; }
    .detail h3 {
      margin: 0 0 10px;
      font-size: 17px;
      line-height: 1.25;
    }
    .detail-block {
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 12px;
    }
    .detail-block h4 {
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .kv {
      display: grid;
      grid-template-columns: minmax(96px, 150px) minmax(0, 1fr);
      gap: 6px 10px;
      color: var(--muted);
    }
    .kv strong { color: var(--text); font-weight: 560; word-break: break-word; }
    .timeline { display: grid; gap: 10px; }
    .timeline-item {
      border-left: 3px solid var(--line);
      padding-left: 10px;
    }
    .timeline-item.error, .timeline-item.failed { border-left-color: var(--err); }
    .timeline-item.warning, .timeline-item.waiting_input { border-left-color: var(--warn); }
    .timeline-item.info, .timeline-item.running { border-left-color: var(--info); }
    .timeline-item.done, .timeline-item.completed { border-left-color: var(--ok); }
    .related { display: flex; flex-wrap: wrap; gap: 8px; }
    .related .pill { cursor: pointer; }
    pre {
      margin: 8px 0 0;
      color: var(--muted);
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
    }
    @media (max-width: 820px) {
      header { align-items: flex-start; flex-direction: column; }
      main { grid-template-columns: 1fr; }
      .list, .events, .detail { max-height: none; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>planfile queue dashboard</h1>
      <div class="status"><span id="dot" class="dot"></span><span id="status">connecting...</span></div>
    </div>
    <div class="controls">
      <button id="notify">Enable notifications</button>
      <button id="test-notify">Test notification</button>
      <button id="refresh">Refresh tickets</button>
      <button id="docs">API docs</button>
    </div>
  </header>
  <main>
    <section>
      <div class="section-head"><h2>Queue Summary</h2><span id="updated" class="status">never</span></div>
      <div class="toolbar">
        <label for="queue-filter" class="status">Queue</label>
        <select id="queue-filter">
          <option value="all">all</option>
        </select>
      </div>
      <div class="metrics">
        <div class="metric"><strong id="m-open">0</strong><span>open</span></div>
        <div class="metric"><strong id="m-running">0</strong><span>running</span></div>
        <div class="metric"><strong id="m-waiting">0</strong><span>waiting</span></div>
        <div class="metric"><strong id="m-failed">0</strong><span>failed</span></div>
      </div>
      <div id="tickets" class="list"></div>
    </section>
    <section>
      <div class="section-head"><h2>Ticket Detail</h2><span id="detail-status" class="status">select a ticket</span></div>
      <div id="ticket-detail" class="detail empty">Select a ticket from the queue to inspect status history, tool logs, related work, and human input blockers.</div>
    </section>
    <section>
      <div class="section-head"><h2>Live Events</h2><span id="event-count" class="status">0 events</span></div>
      <div id="events" class="events"></div>
    </section>
  </main>
  <script>
    const state = {
      events: 0,
      notifications: "Notification" in window && Notification.permission === "granted",
      queue: localStorage.getItem("planfile.queue") || "all",
      selectedTicketId: null,
      selectedTicket: null,
      ticketEvents: [],
      seenTicketStates: new Map(),
      lastTickets: [],
    };
    const $ = (id) => document.getElementById(id);
    const dot = $("dot");
    const status = $("status");
    const ticketsEl = $("tickets");
    const eventsEl = $("events");
    const detailEl = $("ticket-detail");
    const detailStatusEl = $("detail-status");

    function setStatus(text, kind) {
      status.textContent = text;
      dot.className = "dot " + (kind || "");
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }

    function stringifyDetail(value) {
      if (value === null || value === undefined || value === "") return "";
      return typeof value === "string" ? value : JSON.stringify(value, null, 2);
    }

    function formatDate(value) {
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString();
    }

    function ticketState(ticket) {
      return ticket?.execution?.state || ticket?.status || "unknown";
    }

    function ticketEventId(event) {
      if (event?.ticket_id && event.ticket_id !== "-") return String(event.ticket_id);
      if (event?.ticket?.id) return String(event.ticket.id);
      if (event?.details?.ticket_id) return String(event.details.ticket_id);
      return "";
    }

    function isNotifiableEvent(event) {
      if (event?.type === "management.event") {
        return ["error", "failed", "warning"].includes(String(event.level || event.status || "").toLowerCase());
      }
      if (!event?.ticket) return false;
      if (event.type === "raw") return false;
      return Boolean(event.ticket_id || event.ticket.id || event.action);
    }

    function ticketSignature(ticket) {
      return `${ticket?.status || "unknown"}:${ticketState(ticket)}:${ticket?.execution?.last_error || ""}`;
    }

    function statusLabel(ticket) {
      const statusName = ticket?.status || "unknown";
      const stateName = ticketState(ticket);
      return statusName === stateName ? stateName : `${statusName}/${stateName}`;
    }

    function ticketQueue(ticket) {
      return ticket?.execution?.queue || "default";
    }

    function isFailedTicket(ticket) {
      const stateName = ticketState(ticket);
      return stateName === "failed" || stateName === "error" || Boolean(ticket?.execution?.last_error);
    }

    function isRunningTicket(ticket) {
      const stateName = ticketState(ticket);
      if (isWaitingTicket(ticket) || isFailedTicket(ticket) || stateName === "done") return false;
      return ticket?.status === "in_progress" || stateName === "running" || stateName === "in_progress";
    }

    function isWaitingTicket(ticket) {
      const stateName = ticketState(ticket);
      return stateName === "waiting_input" || stateName === "waiting";
    }

    function eventQueue(event) {
      if (event?.queue) return String(event.queue);
      return event?.ticket ? ticketQueue(event.ticket) : "default";
    }

    function eventMatchesQueue(event) {
      return state.queue === "all" || eventQueue(event) === state.queue;
    }

    function eventLevel(event) {
      const raw = String(event?.level || event?.status || event?.ticket?.execution?.state || event?.action || "info").toLowerCase();
      if (["error", "failed", "failure"].includes(raw) || event?.ticket?.execution?.last_error) return "error";
      if (["warning", "warn", "waiting_input", "waiting"].includes(raw)) return "warning";
      if (["done", "completed", "ok", "success"].includes(raw)) return "done";
      if (["running", "started", "claim"].includes(raw)) return "running";
      return "info";
    }

    function notifyTicket(ticket, reason) {
      if (!state.notifications || Notification.permission !== "granted" || !ticket) return;
      const body = ticket.execution?.last_error || ticket.name || reason || "planfile event";
      new Notification(`planfile ${ticket.id || "ticket"} ${statusLabel(ticket)}`, { body });
    }

    function notify(event) {
      if (!isNotifiableEvent(event)) return;
      if (event?.type === "management.event") {
        if (!state.notifications || Notification.permission !== "granted") return;
        const body = event.message || JSON.stringify(event.details || {});
        new Notification(`${event.tool || event.source || "koru"} ${event.action || "event"}`, { body });
        return;
      }
      notifyTicket(event.ticket, event.action);
    }

    function selectedTickets(tickets) {
      if (state.queue === "all") return tickets;
      return tickets.filter((ticket) => ticketQueue(ticket) === state.queue);
    }

    function updateQueueOptions(tickets) {
      const queues = Array.from(new Set(tickets.map(ticketQueue))).sort();
      const select = $("queue-filter");
      const html = ['<option value="all">all</option>', ...queues.map((queue) => `<option value="${escapeHtml(queue)}">${escapeHtml(queue)}</option>`)].join("");
      if (select.innerHTML !== html) select.innerHTML = html;
      if (!["all", ...queues].includes(state.queue)) state.queue = "all";
      select.value = state.queue;
    }

    function scanTicketStatuses(tickets, { notifyChanges = false, resetSeen = false } = {}) {
      if (resetSeen) state.seenTicketStates.clear();
      for (const ticket of tickets) {
        const key = ticket?.id || "unknown";
        const signature = ticketSignature(ticket);
        const previous = state.seenTicketStates.get(key);
        if (notifyChanges && previous && previous !== signature) {
          notifyTicket(ticket, `status changed: ${previous} -> ${signature}`);
        } else if (notifyChanges && !previous) {
          notifyTicket(ticket, "new ticket detected by dashboard polling");
        }
        state.seenTicketStates.set(key, signature);
      }
    }

    function resetEvents() {
      state.events = 0;
      eventsEl.innerHTML = "";
      $("event-count").textContent = "0 events";
    }

    function renderTickets(tickets) {
      ticketsEl.innerHTML = tickets
        .filter((t) => t.status !== "done" && t.status !== "canceled")
        .slice(0, 80)
        .map((t) => {
          const stateName = ticketState(t);
          const queue = ticketQueue(t);
          const selectedClass = t.id === state.selectedTicketId ? " selected" : "";
          return `
            <div class="ticket${selectedClass}" data-ticket-id="${escapeHtml(t.id)}" role="button" tabindex="0">
              <div class="title">${escapeHtml(t.id)} ${escapeHtml(t.name)}</div>
              <div class="meta">
                <span class="pill ${escapeHtml(stateName)}">${escapeHtml(stateName)}</span>
                <span class="pill">${escapeHtml(t.priority || "normal")}</span>
                <span class="pill">${escapeHtml(queue)}</span>
              </div>
            </div>
          `;
        })
        .join("") || '<div class="empty">No active tickets in this queue</div>';
    }

    function detailBlock(title, body) {
      if (!body) return "";
      return `<div class="detail-block"><h4>${escapeHtml(title)}</h4>${body}</div>`;
    }

    function keyValues(rows) {
      const visible = rows.filter(([, value]) => value !== undefined && value !== null && value !== "" && value !== "-");
      if (!visible.length) return "";
      return `<div class="kv">${visible.map(([key, value]) => `<span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>`).join("")}</div>`;
    }

    function relatedTicketIds(ticket, events) {
      const ids = new Set([...(ticket?.blocked_by || []), ...(ticket?.blocks || [])]);
      const textParts = [
        ticket?.description,
        ticket?.inputs?.prompt,
        ...(ticket?.outputs?.notes || []),
        ...events.map((event) => `${event.message || ""} ${stringifyDetail(event.details)}`),
      ];
      for (const text of textParts) {
        for (const match of String(text || "").matchAll(/\bPLF-\d+\b/g)) {
          if (match[0] !== ticket?.id) ids.add(match[0]);
        }
      }
      return Array.from(ids).sort();
    }

    function renderRelated(ids) {
      if (!ids.length) return '<div class="empty">No linked tickets detected yet.</div>';
      return `<div class="related">${ids.map((id) => `<button class="pill" data-related-ticket-id="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join("")}</div>`;
    }

    function addTimelineItem(items, when, level, title, body = "", details = null) {
      if (!when && !title && !body && !details) return;
      items.push({
        when: when || null,
        level: level || "info",
        title,
        body,
        details,
        order: items.length,
      });
    }

    function buildTicketTimeline(ticket, events) {
      const items = [];
      const execution = ticket?.execution || {};
      addTimelineItem(items, ticket?.created_at, "info", "ticket created", ticket?.source?.tool ? `source: ${ticket.source.tool}` : "");
      if (execution.started_at) addTimelineItem(items, execution.started_at, "running", "execution started", execution.assigned_to || "");
      if (execution.state === "waiting_input") {
        addTimelineItem(items, ticket?.updated_at, "warning", "waiting for human input", ticket?.inputs?.prompt || execution.last_error || "");
      }
      if (execution.last_error) addTimelineItem(items, ticket?.updated_at, "error", "last error", execution.last_error);
      if (execution.finished_at) addTimelineItem(items, execution.finished_at, execution.state || "done", "execution finished", execution.state || "");
      for (const entry of ticket?.history || []) {
        addTimelineItem(items, entry.created_at || entry.timestamp || entry.when, entry.level || entry.status || "info", entry.action || "history", entry.message || entry.note || "", entry);
      }
      for (const note of ticket?.outputs?.notes || []) {
        addTimelineItem(items, ticket?.updated_at, "info", "output note", note);
      }
      for (const event of events) {
        const management = event.type === "management.event";
        const title = management
          ? `${event.source || "koru"} / ${event.tool || "tool"} / ${event.action || "-"}`
          : `${event.type || "event"} / ${event.action || "-"}`;
        const body = management ? event.message : event.ticket?.name;
        const details = management ? event.details : event.ticket?.execution?.last_error;
        addTimelineItem(items, event.created_at, eventLevel(event), title, body, details);
      }
      if (ticket?.updated_at && ticket.updated_at !== ticket.created_at) {
        addTimelineItem(items, ticket.updated_at, ticketState(ticket), "ticket updated", statusLabel(ticket));
      }
      return items.sort((a, b) => {
        const at = a.when ? new Date(a.when).getTime() : 0;
        const bt = b.when ? new Date(b.when).getTime() : 0;
        if (at === bt) return a.order - b.order;
        return at - bt;
      });
    }

    function renderTimelineItem(item) {
      const details = stringifyDetail(item.details);
      return `
        <div class="timeline-item ${escapeHtml(item.level)}">
          <div class="title">${escapeHtml(item.title || "event")}</div>
          <div class="meta"><span class="pill ${escapeHtml(item.level)}">${escapeHtml(item.level)}</span><span>${escapeHtml(formatDate(item.when))}</span></div>
          ${item.body ? `<pre>${escapeHtml(item.body)}</pre>` : ""}
          ${details ? `<pre>${escapeHtml(details)}</pre>` : ""}
        </div>
      `;
    }

    function renderTicketTimeline(ticket, events) {
      const items = buildTicketTimeline(ticket, events);
      if (!items.length) return '<div class="empty">No ticket timeline entries yet.</div>';
      return `<div class="timeline">${items.map(renderTimelineItem).join("")}</div>`;
    }

    function renderTicketDetail(ticket, events = []) {
      if (!ticket) {
        detailStatusEl.textContent = "select a ticket";
        detailEl.className = "detail empty";
        detailEl.textContent = "Select a ticket from the queue to inspect status history, tool logs, related work, and human input blockers.";
        return;
      }
      const execution = ticket.execution || {};
      const executor = ticket.executor || {};
      const inputs = ticket.inputs || {};
      const outputs = ticket.outputs || {};
      const source = ticket.source || {};
      const stateName = ticketState(ticket);
      const related = relatedTicketIds(ticket, events);
      detailStatusEl.textContent = ticket.id;
      detailEl.className = "detail";
      detailEl.innerHTML = `
        <h3>${escapeHtml(ticket.id)} ${escapeHtml(ticket.name)}</h3>
        <div class="meta">
          <span class="pill ${escapeHtml(stateName)}">${escapeHtml(statusLabel(ticket))}</span>
          <span class="pill">${escapeHtml(ticket.priority || "normal")}</span>
          <span class="pill">${escapeHtml(ticketQueue(ticket))}</span>
        </div>
        ${ticket.description ? `<pre>${escapeHtml(ticket.description)}</pre>` : ""}
        ${detailBlock("Lifecycle", keyValues([
          ["created", formatDate(ticket.created_at)],
          ["updated", formatDate(ticket.updated_at)],
          ["source", [source.tool, source.version].filter(Boolean).join(" ")],
          ["labels", (ticket.labels || []).join(", ")],
        ]))}
        ${detailBlock("Current work", keyValues([
          ["executor", [executor.kind, executor.mode, executor.handler].filter(Boolean).join(" / ")],
          ["state", execution.state],
          ["assigned_to", execution.assigned_to],
          ["attempt", execution.attempt !== undefined ? `${execution.attempt}/${execution.max_attempts || 1}` : ""],
          ["started", formatDate(execution.started_at)],
          ["finished", formatDate(execution.finished_at)],
          ["lease_expires", formatDate(execution.lease_expires_at)],
          ["last_error", execution.last_error],
        ]))}
        ${detailBlock("Human/API/Tool inputs", keyValues([
          ["prompt", inputs.prompt],
          ["env_keys", (inputs.env_keys || []).join(", ")],
          ["script", inputs.script],
          ["api", [inputs.api_method, inputs.api_endpoint].filter(Boolean).join(" ")],
          ["mcp_tool", inputs.mcp_tool],
          ["llm_model", inputs.llm_model],
        ]))}
        ${detailBlock("Outputs", keyValues([
          ["artifacts", (outputs.artifacts || []).join(", ")],
          ["notes", (outputs.notes || []).join(" | ")],
          ["result", stringifyDetail(outputs.result)],
        ]))}
        ${detailBlock("Related tickets and splits", renderRelated(related))}
        ${detailBlock("Timeline and tool logs", renderTicketTimeline(ticket, events))}
      `;
    }

    async function selectTicket(ticketId, options = {}) {
      if (!ticketId) return;
      state.selectedTicketId = ticketId;
      renderTickets(selectedTickets(state.lastTickets));
      if (!options.silent) {
        detailStatusEl.textContent = "loading...";
        detailEl.className = "detail empty";
        detailEl.textContent = `Loading ${ticketId}...`;
      }
      const [ticketResponse, eventsResponse] = await Promise.all([
        fetch(`/tickets/${encodeURIComponent(ticketId)}`, { cache: "no-store" }),
        fetch(`/events?ticket_id=${encodeURIComponent(ticketId)}&limit=500`, { cache: "no-store" }),
      ]);
      if (!ticketResponse.ok) throw new Error(`Ticket ${ticketId} returned HTTP ${ticketResponse.status}`);
      state.selectedTicket = await ticketResponse.json();
      state.ticketEvents = eventsResponse.ok ? await eventsResponse.json() : [];
      renderTicketDetail(state.selectedTicket, state.ticketEvents);
      renderTickets(selectedTickets(state.lastTickets));
    }

    function refreshSelectedTicket() {
      if (!state.selectedTicketId) return;
      selectTicket(state.selectedTicketId, { silent: true }).catch((error) => {
        detailStatusEl.textContent = "error";
        detailEl.className = "detail";
        detailEl.innerHTML = `<pre>${escapeHtml(String(error))}</pre>`;
      });
    }

    function addEvent(event, options = {}) {
      if (!eventMatchesQueue(event)) return;
      const notifyEvent = options.notifyEvent !== false;
      const refresh = options.refresh !== false;
      state.events += 1;
      $("event-count").textContent = `${state.events} events`;
      const item = document.createElement("div");
      item.className = "event";
      const stateName = ticketState(event.ticket);
      const when = event.created_at ? new Date(event.created_at) : new Date();
      const management = event.type === "management.event";
      const eventTitle = management
        ? `${event.source || "koru"} / ${event.tool || "tool"} / ${event.action || "-"}`
        : `${event.type || "event"} / ${event.action || "-"} / ${event.ticket_id || "-"}`;
      const eventState = management ? (event.status || event.level || "info") : stateName;
      const eventMessage = management ? event.message : event.ticket?.name;
      const eventDetail = management ? event.details : event.ticket?.execution?.last_error;
      item.innerHTML = `
        <div class="title">${escapeHtml(eventTitle)}</div>
        <div class="meta"><span class="pill ${escapeHtml(eventState)}">${escapeHtml(eventState)}</span><span class="pill">${escapeHtml(eventQueue(event))}</span><span>${when.toLocaleTimeString()}</span></div>
        ${eventMessage ? `<pre>${escapeHtml(eventMessage)}</pre>` : ""}
        ${eventDetail ? `<pre>${escapeHtml(stringifyDetail(eventDetail))}</pre>` : ""}
      `;
      eventsEl.prepend(item);
      while (eventsEl.children.length > 100) eventsEl.lastChild.remove();
      if (state.selectedTicketId && ticketEventId(event) === state.selectedTicketId) {
        state.ticketEvents.push(event);
        renderTicketDetail(state.selectedTicket, state.ticketEvents);
        refreshSelectedTicket();
      }
      if (notifyEvent) notify(event);
      if (refresh) refreshTickets({ notifyChanges: false });
    }

    async function loadEventHistory() {
      const queueParam = state.queue === "all" ? "" : `&queue=${encodeURIComponent(state.queue)}`;
      const response = await fetch(`/events?limit=100${queueParam}`, { cache: "no-store" });
      const events = await response.json();
      resetEvents();
      for (const event of events) {
        addEvent(event, { notifyEvent: false, refresh: false });
      }
    }

    async function refreshTickets(options = {}) {
      const response = await fetch("/tickets?sprint=all", { cache: "no-store" });
      const tickets = await response.json();
      state.lastTickets = tickets;
      updateQueueOptions(tickets);
      const visibleTickets = selectedTickets(tickets);
      scanTicketStatuses(visibleTickets, options);
      const open = visibleTickets.filter((t) => t.status === "open").length;
      const running = visibleTickets.filter(isRunningTicket).length;
      const waiting = visibleTickets.filter(isWaitingTicket).length;
      const failed = visibleTickets.filter(isFailedTicket).length;
      $("m-open").textContent = open;
      $("m-running").textContent = running;
      $("m-waiting").textContent = waiting;
      $("m-failed").textContent = failed;
      $("updated").textContent = new Date().toLocaleTimeString();
      renderTickets(visibleTickets);
      if (state.selectedTicketId && !tickets.some((ticket) => ticket.id === state.selectedTicketId)) {
        state.selectedTicketId = null;
        state.selectedTicket = null;
        state.ticketEvents = [];
        renderTicketDetail(null);
      }
    }

    function connect() {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${location.host}/ws`);
      ws.onopen = () => setStatus("connected", "ok");
      ws.onclose = () => {
        setStatus("disconnected, retrying...", "err");
        setTimeout(connect, 2000);
      };
      ws.onerror = () => setStatus("websocket error", "err");
      ws.onmessage = (message) => {
        try {
          addEvent(JSON.parse(message.data));
        } catch {
          addEvent({ type: "raw", action: "message", ticket_id: "-", ticket: { name: message.data } });
        }
      };
    }

    ticketsEl.addEventListener("click", (event) => {
      const node = event.target.closest("[data-ticket-id]");
      if (node) selectTicket(node.dataset.ticketId).catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: node.dataset.ticketId, ticket: { execution: { state: "failed", last_error: String(error) } } }));
    });
    ticketsEl.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const node = event.target.closest("[data-ticket-id]");
      if (!node) return;
      event.preventDefault();
      selectTicket(node.dataset.ticketId).catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: node.dataset.ticketId, ticket: { execution: { state: "failed", last_error: String(error) } } }));
    });
    detailEl.addEventListener("click", (event) => {
      const node = event.target.closest("[data-related-ticket-id]");
      if (node) selectTicket(node.dataset.relatedTicketId).catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: node.dataset.relatedTicketId, ticket: { execution: { state: "failed", last_error: String(error) } } }));
    });

    $("notify").onclick = async () => {
      if (!("Notification" in window)) {
        alert("Browser notifications are not supported here.");
        return;
      }
      const permission = await Notification.requestPermission();
      state.notifications = permission === "granted";
      $("notify").textContent = state.notifications ? "Notifications enabled" : `Notifications: ${permission}`;
      if (state.notifications) {
        refreshTickets({ notifyChanges: false, resetSeen: true });
      }
    };
    $("test-notify").onclick = async () => {
      if (!("Notification" in window)) {
        alert("Browser notifications are not supported here.");
        return;
      }
      if (Notification.permission !== "granted") {
        const permission = await Notification.requestPermission();
        state.notifications = permission === "granted";
      }
      if (state.notifications) {
        new Notification("planfile notifications are enabled", { body: "Ticket status changes and errors will appear while this dashboard is open." });
      }
    };
    $("refresh").onclick = () => {
      refreshTickets({ notifyChanges: true });
      refreshSelectedTicket();
    };
    $("queue-filter").onchange = (event) => {
      state.queue = event.target.value;
      localStorage.setItem("planfile.queue", state.queue);
      refreshTickets({ notifyChanges: false, resetSeen: true });
      loadEventHistory().catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
    };
    $("docs").onclick = () => location.href = "/docs";

    $("notify").textContent = state.notifications ? "Notifications enabled" : "Enable notifications";
    refreshTickets().catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
    loadEventHistory().catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
    setInterval(() => {
      refreshTickets({ notifyChanges: true }).catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
      refreshSelectedTicket();
    }, 15000);
    connect();
  </script>
</body>
</html>"""


async def _broadcast_ticket_event(
    event_type: str,
    action: str,
    ticket=None,
    ticket_id: str | None = None,
) -> None:
    """Notify WebSocket clients about ticket lifecycle changes."""
    payload = {
        "type": event_type,
        "action": action,
        "ticket_id": ticket.id if ticket is not None else ticket_id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if ticket is not None:
        payload["ticket"] = ticket.model_dump(mode="json", exclude_none=True)
        _watch_snapshot[ticket.id] = _ticket_signature(ticket)
    _remember_event(payload)
    await _manager.broadcast(payload)


@app.websocket("/ws", name="ws_dsl")
async def websocket_dsl(websocket: WebSocket, project_path: str = "."):
    """WebSocket endpoint — send DSL commands, receive JSON results.

    Protocol:
      Client sends: {"command": "list tickets sprint=current"}
      Server replies: {"ok": true, "data": [...], "message": "Found 3 ticket(s)"}
    """
    from planfile.dsl import DSLExecutor
    await _manager.connect(websocket)
    executor = DSLExecutor(project_path=project_path)
    try:
        await websocket.send_json({"ok": True, "message": "planfile DSL ready. Type 'help' for commands."})
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                command = payload.get("command", raw)
            except (json.JSONDecodeError, AttributeError):
                command = raw.strip()

            if not command:
                continue

            result = executor.run(command)
            await websocket.send_json(result.to_dict())
    except WebSocketDisconnect:
        _manager.disconnect(websocket)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health():
    import planfile
    return {"status": "ok", "version": planfile.__version__}


@app.get("/", response_class=HTMLResponse, tags=["system"])
def root():
    return HTMLResponse(_dashboard_html(), headers=NO_STORE_HEADERS)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
