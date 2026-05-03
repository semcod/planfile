"""FastAPI server for planfile — REST + WebSocket + DSL API.

Run with: uvicorn planfile.api.server:app --reload
"""

from __future__ import annotations

import json
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("FastAPI required: pip install 'fastapi[all]' uvicorn")

from planfile.server_common import get_planfile

app = FastAPI(
    title="planfile",
    description="Universal ticket standard — REST + WebSocket + DSL API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    name: str
    priority: str = "normal"
    sprint: str = "current"
    description: str = ""
    labels: list[str] = []


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    name: str | None = None
    description: str | None = None
    labels: list[str] | None = None


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


# ── Tickets ────────────────────────────────────────────────────────────────────

@app.get("/tickets", tags=["tickets"])
def list_tickets(
    sprint: str = Query("current"),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    source: str | None = Query(None),
):
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
def create_ticket(body: TicketCreate):
    pf = get_planfile()
    from planfile import TicketSource
    ticket = pf.create_ticket(
        name=body.name,
        priority=body.priority,
        sprint=body.sprint,
        description=body.description,
        labels=body.labels,
        source=TicketSource(tool="api"),
    )
    return ticket.model_dump(mode="json", exclude_none=True)


@app.get("/tickets/{ticket_id}", tags=["tickets"])
def get_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.patch("/tickets/{ticket_id}", tags=["tickets"])
def update_ticket(ticket_id: str, body: TicketUpdate):
    pf = get_planfile()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ticket = pf.update_ticket(ticket_id, **updates)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.delete("/tickets/{ticket_id}", status_code=204, tags=["tickets"])
def delete_ticket(ticket_id: str):
    pf = get_planfile()
    ok = pf.store.delete_ticket(ticket_id)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")


@app.post("/tickets/{ticket_id}/move", tags=["tickets"])
def move_ticket(ticket_id: str, to_sprint: str = Query(...)):
    pf = get_planfile()
    ok = pf.store.move_ticket(ticket_id, to_sprint)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return {"moved": ticket_id, "to": to_sprint}


@app.post("/tickets/{ticket_id}/done", tags=["tickets"])
def done_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.update_ticket(ticket_id, status="done")
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.post("/tickets/{ticket_id}/start", tags=["tickets"])
def start_ticket(ticket_id: str):
    pf = get_planfile()
    ticket = pf.update_ticket(ticket_id, status="in_progress")
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


# ── Sprints ────────────────────────────────────────────────────────────────────

@app.get("/sprints", tags=["sprints"])
def list_sprints():
    import yaml
    from pathlib import Path
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        return []
    with open(pf_path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("sprints", [])


@app.post("/sprints", status_code=201, tags=["sprints"])
def create_sprint(body: SprintCreate):
    import yaml
    from pathlib import Path
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
    import yaml
    from pathlib import Path
    pf = get_planfile()
    pf_path = Path(pf.store.project_dir) / "planfile.yaml"
    if not pf_path.exists():
        raise HTTPException(404, "planfile.yaml not found")
    with open(pf_path) as f:
        return yaml.safe_load(f) or {}


@app.patch("/yaml", tags=["yaml"])
def patch_yaml(body: YAMLPatchRequest):
    """Patch a top-level key in planfile.yaml. path=key, value=new_value."""
    import yaml
    from pathlib import Path
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
    from planfile.dsl import DSLExecutor, DSLCommand
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


@app.get("/", tags=["system"])
def root():
    return {
        "service": "planfile",
        "docs": "/docs",
        "ws": "/ws",
        "dsl": "/dsl",
        "tickets": "/tickets",
        "sprints": "/sprints",
        "yaml": "/yaml",
    }
