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
from typing import Any, Literal

import yaml

try:
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, Response
    from pydantic import BaseModel
except ImportError as exc:
    raise ImportError("FastAPI required: pip install 'fastapi[all]' uvicorn") from exc

from planfile.core.models import TicketExecution, TicketExecutor, TicketInputs, TicketOutputs
from planfile.runtime_context import (
    build_runtime_context,
    load_runtime_context_config,
    save_runtime_context_config,
)
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


class TicketResponseRequest(BaseModel):
    note: str
    next_state: Literal["ready", "in_progress"] = "ready"
    actor: str = "founder"


class TestEventRequest(BaseModel):
    queue: str = "default"
    message: str = "Synthetic dashboard error event"
    state: str = "failed"


class ManagementEventRequest(BaseModel):
    source: str = "koru"
    tool: str = "koru"
    action: str
    ticket_id: str | None = None
    status: str = "info"
    message: str = ""
    queue: str = "default"
    level: str = "info"
    details: dict[str, Any] = {}


class RuntimeContextConfigRequest(BaseModel):
    enabled: dict[str, bool] = {}
    overrides: dict[str, Any] = {}


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


@app.post("/tickets/{ticket_id}/respond", tags=["tickets"])
async def respond_ticket(ticket_id: str, body: TicketResponseRequest):
    pf = get_planfile()
    try:
        ticket = pf.respond_ticket(
            ticket_id,
            note=body.note,
            next_state=body.next_state,
            actor=body.actor.strip() or "dashboard-user",
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    await _broadcast_ticket_event("ticket.execution.changed", "respond", ticket)
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
    ticket_id = str(body.ticket_id or body.details.get("ticket_id") or "-")
    details = dict(body.details)
    if ticket_id != "-":
        details.setdefault("ticket_id", ticket_id)
    payload = {
        "type": "management.event",
        "action": body.action,
        "ticket_id": ticket_id,
        "created_at": datetime.now(UTC).isoformat(),
        "source": body.source,
        "tool": body.tool,
        "queue": body.queue,
        "level": body.level,
        "status": body.status,
        "message": body.message,
        "details": details,
    }
    _remember_event(payload)
    await _manager.broadcast(payload)
    return payload


def _runtime_context_project() -> Path:
    return get_planfile().store.project_dir


@app.get("/api/runtime-context", tags=["runtime-context"])
def get_runtime_context():
    return build_runtime_context(_runtime_context_project())


@app.get("/api/runtime-context/config", tags=["runtime-context"])
def get_runtime_context_config():
    return load_runtime_context_config(_runtime_context_project())


@app.put("/api/runtime-context/config", tags=["runtime-context"])
def update_runtime_context_config(body: RuntimeContextConfigRequest):
    return save_runtime_context_config(_runtime_context_project(), body.model_dump())


@app.get("/runtime-context", response_class=HTMLResponse, tags=["runtime-context"])
def runtime_context_page():
    return HTMLResponse(_runtime_context_html(), headers=NO_STORE_HEADERS)


def _runtime_context_html() -> str:
    return r"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Planfile Runtime Context</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font-family: Inter, system-ui, sans-serif; background: #020617; color: #e5e7eb; }
    header { position: sticky; top: 0; z-index: 2; padding: 16px 24px; border-bottom: 1px solid #1e293b; background: rgba(15,23,42,.96); backdrop-filter: blur(10px); }
    h1 { margin: 0 0 6px; font-size: 24px; }
    h2 { margin: 0 0 12px; font-size: 18px; }
    h3 { margin: 14px 0 8px; font-size: 15px; color: #bae6fd; }
    button { cursor: pointer; border: 1px solid #334155; border-radius: 10px; padding: 8px 12px; color: #e5e7eb; background: #0f172a; }
    button.primary { border-color: #0284c7; background: #0369a1; }
    main { display: grid; grid-template-columns: 280px 1fr; gap: 18px; padding: 18px; }
    aside, section { border: 1px solid #1e293b; border-radius: 14px; background: #0f172a; padding: 16px; }
    label { display: flex; align-items: center; gap: 8px; margin: 10px 0; color: #cbd5e1; }
    input[type="checkbox"] { width: 18px; height: 18px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
    .card { border: 1px solid #334155; border-radius: 12px; padding: 14px; background: #111827; }
    .muted { color: #94a3b8; }
    .pill { display: inline-block; margin: 2px; padding: 3px 8px; border-radius: 999px; background: #1e293b; color: #bfdbfe; font-size: 12px; }
    pre { overflow: auto; max-height: 520px; padding: 12px; border-radius: 10px; background: #020617; border: 1px solid #1e293b; }
    code { color: #bae6fd; }
    .summary { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
    .summary span { padding: 6px 10px; border-radius: 999px; background: #172554; color: #bfdbfe; }
    a { color: #7dd3fc; text-decoration: none; }
    @media (max-width: 820px) { main { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<header>
  <h1>Topology / Runtime Context</h1>
  <div class="muted">Systemy, biblioteki, algorytmy, API, aplikacje i pipeline’y aktualnego projektu planfile.</div>
  <div class="summary" id="summary"></div>
</header>
<main>
  <aside>
    <h2>Widoczność sekcji</h2>
    <div id="checks"></div>
    <div class="toolbar">
      <button class="primary" onclick="saveConfig()">Zapisz</button>
      <button onclick="loadContext()">Odśwież</button>
      <button onclick="showRaw()">JSON</button>
    </div>
    <p class="muted">Checkboxy zapisują konfigurację w <code>.koru/runtime-context.json</code>.</p>
    <p><a href="/">← dashboard</a></p>
  </aside>
  <section>
    <div id="content"></div>
  </section>
</main>
<script>
const labels = {
  systems: 'Systemy / kontenery', libraries: 'Biblioteki i zależności', algorithms: 'Algorytmy',
  apis: 'API', applications: 'Aplikacje', pipelines: 'Pipeline’y / taski', topology: 'Graf topologii'
};
let ctx = null;
let cfg = null;
async function loadContext() {
  ctx = await fetch('/api/runtime-context', {cache: 'no-store'}).then(r => r.json());
  cfg = ctx.config;
  renderChecks(); renderSummary(); renderContent();
}
function renderChecks() {
  document.getElementById('checks').innerHTML = Object.entries(labels).map(([key, label]) =>
    `<label><input type="checkbox" data-key="${key}" ${cfg.enabled[key] ? 'checked' : ''}> ${label}</label>`
  ).join('');
}
function renderSummary() {
  const s = ctx.summary || {};
  document.getElementById('summary').innerHTML = [
    `project: ${s.project || '-'}`, `version: ${s.version || '-'}`, `services: ${s.services || 0}`,
    `workspaces: ${s.workspaces || 0}`, `pipelines: ${s.pipelines || 0}`, `topology nodes: ${s.topology_nodes || 0}`
  ].map(v => `<span>${escapeHtml(v)}</span>`).join('');
}
async function saveConfig() {
  const enabled = {};
  document.querySelectorAll('input[type="checkbox"]').forEach(input => enabled[input.dataset.key] = input.checked);
  cfg = await fetch('/api/runtime-context/config', {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...cfg, enabled})
  }).then(r => r.json());
  await loadContext();
}
function showRaw() { document.getElementById('content').innerHTML = `<pre>${escapeHtml(JSON.stringify(ctx, null, 2))}</pre>`; }
function renderContent() {
  const parts = [];
  if (ctx.systems?.length) parts.push(section('Systemy', ctx.systems.map(service => card(
    service.name,
    [`compose: ${(service.compose_files || []).join(', ')}`, `ports: ${(service.ports || []).join(', ') || '-'}`, `depends: ${(service.depends_on || []).join(', ') || '-'}`],
    Object.keys(service.environment || {}).slice(0, 12)
  )).join('')));
  if (ctx.libraries?.node || ctx.libraries?.python) parts.push(section('Biblioteki', [
    ctx.libraries.node ? card(`Node: ${ctx.libraries.node.name}`, [ctx.libraries.node.description || '', `workspaces: ${(ctx.libraries.node.workspaces || []).length}`], Object.keys(ctx.libraries.node.dependencies || {}).concat(Object.keys(ctx.libraries.node.devDependencies || {}))) : '',
    ctx.libraries.python ? card(`Python: ${ctx.libraries.python.name}`, [ctx.libraries.python.description || '', `version: ${ctx.libraries.python.version || '-'}`], ctx.libraries.python.dependencies || []) : ''
  ].join('')));
  if (ctx.algorithms?.length) parts.push(section('Algorytmy', ctx.algorithms.map(a => card(a.name, [a.role, a.source], [])).join('')));
  if (ctx.apis?.length) parts.push(section('API', ctx.apis.map(a => card(a.name, [a.base_url], a.endpoints || [])).join('')));
  if (ctx.applications?.length) parts.push(section('Aplikacje', ctx.applications.map(a => card(a.name, [a.role, a.url], [])).join('')));
  if (ctx.pipelines?.length) parts.push(section('Pipeline’y', ctx.pipelines.map(p => card(p.name, [p.description || '-', p.interactive ? 'interactive' : 'batch'], [])).join('')));
  if (ctx.topology?.node_count !== undefined) parts.push(section('Topologia', card('TestQL topology', [`nodes: ${ctx.topology.node_count}`, `edges: ${ctx.topology.edge_count}`, `traces: ${ctx.topology.trace_count}`, `confidence: ${ctx.topology.confidence || '-'}`], (ctx.topology.metadata?.source_types || [])) + `<pre>${escapeHtml(JSON.stringify({nodes: ctx.topology.nodes, edges: ctx.topology.edges, traces: ctx.topology.traces}, null, 2))}</pre>`));
  document.getElementById('content').innerHTML = parts.join('') || '<p class="muted">Brak aktywnych sekcji. Włącz sekcje checkboxami.</p>';
}
function section(title, html) { return `<h2>${escapeHtml(title)}</h2><div class="grid">${html}</div>`; }
function card(title, lines, pills) { return `<div class="card"><h3>${escapeHtml(title || '-')}</h3>${(lines || []).filter(Boolean).map(line => `<div class="muted">${escapeHtml(String(line))}</div>`).join('')}<div>${(pills || []).slice(0, 30).map(p => `<span class="pill">${escapeHtml(String(p))}</span>`).join('')}</div></div>`; }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch])); }
loadContext();
</script>
</body>
</html>"""


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
    .new-ticket {
      padding: 14px;
      border-top: 1px solid var(--line);
    }
    .new-ticket h3 {
      margin: 0 0 10px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 620;
    }
    .form-grid { display: grid; gap: 10px; }
    .form-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: flex-end;
    }
    .form-row label.field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      min-width: 100px;
      flex: 1;
    }
    .form-row input, .form-row textarea, .form-row select {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }
    .form-row textarea { min-height: 72px; resize: vertical; width: 100%; }
    .form-msg { font-size: 12px; margin-top: 8px; min-height: 1.2em; }
    .form-msg.err { color: var(--err); }
    .form-msg.ok { color: var(--ok); }
    label.field-block {
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
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
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0;
    }
    .tab.active {
      border-color: var(--info);
      color: var(--text);
      background: #213048;
    }
    .detail-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin: 0 0 12px;
    }
    .detail-actions .copy-feedback {
      font-size: 12px;
      color: var(--ok);
    }
    .detail-actions .copy-feedback.err {
      color: var(--err);
    }
    .ticket-response {
      margin: 0 0 14px;
      padding: 12px;
      border: 1px solid #31516f;
      border-radius: 8px;
      background: #182230;
    }
    .ticket-response h4 {
      margin: 0 0 8px;
      font-size: 13px;
    }
    .ticket-response textarea {
      min-height: 110px;
      width: 100%;
      resize: vertical;
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
    }
    .ticket-response .response-controls {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      gap: 10px;
      margin-top: 10px;
    }
    .ticket-response .response-controls label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
    }
    .ticket-response .response-controls button { margin-left: auto; }
    .ticket-response .form-msg { flex-basis: 100%; }
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
      <h1>planfile queue dashboard <a href="/runtime-context" style="color: var(--info); font-size: 13px; margin-left: 12px; text-decoration: none;">Topology / Runtime Context</a></h1>
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
        <label for="status-filter" class="status">Status</label>
        <select id="status-filter">
          <option value="active">active</option>
          <option value="all">all</option>
        </select>
      </div>
      <div class="metrics">
        <div class="metric"><strong id="m-open">0</strong><span>open</span></div>
        <div class="metric"><strong id="m-running">0</strong><span>running</span></div>
        <div class="metric"><strong id="m-waiting">0</strong><span>waiting</span></div>
        <div class="metric"><strong id="m-failed">0</strong><span>failed</span></div>
      </div>
      <div class="new-ticket">
        <h3>New ticket</h3>
        <form id="new-ticket-form">
          <div class="form-grid">
            <div class="form-row">
              <label class="field">Title
                <input type="text" id="nt-name" required maxlength="500" placeholder="Short title" autocomplete="off" />
              </label>
              <label class="field">Priority
                <select id="nt-priority">
                  <option value="normal">normal</option>
                  <option value="low">low</option>
                  <option value="high">high</option>
                  <option value="critical">critical</option>
                </select>
              </label>
              <label class="field">Sprint
                <input type="text" id="nt-sprint" value="current" />
              </label>
              <label class="field">Queue
                <input type="text" id="nt-queue" placeholder="defaults from filter or default" autocomplete="off" />
              </label>
            </div>
            <label class="field-block">Description
              <textarea id="nt-desc" placeholder="Optional details"></textarea>
            </label>
            <div class="form-row">
              <label class="field">Labels
                <input type="text" id="nt-labels" placeholder="comma-separated, e.g. bug, triage" autocomplete="off" />
              </label>
              <label class="field">Executor kind
                <select id="nt-executor">
                  <option value="human">human</option>
                  <option value="shell">shell</option>
                  <option value="llm">llm</option>
                </select>
              </label>
            </div>
            <div class="form-row">
              <button type="submit" id="nt-submit">Create ticket</button>
            </div>
          </div>
          <div id="nt-msg" class="form-msg" aria-live="polite"></div>
        </form>
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
      queue: "all",
      statusFilter: "active",
      selectedTicketId: null,
      selectedTicket: null,
      ticketEvents: [],
      detailTab: "overview",
      activeViewTicketId: null,
      responseFeedback: null,
      responseSubmitting: false,
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
    const detailTabs = new Set(["overview", "timeline", "logs", "raw"]);
    const commonStatusFilters = ["active", "all", "open", "in_progress", "ready", "pending", "running", "waiting_input", "waiting", "failed", "done", "canceled"];

    function normalizeTab(tab) {
      return detailTabs.has(tab) ? tab : "overview";
    }

    function applyUrlState() {
      const params = new URLSearchParams(location.search);
      state.queue = params.get("queue") || localStorage.getItem("planfile.queue") || "all";
      state.statusFilter = params.get("status") || localStorage.getItem("planfile.statusFilter") || "active";
      state.selectedTicketId = params.get("ticket") || params.get("ticket_id") || null;
      state.detailTab = normalizeTab(params.get("tab") || localStorage.getItem("planfile.detailTab") || "overview");
    }

    function syncUrlState(options = {}) {
      const params = new URLSearchParams(location.search);
      if (state.queue && state.queue !== "all") params.set("queue", state.queue);
      else params.delete("queue");
      if (state.statusFilter && state.statusFilter !== "active") params.set("status", state.statusFilter);
      else params.delete("status");
      if (state.selectedTicketId) params.set("ticket", state.selectedTicketId);
      else {
        params.delete("ticket");
        params.delete("ticket_id");
      }
      if (state.detailTab && state.detailTab !== "overview") params.set("tab", state.detailTab);
      else params.delete("tab");
      const query = params.toString();
      const nextUrl = `${location.pathname}${query ? `?${query}` : ""}${location.hash || ""}`;
      const currentUrl = `${location.pathname}${location.search}${location.hash || ""}`;
      if (nextUrl === currentUrl) return;
      const payload = { queue: state.queue, status: state.statusFilter, ticket: state.selectedTicketId, tab: state.detailTab };
      if (options.replace) history.replaceState(payload, "", nextUrl);
      else history.pushState(payload, "", nextUrl);
    }

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

    function ticketLifecycleValues(ticket) {
      return new Set([
        String(ticket?.status || "unknown"),
        String(ticketState(ticket)),
      ]);
    }

    function isActiveTicket(ticket) {
      const values = ticketLifecycleValues(ticket);
      return !values.has("done") && !values.has("canceled") && !values.has("cancelled");
    }

    function ticketMatchesStatus(ticket) {
      if (state.statusFilter === "all") return true;
      if (state.statusFilter === "active") return isActiveTicket(ticket);
      return ticketLifecycleValues(ticket).has(state.statusFilter);
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
      return tickets.filter((ticket) => {
        const queueMatches = state.queue === "all" || ticketQueue(ticket) === state.queue;
        return queueMatches && ticketMatchesStatus(ticket);
      });
    }

    function updateQueueOptions(tickets) {
      const queues = Array.from(new Set(tickets.map(ticketQueue))).sort();
      const select = $("queue-filter");
      const html = ['<option value="all">all</option>', ...queues.map((queue) => `<option value="${escapeHtml(queue)}">${escapeHtml(queue)}</option>`)].join("");
      if (select.innerHTML !== html) select.innerHTML = html;
      if (!["all", ...queues].includes(state.queue)) state.queue = "all";
      select.value = state.queue;
    }

    function updateStatusOptions(tickets) {
      const discovered = new Set(commonStatusFilters);
      for (const ticket of tickets) {
        for (const value of ticketLifecycleValues(ticket)) {
          if (value && value !== "unknown") discovered.add(value);
        }
      }
      const statuses = Array.from(discovered);
      const labels = {
        active: "active",
        all: "all",
        in_progress: "in progress",
        waiting_input: "waiting input",
      };
      const select = $("status-filter");
      const html = statuses.map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(labels[status] || status)}</option>`).join("");
      if (select.innerHTML !== html) select.innerHTML = html;
      if (!statuses.includes(state.statusFilter)) state.statusFilter = "active";
      select.value = state.statusFilter;
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

    function ticketDetailExportPayload(tab) {
      const ticket = state.selectedTicket;
      const events = state.ticketEvents || [];
      const activeTab = tab || state.detailTab || "overview";
      const base = {
        exported_at: new Date().toISOString(),
        ticket_id: ticket?.id || null,
        tab: activeTab,
      };
      if (!ticket) return base;
      if (activeTab === "timeline") {
        return {
          ...base,
          ticket,
          timeline: buildTicketTimeline(ticket, events),
          events,
        };
      }
      if (activeTab === "logs") {
        return { ...base, ticket, events };
      }
      if (activeTab === "raw") {
        return { ...base, ticket };
      }
      return {
        ...base,
        ticket,
        timeline: buildTicketTimeline(ticket, events),
        events,
      };
    }

    async function copyJsonToClipboard(text) {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return;
      }
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      try {
        if (!document.execCommand("copy")) {
          throw new Error("execCommand('copy') failed");
        }
      } finally {
        document.body.removeChild(area);
      }
    }

    async function copyTicketDetailJson(options = {}) {
      if (!state.selectedTicket) {
        throw new Error("Select a ticket first");
      }
      const tab = options.tab || state.detailTab;
      const json = JSON.stringify(ticketDetailExportPayload(tab), null, 2);
      await copyJsonToClipboard(json);
      return json.length;
    }

    function renderDetailTabs() {
      const labels = {
        overview: "Overview",
        timeline: "Timeline",
        logs: "Tool logs",
        raw: "Raw JSON",
      };
      return `<div class="tabs">${Array.from(detailTabs).map((tab) => `
        <button class="tab ${tab === state.detailTab ? "active" : ""}" data-detail-tab="${escapeHtml(tab)}">${escapeHtml(labels[tab] || tab)}</button>
      `).join("")}</div>`;
    }

    function renderDetailActions() {
      if (!state.selectedTicket) return "";
      return `<div class="detail-actions">
        <button type="button" data-copy-ticket-json title="Copy ticket payload for the active tab as JSON">Copy JSON to clipboard</button>
        <span class="copy-feedback" id="copy-json-feedback" hidden aria-live="polite"></span>
      </div>`;
    }

    function renderTicketResponseForm(ticket) {
      if (!ticket) return "";
      const terminal = ["done", "canceled", "blocked"].includes(String(ticket.status || ""))
        || ticket?.execution?.state === "done";
      if (terminal) return "";
      const feedback = state.responseFeedback?.ticketId === ticket.id ? state.responseFeedback : null;
      const disabled = state.responseSubmitting ? "disabled" : "";
      return `<form class="ticket-response" data-ticket-response-form data-ticket-id="${escapeHtml(ticket.id)}">
        <h4>Respond to this ticket</h4>
        <label class="field-block" for="ticket-response-note">Response</label>
        <textarea id="ticket-response-note" name="note" required placeholder="Write the decision, answer, or information needed to continue..." ${disabled}></textarea>
        <div class="response-controls">
          <label for="ticket-response-state">Status after response
            <select id="ticket-response-state" name="next_state" ${disabled}>
              <option value="ready" selected>READY — response complete</option>
              <option value="in_progress">IN PROGRESS — continue working</option>
            </select>
          </label>
          <button type="submit" ${disabled}>${state.responseSubmitting ? "Sending..." : "Send response"}</button>
          <div class="form-msg ${feedback?.kind === "error" ? "err" : feedback ? "ok" : ""}" data-response-feedback aria-live="polite">${escapeHtml(feedback?.text || "")}</div>
        </div>
      </form>`;
    }

    function renderTicketEventLog(events) {
      if (!events.length) return '<div class="empty">No management or tool events linked to this ticket yet.</div>';
      return `<div class="timeline">${events.map((event) => {
        const management = event.type === "management.event";
        const title = management
          ? `${event.source || "koru"} / ${event.tool || "tool"} / ${event.action || "-"}`
          : `${event.type || "event"} / ${event.action || "-"}`;
        const message = management ? event.message : event.ticket?.name;
        const details = management ? event.details : event.ticket?.execution?.last_error;
        const level = eventLevel(event);
        return `
          <div class="timeline-item ${escapeHtml(level)}">
            <div class="title">${escapeHtml(title)}</div>
            <div class="meta"><span class="pill ${escapeHtml(level)}">${escapeHtml(level)}</span><span>${escapeHtml(formatDate(event.created_at))}</span></div>
            ${message ? `<pre>${escapeHtml(message)}</pre>` : ""}
            ${details ? `<pre>${escapeHtml(stringifyDetail(details))}</pre>` : ""}
          </div>
        `;
      }).join("")}</div>`;
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
      const overviewHtml = `
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
      `;
      const tabHtml = {
        overview: overviewHtml,
        timeline: detailBlock("Timeline", renderTicketTimeline(ticket, events)),
        logs: detailBlock("Tool logs", renderTicketEventLog(events)),
        raw: detailBlock("Raw ticket JSON", `<pre>${escapeHtml(JSON.stringify(ticket, null, 2))}</pre>`),
      }[state.detailTab] || overviewHtml;
      detailStatusEl.textContent = ticket.id;
      detailEl.className = "detail";
      detailEl.innerHTML = `
        <h3>${escapeHtml(ticket.id)} ${escapeHtml(ticket.name)}</h3>
        <div class="meta">
          <span class="pill ${escapeHtml(stateName)}">${escapeHtml(statusLabel(ticket))}</span>
          <span class="pill">${escapeHtml(ticket.priority || "normal")}</span>
          <span class="pill">${escapeHtml(ticketQueue(ticket))}</span>
        </div>
        ${renderDetailTabs()}
        ${renderDetailActions()}
        ${renderTicketResponseForm(ticket)}
        ${tabHtml}
      `;
    }

    async function beginTicketWork(ticket) {
      if (!ticket || state.activeViewTicketId === ticket.id) return ticket;
      state.activeViewTicketId = ticket.id;
      const execution = ticket.execution || {};
      const executor = ticket.executor || {};
      const terminal = ["done", "canceled", "blocked"].includes(String(ticket.status || ""))
        || ["done", "running"].includes(String(execution.state || ""));
      const interactiveHuman = executor.kind === "human" && executor.mode === "interactive";
      if (!interactiveHuman || terminal || ticket.status === "in_progress") return ticket;
      const assignedTo = executor.handler || execution.assigned_to || ticketQueue(ticket) || "dashboard-human";
      const response = await fetch(`/tickets/${encodeURIComponent(ticket.id)}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assigned_to: assignedTo }),
      });
      if (!response.ok) throw new Error(`Starting ${ticket.id} returned HTTP ${response.status}`);
      return response.json();
    }

    async function selectTicket(ticketId, options = {}) {
      if (!ticketId) return;
      state.selectedTicketId = ticketId;
      if (options.updateUrl !== false) syncUrlState();
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
      try {
        state.selectedTicket = await beginTicketWork(state.selectedTicket);
      } catch (error) {
        state.responseFeedback = { ticketId, kind: "error", text: String(error) };
      }
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
      updateStatusOptions(tickets);
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
        syncUrlState({ replace: true });
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
      const copyBtn = event.target.closest("[data-copy-ticket-json]");
      if (copyBtn) {
        event.preventDefault();
        const feedback = $("copy-json-feedback");
        if (feedback) {
          feedback.hidden = false;
          feedback.className = "copy-feedback";
          feedback.textContent = "Copying...";
        }
        copyTicketDetailJson()
          .then((length) => {
            if (feedback) {
              feedback.textContent = `Copied ${length} characters`;
              feedback.className = "copy-feedback";
            } else if (state.selectedTicketId) {
              detailStatusEl.textContent = `${state.selectedTicketId} — JSON copied`;
            }
          })
          .catch((error) => {
            const message = String(error);
            if (feedback) {
              feedback.textContent = message;
              feedback.className = "copy-feedback err";
            } else {
              alert(message);
            }
          });
        return;
      }
      const tabNode = event.target.closest("[data-detail-tab]");
      if (tabNode) {
        state.detailTab = normalizeTab(tabNode.dataset.detailTab);
        localStorage.setItem("planfile.detailTab", state.detailTab);
        syncUrlState();
        renderTicketDetail(state.selectedTicket, state.ticketEvents);
        return;
      }
      const node = event.target.closest("[data-related-ticket-id]");
      if (node) selectTicket(node.dataset.relatedTicketId).catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: node.dataset.relatedTicketId, ticket: { execution: { state: "failed", last_error: String(error) } } }));
    });

    detailEl.addEventListener("submit", async (event) => {
      const form = event.target.closest("[data-ticket-response-form]");
      if (!form) return;
      event.preventDefault();
      const ticketId = form.dataset.ticketId;
      const data = new FormData(form);
      const note = String(data.get("note") || "").trim();
      const nextState = String(data.get("next_state") || "ready");
      const feedback = form.querySelector("[data-response-feedback]");
      if (!note) {
        if (feedback) {
          feedback.className = "form-msg err";
          feedback.textContent = "Response is required.";
        }
        return;
      }
      state.responseSubmitting = true;
      for (const control of form.querySelectorAll("button, textarea, select")) control.disabled = true;
      if (feedback) {
        feedback.className = "form-msg";
        feedback.textContent = "Sending response...";
      }
      try {
        const actor = state.selectedTicket?.executor?.handler
          || state.selectedTicket?.execution?.assigned_to
          || ticketQueue(state.selectedTicket)
          || "dashboard-user";
        const response = await fetch(`/tickets/${encodeURIComponent(ticketId)}/respond`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note, next_state: nextState, actor }),
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({}));
          throw new Error(payload.detail || `Response failed with HTTP ${response.status}`);
        }
        state.selectedTicket = await response.json();
        state.responseFeedback = {
          ticketId,
          kind: "success",
          text: `Response saved. Ticket is ${nextState === "ready" ? "READY" : "IN PROGRESS"}.`,
        };
        await refreshTickets({ notifyChanges: false });
      } catch (error) {
        state.responseFeedback = { ticketId, kind: "error", text: String(error) };
      } finally {
        state.responseSubmitting = false;
        renderTicketDetail(state.selectedTicket, state.ticketEvents);
      }
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

    $("new-ticket-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const msg = $("nt-msg");
      msg.textContent = "";
      msg.className = "form-msg";
      const name = $("nt-name").value.trim();
      if (!name) {
        msg.textContent = "Title is required.";
        msg.classList.add("err");
        return;
      }
      const queueInput = $("nt-queue").value.trim();
      const queue =
        queueInput || (state.queue === "all" ? "default" : state.queue);
      const labels = $("nt-labels")
        .value.split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      const execKind = $("nt-executor").value;
      const mode = execKind === "human" ? "interactive" : "automatic";
      const body = {
        name,
        priority: $("nt-priority").value,
        sprint: $("nt-sprint").value.trim() || "current",
        description: $("nt-desc").value.trim(),
        labels,
        executor: { kind: execKind, mode },
        execution: { queue, state: "ready" },
      };
      try {
        const response = await fetch("/tickets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!response.ok) {
          let detail = response.statusText || "Create failed";
          try {
            const err = await response.json();
            if (Array.isArray(err.detail)) {
              detail = err.detail
                .map((item) =>
                  typeof item === "object" && item.msg ? item.msg : String(item)
                )
                .join("; ");
            } else if (typeof err.detail === "string") {
              detail = err.detail;
            }
          } catch {
            /* ignore */
          }
          msg.textContent = detail;
          msg.classList.add("err");
          return;
        }
        const created = await response.json();
        msg.textContent = `Created ${created.id}`;
        msg.classList.add("ok");
        $("nt-name").value = "";
        $("nt-desc").value = "";
        $("nt-labels").value = "";
        await refreshTickets({ notifyChanges: false, resetSeen: false });
        await selectTicket(created.id);
      } catch (error) {
        msg.textContent = String(error);
        msg.classList.add("err");
      }
    });
    $("queue-filter").onchange = (event) => {
      state.queue = event.target.value;
      localStorage.setItem("planfile.queue", state.queue);
      syncUrlState();
      refreshTickets({ notifyChanges: false, resetSeen: true });
      loadEventHistory().catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
    };
    $("status-filter").onchange = (event) => {
      state.statusFilter = event.target.value;
      localStorage.setItem("planfile.statusFilter", state.statusFilter);
      syncUrlState();
      refreshTickets({ notifyChanges: false, resetSeen: true });
    };
    $("docs").onclick = () => location.href = "/docs";

    $("notify").textContent = state.notifications ? "Notifications enabled" : "Enable notifications";

    async function initializeDashboard() {
      applyUrlState();
      syncUrlState({ replace: true });
      await refreshTickets();
      await loadEventHistory();
      if (state.selectedTicketId) {
        await selectTicket(state.selectedTicketId, { silent: true, updateUrl: false });
      }
    }

    window.addEventListener("popstate", () => {
      applyUrlState();
      refreshTickets({ notifyChanges: false, resetSeen: true })
        .then(() => loadEventHistory())
        .then(() => {
          if (state.selectedTicketId) return selectTicket(state.selectedTicketId, { silent: true, updateUrl: false });
          state.activeViewTicketId = null;
          renderTicketDetail(null);
          return null;
        })
        .catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
    });

    initializeDashboard().catch((error) => addEvent({ type: "dashboard", action: "error", ticket_id: "-", ticket: { execution: { state: "failed", last_error: String(error) } } }));
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
