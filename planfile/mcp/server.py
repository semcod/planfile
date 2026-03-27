"""MCP (Model Context Protocol) server for planfile.

Exposes ticket CRUD as MCP tools so LLM agents can manage tickets
directly from their context window.

Run with: python -m planfile.mcp.server
"""

import json
from typing import Optional

from planfile import Planfile, Ticket, TicketSource
from planfile.server_common import get_planfile


# ── MCP tool definitions (JSON-Schema) ──

TOOLS = [
    {
        "name": "planfile_list_tickets",
        "description": "List tickets in a sprint with optional filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sprint": {"type": "string", "default": "current"},
                "status": {"type": "string", "enum": [
                    "open", "in_progress", "review", "done", "blocked"
                ]},
            },
        },
    },
    {
        "name": "planfile_create_ticket",
        "description": "Create a new ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "priority": {"type": "string", "default": "normal"},
                "sprint": {"type": "string", "default": "current"},
                "description": {"type": "string", "default": ""},
                "labels": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["title"],
        },
    },
    {
        "name": "planfile_get_ticket",
        "description": "Get a single ticket by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "planfile_update_ticket",
        "description": "Update ticket fields (status, priority, title).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "planfile_move_ticket",
        "description": "Move a ticket to another sprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "to_sprint": {"type": "string"},
            },
            "required": ["ticket_id", "to_sprint"],
        },
    },
]


# ── Handler dispatch ──

def handle_tool_call(name: str, arguments: dict) -> dict:
    """Dispatch an MCP tool call and return the result dict."""
    pf = get_planfile()

    if name == "planfile_list_tickets":
        filters = {}
        if "status" in arguments:
            filters["status"] = arguments["status"]
        tickets = pf.list_tickets(
            sprint=arguments.get("sprint", "current"), **filters
        )
        return [t.model_dump(mode="json", exclude_none=True) for t in tickets]

    elif name == "planfile_create_ticket":
        ticket = pf.create_ticket(
            title=arguments["title"],
            priority=arguments.get("priority", "normal"),
            sprint=arguments.get("sprint", "current"),
            description=arguments.get("description", ""),
            labels=arguments.get("labels", []),
            source=TicketSource(tool="mcp"),
        )
        return ticket.model_dump(mode="json", exclude_none=True)

    elif name == "planfile_get_ticket":
        ticket = pf.get_ticket(arguments["ticket_id"])
        if not ticket:
            return {"error": f"Ticket {arguments['ticket_id']} not found"}
        return ticket.model_dump(mode="json", exclude_none=True)

    elif name == "planfile_update_ticket":
        updates = {k: v for k, v in arguments.items()
                   if k != "ticket_id" and v is not None}
        ticket = pf.update_ticket(arguments["ticket_id"], **updates)
        if not ticket:
            return {"error": f"Ticket {arguments['ticket_id']} not found"}
        return ticket.model_dump(mode="json", exclude_none=True)

    elif name == "planfile_move_ticket":
        ok = pf.store.move_ticket(arguments["ticket_id"], arguments["to_sprint"])
        if not ok:
            return {"error": f"Ticket {arguments['ticket_id']} not found"}
        return {"moved": arguments["ticket_id"], "to": arguments["to_sprint"]}

    return {"error": f"Unknown tool: {name}"}


# ── Stdio transport (minimal MCP server) ──

def _read_jsonrpc():
    """Read a JSON-RPC message from stdin."""
    import sys
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _write_jsonrpc(obj: dict):
    """Write a JSON-RPC message to stdout."""
    import sys
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    """Run a minimal MCP stdio server."""
    import sys

    while True:
        msg = _read_jsonrpc()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method == "initialize":
            _write_jsonrpc({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "planfile", "version": "0.2.0"},
                },
            })

        elif method == "tools/list":
            _write_jsonrpc({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"tools": TOOLS},
            })

        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments)
            _write_jsonrpc({
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "content": [{"type": "text",
                                 "text": json.dumps(result, default=str)}],
                },
            })

        elif method == "notifications/initialized":
            pass  # no response needed

        else:
            if msg_id is not None:
                _write_jsonrpc({
                    "jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                })


if __name__ == "__main__":
    main()
