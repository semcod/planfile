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

import re
import shlex
from dataclasses import dataclass, field
from typing import Any

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
        """Parse a single DSL command string."""
        text = text.strip()
        if not text:
            return DSLCommand(verb="help", raw=text)

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
