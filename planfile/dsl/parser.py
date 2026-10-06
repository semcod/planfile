"""DSL parser for planfile natural language commands.

Grammar (simplified EBNF):
  command     := verb object? target? modifiers*
  verb        := 'create'|'add'|'list'|'show'|'get'|'update'|'set'|'move'
                 |'delete'|'remove'|'done'|'start'|'block'|'validate'|'sync'
                 |'query'|'export'|'pokaż'|'dodaj'|'zamknij'|'usuń'|'edytuj'
  object      := 'ticket'|'tickets'|'sprint'|'sprints'|'backlog'|'strategy'
                 |'config'|'configuration'|'settings'|'zadanie'|'zadania'
  target      := TICKET_ID | QUOTED_STRING | WORD
  modifiers   := KEY=VALUE | 'to' VALUE | 'where' FILTER_EXPR
  FILTER_EXPR := KEY=VALUE ('and' KEY=VALUE)*
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

try:
    from planfile_dsl import HAS_RUST_DSL
    from planfile_dsl import parse_dsl as _native_parse_dsl
except ImportError:
    HAS_RUST_DSL = False
    _native_parse_dsl = None

VERBS = {
    # English
    "create": "create",
    "add": "create",
    "new": "create",
    "list": "list",
    "ls": "list",
    "show": "show",
    "get": "show",
    "display": "show",
    "update": "update",
    "set": "update",
    "edit": "update",
    "patch": "update",
    "move": "move",
    "mv": "move",
    "delete": "delete",
    "remove": "delete",
    "del": "delete",
    "rm": "delete",
    "done": "done",
    "close": "done",
    "finish": "done",
    "complete": "done",
    "start": "start",
    "begin": "start",
    "block": "block",
    "validate": "validate",
    "check": "validate",
    "sync": "sync",
    "push": "sync",
    "query": "query",
    "find": "query",
    "search": "query",
    "export": "export",
    "help": "help",
    # Polish
    "pokaż": "list",
    "pokaz": "list",
    "wypisz": "list",
    "wyświetl": "list",
    "wyswietl": "list",
    "lista": "list",
    "listuj": "list",
    "szczegóły": "show",
    "szczegoly": "show",
    "dane": "show",
    "dodaj": "create",
    "utwórz": "create",
    "utworz": "create",
    "stwórz": "create",
    "stworz": "create",
    "nowy": "create",
    "nowa": "create",
    "nowe": "create",
    "załóż": "create",
    "zaloz": "create",
    "zmień": "update",
    "zmien": "update",
    "edytuj": "update",
    "zaktualizuj": "update",
    "ustaw": "update",
    "przenieś": "move",
    "przenies": "move",
    "zamknij": "done",
    "zakończ": "done",
    "zakoncz": "done",
    "zrobione": "done",
    "gotowe": "done",
    "rozpocznij": "start",
    "zacznij": "start",
    "zablokuj": "block",
    "odblokuj": "start",
    "usuń": "delete",
    "usun": "delete",
    "skasuj": "delete",
    "odrzuć": "delete",
    "odrzuc": "delete",
    "wyrzuć": "delete",
    "wyrzuc": "delete",
    "szukaj": "query",
    "znajdź": "query",
    "znajdz": "query",
    "synchronizuj": "sync",
    "wypchnij": "sync",
    "waliduj": "validate",
    "sprawdź": "validate",
    "sprawdz": "validate",
    "pomoc": "help",
}

OBJECTS = {
    # English
    "ticket": "ticket",
    "tickets": "ticket",
    "issue": "ticket",
    "issues": "ticket",
    "task": "ticket",
    "tasks": "ticket",
    "sprint": "sprint",
    "sprints": "sprint",
    "iteration": "sprint",
    "backlog": "backlog",
    "strategy": "strategy",
    "plan": "strategy",
    "planfile": "strategy",
    "config": "config",
    "configuration": "config",
    "settings": "config",
    # Polish
    "zadanie": "ticket",
    "zadania": "ticket",
    "zadań": "ticket",
    "zadan": "ticket",
    "tickety": "ticket",
    "ticketów": "ticket",
    "ticketow": "ticket",
    "zgłoszenie": "ticket",
    "zgłoszenia": "ticket",
    "zgłoszeń": "ticket",
    "zagadnienie": "ticket",
    "sprinty": "sprint",
    "sprintów": "sprint",
    "sprintow": "sprint",
    "iteracja": "sprint",
    "iteracji": "sprint",
    "strategia": "strategy",
    "strategie": "strategy",
    "strategii": "strategy",
    "konfiguracja": "config",
    "konfiguracji": "config",
    "ustawienia": "config",
    "ustawień": "config",
}

STATUS_ADJECTIVES = {
    "otwarte": "todo",
    "otwarty": "todo",
    "otwarta": "todo",
    "open": "todo",
    "nieukończone": "todo",
    "niescalone": "todo",
    "zamknięte": "done",
    "zamknięty": "done",
    "zamkniete": "done",
    "closed": "done",
    "done": "done",
    "zrobione": "done",
    "ukończone": "done",
    "w_toku": "in_progress",
    "rozpoczęte": "in_progress",
    "trwające": "in_progress",
    "active": "in_progress",
    "zablokowane": "blocked",
    "blocked": "blocked",
}

TICKET_ID_RE = re.compile(r"^[A-Z]+-\d+$|^#\d+$")
KV_RE = re.compile(r"^([\w.-]+)=(.*)$")


@dataclass
class DSLCommand:
    verb: str
    object_type: str | None = None
    target: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    raw: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(self.verb) and self.verb != "unknown"

    def to_dict(self) -> dict:
        return {
            "verb": self.verb,
            "object_type": self.object_type,
            "target": self.target,
            "params": self.params,
        }


class DSLParser:
    """Parse natural language / DSL commands into DSLCommand objects."""

    def parse(self, text: str) -> DSLCommand:
        text = text.strip()
        if not text:
            return DSLCommand(verb="help", raw=text)

        # Fast-path: planfile:// URI command or envelope
        if text.startswith(("planfile://", "uri: planfile://", "uri:planfile://", "uri: ")) or text == "planfile://":
            return self._parse_uri_command(text)
        if text.startswith("{") and ("wellmanifest.nl-plan/v1" in text or '"plan"' in text):
            return self._parse_nl_plan_command(text)

        if HAS_RUST_DSL and _native_parse_dsl is not None:
            try:
                native_cmd = _native_parse_dsl(text)
                return DSLCommand(
                    verb=native_cmd.verb,
                    object_type=native_cmd.object_type,
                    target=native_cmd.target,
                    params=dict(native_cmd.params),
                    raw=native_cmd.raw,
                )
            except Exception:
                pass

        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()

        if not tokens:
            return DSLCommand(verb="help", raw=text)

        # Support direct entity.operation format (e.g. ticket.list, ticket.create)
        if "." in tokens[0] and not tokens[0].startswith("."):
            parts = tokens[0].split(".", 1)
            ent_raw = parts[0].lower()
            op_raw = parts[1].lower()
            verb = VERBS.get(op_raw, op_raw)
            obj = OBJECTS.get(ent_raw, ent_raw)
            cmd = DSLCommand(verb=verb, object_type=obj, raw=text)
            rest = tokens[1:]
            rest = self._extract_target(cmd, rest)
            self._extract_modifiers(cmd, rest)
            return cmd

        verb_raw = tokens[0].lower()
        verb = VERBS.get(verb_raw)

        if not verb:
            # Check if first token is an object or adjective, implying 'list'
            if verb_raw in OBJECTS or verb_raw in STATUS_ADJECTIVES:
                verb = "list"
                rest = tokens
            else:
                return DSLCommand(verb="unknown", raw=text, params={"input": text})
        else:
            rest = tokens[1:]

        cmd = DSLCommand(verb=verb, raw=text)

        rest = self._extract_object_and_status(cmd, rest)
        rest = self._extract_target(cmd, rest)
        self._extract_modifiers(cmd, rest)

        # Default object to 'ticket' if target matches ticket pattern or id
        if not cmd.object_type and cmd.target and TICKET_ID_RE.match(cmd.target.upper()):
            cmd.object_type = "ticket"

        # Default create title parameter
        if cmd.verb == "create" and cmd.target and "title" not in cmd.params:
            cmd.params["title"] = cmd.target

        return cmd

    def _extract_object_and_status(self, cmd: DSLCommand, tokens: list[str]) -> list[str]:
        """Extract object type and any status adjective (PL & EN) from tokens."""
        remaining: list[str] = []
        for tok in tokens:
            lower = tok.lower()
            if not cmd.object_type and lower in OBJECTS:
                cmd.object_type = OBJECTS[lower]
                continue
            if "status" not in cmd.params and lower in STATUS_ADJECTIVES:
                cmd.params["status"] = STATUS_ADJECTIVES[lower]
                continue
            remaining.append(tok)
        return remaining

    def _extract_target(self, cmd: DSLCommand, tokens: list[str]) -> list[str]:
        if not tokens:
            return tokens
        first = tokens[0]
        if TICKET_ID_RE.match(first.upper()):
            cmd.target = first.upper()
            return tokens[1:]
        if first.startswith('"') or (not KV_RE.match(first) and first.lower() not in ("to", "where", "and", "in", "do")):
            if not KV_RE.match(first):
                cmd.target = first
                return tokens[1:]
        return tokens

    def _extract_modifiers(self, cmd: DSLCommand, tokens: list[str]) -> None:
        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.lower() in ("to", "do") and i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                m = KV_RE.match(next_tok)
                if m:
                    cmd.params[m.group(1)] = self._coerce(m.group(2))
                else:
                    cmd.params["to"] = next_tok
                i += 2
                continue

            if token.lower() in ("where", "gdzie"):
                i += 1
                while i < len(tokens) and tokens[i].lower() not in ("order", "sortuj"):
                    m = KV_RE.match(tokens[i])
                    if m:
                        cmd.params[m.group(1)] = self._coerce(m.group(2))
                    i += 1
                continue

            m = KV_RE.match(token)
            if m:
                key = m.group(1)
                val_str = m.group(2)
                if "," in val_str and key in ("labels", "tags", "files", "tagi"):
                    cmd.params[key] = [v.strip() for v in val_str.split(",")]
                else:
                    cmd.params[key] = self._coerce(val_str)
                i += 1
                continue

            if not cmd.target and not TICKET_ID_RE.match(token.upper()):
                cmd.target = token
            i += 1

    @staticmethod
    def _coerce(val: str) -> Any:
        if val.lower() in ("true", "yes", "tak"):
            return True
        if val.lower() in ("false", "no", "nie"):
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val

    def _parse_uri_command(self, text: str) -> DSLCommand:
        """Parse a planfile:// URI command with exact validation and ambiguity abstention."""
        raw_text = text
        stripped = text.strip()
        if stripped.lower().startswith("uri:"):
            stripped = stripped[4:].strip()

        if not stripped.startswith("planfile://"):
            return DSLCommand(
                verb="unknown",
                raw=raw_text,
                params={"error": f"Invalid URI scheme, expected 'planfile://': {stripped}", "uri": stripped},
            )

        uri_and_args = stripped[len("planfile://"):].strip()
        if not uri_and_args:
            return DSLCommand(
                verb="unknown",
                raw=raw_text,
                params={"error": "Empty planfile URI path", "uri": stripped},
            )

        parts = uri_and_args.split(maxsplit=1)
        path = parts[0]
        args_str = parts[1] if len(parts) > 1 else ""

        if "?" in path or "#" in path:
            return DSLCommand(
                verb="unknown",
                raw=raw_text,
                params={"error": f"Query strings and fragments are excluded from operation URIs: {path}", "uri": stripped},
            )

        path = path.strip("/")
        path_segments = [p for p in path.split("/") if p]
        if not path_segments:
            return DSLCommand(
                verb="unknown",
                raw=raw_text,
                params={"error": "Empty planfile URI path", "uri": stripped},
            )

        cmd: DSLCommand | None = None

        # 1. tickets/command/create
        if path_segments == ["tickets", "command", "create"]:
            cmd = DSLCommand(verb="create", object_type="ticket", raw=raw_text)

        # 2. tickets/{id}/command/{action}
        elif len(path_segments) == 4 and path_segments[0] == "tickets" and path_segments[2] == "command":
            t_id = path_segments[1]
            action = path_segments[3].lower()
            verb = VERBS.get(action)
            if not verb:
                return DSLCommand(
                    verb="unknown",
                    raw=raw_text,
                    params={"error": f"Unrecognized ticket action '{action}' in URI", "uri": stripped},
                )
            cmd = DSLCommand(verb=verb, object_type="ticket", target=t_id, raw=raw_text)

        # 3. tickets/{id}
        elif len(path_segments) == 2 and path_segments[0] == "tickets":
            t_id = path_segments[1]
            cmd = DSLCommand(verb="show", object_type="ticket", target=t_id, raw=raw_text)

        # 4. tickets
        elif path_segments == ["tickets"]:
            cmd = DSLCommand(verb="list", object_type="ticket", raw=raw_text)

        # 5. sprints/{sprint}/tickets
        elif len(path_segments) == 3 and path_segments[0] == "sprints" and path_segments[2] == "tickets":
            sprint_id = path_segments[1]
            cmd = DSLCommand(verb="list", object_type="ticket", params={"sprint": sprint_id}, raw=raw_text)

        # 6. sprints/command/create
        elif path_segments == ["sprints", "command", "create"]:
            cmd = DSLCommand(verb="create", object_type="sprint", raw=raw_text)

        # 7. sprints/{sprint}
        elif len(path_segments) == 2 and path_segments[0] == "sprints":
            sprint_id = path_segments[1]
            cmd = DSLCommand(verb="show", object_type="sprint", target=sprint_id, raw=raw_text)

        # 8. sprints
        elif path_segments == ["sprints"]:
            cmd = DSLCommand(verb="list", object_type="sprint", raw=raw_text)

        # 9. sync
        elif path_segments == ["sync"]:
            cmd = DSLCommand(verb="sync", object_type="ticket", raw=raw_text)

        # 10. config/command/set
        elif path_segments == ["config", "command", "set"]:
            cmd = DSLCommand(verb="update", object_type="config", raw=raw_text)

        # 11. config/{path}
        elif len(path_segments) >= 2 and path_segments[0] == "config":
            cfg_path = "/".join(path_segments[1:])
            cmd = DSLCommand(verb="show", object_type="config", target=cfg_path, raw=raw_text)

        # 12. config
        elif path_segments == ["config"]:
            cmd = DSLCommand(verb="show", object_type="config", raw=raw_text)

        # 13. validate
        elif path_segments == ["validate"]:
            cmd = DSLCommand(verb="validate", object_type="strategy", raw=raw_text)

        else:
            return DSLCommand(
                verb="unknown",
                raw=raw_text,
                params={"error": f"Invalid or unrecognized planfile URI path: '{path}'", "uri": stripped},
            )

        if args_str:
            args_str = args_str.strip()
            if args_str.startswith(("{", "[")):
                try:
                    parsed_json = json.loads(args_str)
                    if isinstance(parsed_json, dict):
                        cmd.params.update(parsed_json)
                    else:
                        return DSLCommand(
                            verb="unknown",
                            raw=raw_text,
                            params={"error": f"JSON arguments must be an object, got {type(parsed_json).__name__}"},
                        )
                except Exception as exc:
                    return DSLCommand(
                        verb="unknown",
                        raw=raw_text,
                        params={"error": f"Malformed JSON arguments: {exc}"},
                    )
            else:
                try:
                    tokens = shlex.split(args_str)
                except ValueError:
                    tokens = args_str.split()
                self._extract_modifiers(cmd, tokens)

        if cmd.verb == "create" and cmd.object_type == "ticket":
            if "name" not in cmd.params and "title" in cmd.params:
                cmd.params["name"] = cmd.params["title"]
            if "title" not in cmd.params and "name" in cmd.params:
                cmd.params["title"] = cmd.params["name"]
            if not cmd.target and cmd.params.get("name"):
                cmd.target = cmd.params["name"]
            elif cmd.target and "name" not in cmd.params:
                cmd.params["name"] = cmd.target
                cmd.params["title"] = cmd.target

        if cmd.verb == "sync":
            if "integration" in cmd.params and not cmd.target:
                cmd.target = cmd.params["integration"]
            elif cmd.target and "integration" not in cmd.params:
                cmd.params["integration"] = cmd.target

        return cmd

    def _parse_nl_plan_command(self, text: str) -> DSLCommand:
        """Parse a wellmanifest.nl-plan/v1 envelope."""
        try:
            envelope = json.loads(text.strip())
        except Exception as exc:
            return DSLCommand(
                verb="unknown",
                raw=text,
                params={"error": f"Malformed JSON envelope: {exc}"},
            )

        if not isinstance(envelope, dict):
            return DSLCommand(
                verb="unknown",
                raw=text,
                params={"error": "Plan envelope must be a JSON object"},
            )

        status = envelope.get("status")
        if status == "clarify":
            return DSLCommand(
                verb="clarify",
                raw=text,
                params={"question": envelope.get("question", "")},
            )
        elif status == "unsupported":
            return DSLCommand(
                verb="unsupported",
                raw=text,
                params={"reason": envelope.get("reason", "")},
            )
        elif status == "ok":
            plan = envelope.get("plan")
            if not isinstance(plan, dict):
                return DSLCommand(
                    verb="unknown",
                    raw=text,
                    params={"error": "Missing or invalid 'plan' object in ok envelope"},
                )
            kind = plan.get("kind")
            if kind == "call":
                op = plan.get("operation")
                args = plan.get("arguments", {})
                if not op or not isinstance(op, str):
                    return DSLCommand(
                        verb="unknown",
                        raw=text,
                        params={"error": "Call plan missing 'operation' URI string"},
                    )
                args_json = json.dumps(args)
                return self._parse_uri_command(f"{op} {args_json}")
            elif kind == "sequence":
                calls = plan.get("calls", [])
                if not isinstance(calls, list):
                    return DSLCommand(
                        verb="unknown",
                        raw=text,
                        params={"error": "'calls' in sequence must be a list"},
                    )
                return DSLCommand(
                    verb="sequence",
                    raw=text,
                    params={"calls": calls, "digest": plan.get("digest")},
                )
            else:
                return DSLCommand(
                    verb="unknown",
                    raw=text,
                    params={"error": f"Unknown plan kind '{kind}', expected 'call' or 'sequence'"},
                )
        else:
            return DSLCommand(
                verb="unknown",
                raw=text,
                params={"error": f"Unknown envelope status '{status}', expected ok/clarify/unsupported"},
            )
