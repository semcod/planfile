"""DSL parser for planfile natural language commands.

Grammar (simplified EBNF):
  command     := verb object? target? modifiers*
  verb        := 'create'|'add'|'list'|'show'|'get'|'update'|'set'|'move'
                 |'delete'|'remove'|'done'|'start'|'block'|'validate'|'sync'
                 |'query'|'export'
  object      := 'ticket'|'tickets'|'sprint'|'sprints'|'backlog'|'strategy'
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
}

OBJECTS = {
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
        return bool(self.verb)

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

        verb_raw = tokens[0].lower()
        verb = VERBS.get(verb_raw)
        if not verb:
            return DSLCommand(verb="unknown", raw=text, params={"input": text})

        cmd = DSLCommand(verb=verb, raw=text)
        rest = tokens[1:]

        rest = self._extract_object(cmd, rest)
        rest = self._extract_target(cmd, rest)
        self._extract_modifiers(cmd, rest)

        return cmd

    def _extract_object(self, cmd: DSLCommand, tokens: list[str]) -> list[str]:
        if not tokens:
            return tokens
        obj = OBJECTS.get(tokens[0].lower())
        if obj:
            cmd.object_type = obj
            return tokens[1:]
        return tokens

    def _extract_target(self, cmd: DSLCommand, tokens: list[str]) -> list[str]:
        if not tokens:
            return tokens
        first = tokens[0]
        if TICKET_ID_RE.match(first.upper()):
            cmd.target = first.upper()
            return tokens[1:]
        if first.startswith('"') or (not KV_RE.match(first) and first.lower() not in ("to", "where", "and", "in")):
            if not KV_RE.match(first):
                cmd.target = first
                return tokens[1:]
        return tokens

    def _extract_modifiers(self, cmd: DSLCommand, tokens: list[str]) -> None:
        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.lower() == "to" and i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                m = KV_RE.match(next_tok)
                if m:
                    cmd.params[m.group(1)] = self._coerce(m.group(2))
                else:
                    cmd.params["to"] = next_tok
                i += 2
                continue

            if token.lower() == "where":
                i += 1
                while i < len(tokens) and tokens[i].lower() != "order":
                    m = KV_RE.match(tokens[i])
                    if m:
                        cmd.params[m.group(1)] = self._coerce(m.group(2))
                    i += 1
                continue

            m = KV_RE.match(token)
            if m:
                key = m.group(1)
                val_str = m.group(2)
                if "," in val_str and key in ("labels", "tags", "files"):
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
        if val.lower() in ("true", "yes"):
            return True
        if val.lower() in ("false", "no"):
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
