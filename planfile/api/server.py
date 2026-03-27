"""FastAPI server for planfile — OpenAPI interface.

Run with: uvicorn planfile.api.server:app --reload
"""

from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel
except ImportError:
    raise ImportError("FastAPI required: pip install fastapi uvicorn")

from planfile import Planfile, Ticket, TicketStatus

app = FastAPI(
    title="planfile",
    description="Universal ticket standard — REST API",
    version="0.2.0",
)

_pf: Optional[Planfile] = None


def _get_pf() -> Planfile:
    global _pf
    if _pf is None:
        _pf = Planfile.auto_discover()
    return _pf


# ── Schemas ──

class TicketCreate(BaseModel):
    title: str
    priority: str = "normal"
    sprint: str = "current"
    description: str = ""
    labels: list[str] = []


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None


# ── Endpoints ──

@app.get("/tickets")
def list_tickets(
    sprint: str = Query("current"),
    status: Optional[str] = Query(None),
):
    pf = _get_pf()
    filters = {}
    if status:
        filters["status"] = status
    tickets = pf.list_tickets(sprint=sprint, **filters)
    return [t.model_dump(mode="json", exclude_none=True) for t in tickets]


@app.post("/tickets", status_code=201)
def create_ticket(body: TicketCreate):
    pf = _get_pf()
    ticket = pf.create_ticket(**body.model_dump())
    return ticket.model_dump(mode="json", exclude_none=True)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    pf = _get_pf()
    ticket = pf.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, body: TicketUpdate):
    pf = _get_pf()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ticket = pf.update_ticket(ticket_id, **updates)
    if not ticket:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json", exclude_none=True)


@app.delete("/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: str):
    pf = _get_pf()
    ok = pf.store.delete_ticket(ticket_id)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")


@app.post("/tickets/{ticket_id}/move")
def move_ticket(ticket_id: str, to_sprint: str = Query(...)):
    pf = _get_pf()
    ok = pf.store.move_ticket(ticket_id, to_sprint)
    if not ok:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return {"moved": ticket_id, "to": to_sprint}


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}
