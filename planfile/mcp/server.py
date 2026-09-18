"""MCP (Model Context Protocol) server for planfile.

Exposes ticket CRUD as MCP tools so LLM agents can manage tickets
directly from their context window.

Run with: python -m planfile.mcp.server
"""

import json
import os
from pathlib import Path

from planfile import TicketSource
from planfile.server_common import get_planfile

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_MUTATING_TOOLS = frozenset(
    {
        "planfile_create_ticket",
        "planfile_update_ticket",
        "planfile_move_ticket",
        "planfile_yaml_patch",
    }
)
_READ_ONLY_DSL_VERBS = frozenset({"get", "help", "list", "query", "show", "validate"})


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUE_VALUES


def _require_mutation(action: str) -> None:
    if not _enabled("PLANFILE_MCP_ALLOW_MUTATION"):
        raise PermissionError(
            f"MCP mutation '{action}' is disabled; set PLANFILE_MCP_ALLOW_MUTATION=1"
        )


def _project_root() -> Path:
    return Path(os.getenv("PLANFILE_MCP_PROJECT_ROOT", ".")).expanduser().resolve()


def _require_project_path(raw_path: object) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("project_path must be a non-empty string")
    candidate = Path(raw_path).expanduser().resolve(strict=False)
    try:
        candidate.relative_to(_project_root())
    except ValueError as exc:
        raise PermissionError(
            "planfile MCP path is outside PLANFILE_MCP_PROJECT_ROOT"
        ) from exc
    return str(candidate)


def _guard_tool_call(name: str, arguments: dict) -> None:
    if "project_path" in arguments or name in {
        "planfile_dsl",
        "planfile_ask",
        "planfile_yaml_get",
        "planfile_yaml_patch",
        "planfile_list_sprints",
    }:
        _require_project_path(arguments.get("project_path", "."))

    if name in _MUTATING_TOOLS:
        _require_mutation(name)
    elif name in ("planfile_dsl", "planfile_ask"):
        command = str(arguments.get("command") or arguments.get("query") or "").strip()
        from planfile.dsl.parser import DSLParser
        parsed = DSLParser().parse(command)
        if parsed.verb not in _READ_ONLY_DSL_VERBS:
            _require_mutation(name)

# ── MCP tool definitions (JSON-Schema) ──

TOOLS = [
    {
        "name": "planfile_ask",
        "description": (
            "Ask a natural language query in Polish or English to inspect or modify planfile resources "
            "via the NL-DSL-LLM pattern. Fast-path supports PL/EN verbs and adjectives; falls back to LLM translation. "
            "Examples: 'pokaż otwarte zadania', 'show open tickets', 'dodaj zadanie Napraw bug', 'zamknij zadanie PLF-001'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query in Polish or English",
                },
                "project_path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path to project directory (default: current directory)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "planfile_describe_grammar",
        "description": "Return the supported DSL and natural language grammar, vocabulary, and usage examples.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "planfile_dsl",
        "description": (
            "Execute a natural language / DSL command against planfile. "
            "Supports: create/list/show/update/move/done/start/block/delete ticket(s), "
            "list/add sprint, safe list/show/set configuration, validate, sync, query, export. "
            "Examples: 'create ticket \"Fix login\" priority=high', "
            "'list tickets sprint=current status=open', "
            "'update ticket PLF-001 status=done', "
            "'move ticket PLF-001 to sprint=2', "
            "'set config store.storage.index=sqlite', "
            "'set config integrations.github.repo=owner/repo if_revision=cfg_...', "
            "'done ticket PLF-001', 'validate', 'sync github', 'help'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "DSL command string",
                },
                "project_path": {
                    "type": "string",
                    "default": ".",
                    "description": "Path to project directory (default: current directory)",
                },
            },
            "required": ["command"],
        },
    },
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
                "name": {"type": "string"},
                "priority": {"type": "string", "default": "normal"},
                "sprint": {"type": "string", "default": "current"},
                "description": {"type": "string", "default": ""},
                "labels": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["name"],
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
        "description": "Update ticket fields (status, priority, name).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "status": {"type": "string"},
                "priority": {"type": "string"},
                "name": {"type": "string"},
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
    {
        "name": "planfile_yaml_get",
        "description": "Read the full planfile.yaml as a JSON object.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "default": "."},
            },
        },
    },
    {
        "name": "planfile_yaml_patch",
        "description": (
            "Patch a key in planfile.yaml using dot-notation path. "
            "Example: path='metadata.model_tier', value='balanced'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Dot-separated key path, e.g. 'metadata.model_tier'"},
                "value": {"description": "New value to set (any JSON type)"},
                "project_path": {"type": "string", "default": "."},
            },
            "required": ["path", "value"],
        },
    },
    {
        "name": "planfile_list_sprints",
        "description": "List all sprints from planfile.yaml.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "default": "."},
            },
        },
    },
]


# ── Handler dispatch ──

def _planfile_yaml_path(arguments: dict) -> Path:
    """Bind an explicit project to its own plan without consulting the global cache."""
    if "project_path" in arguments:
        return Path(_require_project_path(arguments["project_path"])) / "planfile.yaml"
    return Path(get_planfile().store.project_dir) / "planfile.yaml"


def _require_initialized_store(project: Path, *, allow_initialize: bool = False) -> None:
    """Check the effective store before a constructor can read or initialize it."""
    store = project / ".planfile"
    # Do not follow directory symlinks during inspection. A symlink to a
    # different project is forbidden even when both projects are allowlisted.
    paths = [store, project / "planfile.yaml"]
    if store.is_dir() and not store.is_symlink():
        paths.extend(store.rglob("*"))
    for path in paths:
        try:
            path.resolve().relative_to(project)
        except (ValueError, RuntimeError) as exc:
            raise PermissionError("MCP storage is outside the selected project") from exc
    if not allow_initialize and (
        not store.is_dir() or not (store / "config.yaml").is_file()
    ):
        raise ValueError("MCP project must be initialized before ticket operations")


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Dispatch an MCP tool call and return the result dict."""

    _guard_tool_call(name, arguments)

    if name in ("planfile_dsl", "planfile_ask"):
        from planfile.dsl import DSLExecutor
        from planfile.dsl.parser import DSLParser
        project = Path(_require_project_path(arguments.get("project_path", ".")))
        raw_input = arguments.get("command") or arguments.get("query", "")
        command = DSLParser().parse(raw_input)
        if command.verb != "help":
            # The existing capability-gated configuration operation can
            # initialize this exact store; ticket operations cannot.
            _require_initialized_store(
                project,
                allow_initialize=command.verb == "update" and command.object_type == "config",
            )
        executor = DSLExecutor(project_path=str(project), discover_project=False)
        result = executor.run(raw_input) if name == "planfile_ask" else executor.execute(command)
        return result.to_dict()

    if name == "planfile_describe_grammar":
        from planfile.dsl import DSLCommand, DSLExecutor
        executor = DSLExecutor()
        result = executor.execute(DSLCommand(verb="help"))
        return {
            "grammar": result.message or "",
            "supported_languages": ["pl", "en"],
            "standard": "wellmanifest/nl-dsl-llm",
            "layers": {
                "layer_1": "Deterministic NL regex parser (<1ms, 0 tokens, PL + EN)",
                "layer_2": "Canonical DSL execution engine and validator",
                "layer_3": "LiteLLM adaptive fallback compiler"
            }
        }

    if name == "planfile_yaml_get":
        import yaml
        pf_path = _planfile_yaml_path(arguments)
        if not pf_path.exists():
            return {"error": "planfile.yaml not found"}
        with open(pf_path) as f:
            return yaml.safe_load(f) or {}

    if name == "planfile_yaml_patch":
        import yaml
        pf_path = _planfile_yaml_path(arguments)
        if not pf_path.exists():
            return {"error": "planfile.yaml not found"}
        with open(pf_path) as f:
            data = yaml.safe_load(f) or {}
        keys = arguments["path"].split(".")
        node = data
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = arguments["value"]
        with open(pf_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return {"patched": arguments["path"], "value": arguments["value"]}

    if name == "planfile_list_sprints":
        import yaml
        pf_path = _planfile_yaml_path(arguments)
        if not pf_path.exists():
            return []
        with open(pf_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("sprints", [])

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
            name=arguments["name"],
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
            try:
                result = handle_tool_call(tool_name, arguments)
            except (PermissionError, ValueError) as exc:
                # Expected guard/parser refusals are tool errors, not a reason
                # to terminate the transport or expose the command's contents.
                _write_jsonrpc({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": json.dumps({
                            "error": type(exc).__name__,
                            "message": "Request rejected: check project initialization, storage boundary and mutation capability.",
                        })}],
                    },
                })
                continue
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
