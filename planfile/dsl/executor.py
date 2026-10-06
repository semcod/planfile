"""DSL executor — maps DSLCommand to planfile operations."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from planfile.dsl.parser import DSLCommand, DSLParser

logger = logging.getLogger(__name__)


@dataclass
class DSLResult:
    ok: bool
    command: dict = field(default_factory=dict)
    data: Any = None
    error: str | None = None
    message: str | None = None
    source_layer: str = "direct_dsl"

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "command": self.command,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "source_layer": self.source_layer,
        }


class DSLExecutor:
    """Execute DSL commands against a Planfile instance."""

    def __init__(self, project_path: str = ".", *, discover_project: bool = True):
        self._project_path = project_path
        self._discover_project = discover_project
        self._pf = None
        self._parser = DSLParser()

    @property
    def pf(self):
        if self._pf is None:
            from planfile import Planfile
            self._pf = (
                Planfile.auto_discover(self._project_path)
                if self._discover_project else Planfile(self._project_path)
            )
        return self._pf

    def run(self, text: str, *, allow_llm_fallback: bool = True, dry_run: bool = False) -> DSLResult:
        """Parse and execute a DSL command string with optional LLM translation fallback."""
        stripped = text.strip()
        if stripped.startswith("{") and ("wellmanifest.nl-plan/v1" in stripped or '"plan"' in stripped):
            return self.execute_plan(stripped, dry_run=dry_run)

        conv_res = self._handle_conversational_query(text)
        if conv_res is not None:
            return conv_res

        cmd = self._parser.parse(text)
        if dry_run:
            cmd.params["dry_run"] = True

        if (not cmd.is_valid or cmd.verb == "unknown") and allow_llm_fallback:
            if not (cmd.raw.startswith(("planfile://", "uri:")) or cmd.params.get("error")):
                translated = self._translate_with_llm(text)
                if translated:
                    fallback_cmd = self._parser.parse(translated)
                    if fallback_cmd.is_valid:
                        if dry_run:
                            fallback_cmd.params["dry_run"] = True
                        res = self.execute(fallback_cmd)
                        res.source_layer = "llm_fallback"
                        res.command["source_layer"] = "llm_fallback"
                        res.command["original_input"] = text
                        return res

        res = self.execute(cmd)
        if cmd.verb in ("clarify", "unsupported", "sequence"):
            res.source_layer = "nl_plan_v1"
        elif cmd.raw.startswith(("planfile://", "uri:")):
            res.source_layer = "uri_dsl"
        else:
            res.source_layer = "nl_fast_path" if any(w in text.lower() for w in ("pokaż", "zadanie", "zadania", "otwarte", "zamknij", "dodaj", "tickety")) else "direct_dsl"
        res.command["source_layer"] = res.source_layer
        return res

    def execute_plan(self, envelope: dict | str, *, dry_run: bool = False) -> DSLResult:
        """Execute a wellmanifest.nl-plan/v1 envelope."""
        import json
        if isinstance(envelope, str):
            try:
                envelope = json.loads(envelope)
            except Exception as exc:
                return DSLResult(ok=False, error=f"Invalid JSON envelope: {exc}", source_layer="nl_plan_v1")
        if not isinstance(envelope, dict):
            return DSLResult(ok=False, error="Envelope must be a JSON object", source_layer="nl_plan_v1")
        schema = envelope.get("schema")
        if schema not in ("wellmanifest.nl-plan/v1", "nl-plan/v1"):
            return DSLResult(
                ok=False,
                error=f"Unsupported schema '{schema}'. Expected 'wellmanifest.nl-plan/v1'.",
                source_layer="nl_plan_v1",
            )
        raw_json = json.dumps(envelope)
        cmd = self._parser.parse(raw_json)
        if dry_run:
            cmd.params["dry_run"] = True
        res = self.execute(cmd)
        res.source_layer = "nl_plan_v1"
        res.command["source_layer"] = "nl_plan_v1"
        return res

    def _handle_conversational_query(self, text: str) -> DSLResult | None:
        """Handle natural conversation questions about plans, tickets, blockers, and next actions."""
        import re
        import unicodedata

        clean = text.strip().lower().rstrip("?!.,")
        if clean.startswith((
            "planfile://", "uri:", "create ticket", "update ticket", "list tickets", "show ticket",
            "done ticket", "delete ticket", "export ", "query tickets", "move ticket",
            "set ticket", "start ticket", "block ticket", "set config", "show config",
        )):
            return None

        normalized = "".join(
            c for c in unicodedata.normalize("NFD", clean)
            if unicodedata.category(c) != "Mn"
        )
        raw_text = text.strip().rstrip("?!.,")

        # ── Safe Conversational Mutation Proposals (Human-In-The-Loop) ──
        # A. Create ticket proposal
        m_create = re.search(
            r"^(?:dodaj|stworz|utworz|nowe)\s+(?:zadanie|ticket|task)\s+(.+)$",
            normalized,
            re.IGNORECASE,
        )
        if m_create:
            m_create_orig = re.search(
                r"^(?:dodaj|stworz|utworz|stwórz|utwórz|nowe)\s+(?:zadanie|ticket|task)\s+(.+)$",
                raw_text,
                re.IGNORECASE,
            )
            raw_title_part = m_create_orig.group(1).strip() if m_create_orig else m_create.group(1).strip()
            norm_title_part = m_create.group(1).strip()

            prio = "normal"
            m_prio = re.search(
                r"(?:z\s+priorytetem|priorytet|priority)\s*[:=]?\s*(krytyczn\w*|wysok\w*|normaln\w*|nisk\w*|critical|high|normal|low)",
                norm_title_part,
                re.IGNORECASE,
            )
            if m_prio:
                p_word = m_prio.group(1).lower()
                if "krytycz" in p_word or "critical" in p_word:
                    prio = "critical"
                elif "wysok" in p_word or "high" in p_word:
                    prio = "high"
                elif "nisk" in p_word or "low" in p_word:
                    prio = "low"
                else:
                    prio = "normal"
                raw_title_part = raw_title_part[:m_prio.start()].strip().rstrip("-,;:")

            title = raw_title_part.strip().strip('"\'')
            if title:
                return DSLResult(
                    ok=True,
                    command={
                        "verb": "action_proposal",
                        "action": {
                            "type": "create_ticket",
                            "name": title,
                            "priority": prio,
                            "sprint": "current",
                        },
                        "conversational_intent": "create_ticket",
                    },
                    data={
                        "proposal": True,
                        "action": {
                            "type": "create_ticket",
                            "name": title,
                            "priority": prio,
                            "sprint": "current",
                        },
                    },
                    message=f"Czy chcesz utworzyć zadanie '{title}' z priorytetem '{prio}'?",
                    source_layer="conversational_fast_path",
                )

        # B. Close / Done proposal
        m_done = re.search(
            r"^(?:oznacz|zamknij|ukoncz)\s+(?:zadanie\s+|ticket\s+)?([A-Za-z0-9_-]+)(?:\s+jako\s+(?:zrobione|done|ukonczone|wykonane))?$",
            normalized,
            re.IGNORECASE,
        )
        if m_done:
            t_id = m_done.group(1).upper()
            return DSLResult(
                ok=True,
                command={
                    "verb": "action_proposal",
                    "action": {
                        "type": "update_status",
                        "ticket_id": t_id,
                        "status": "done",
                    },
                    "conversational_intent": "close_ticket",
                },
                data={
                    "proposal": True,
                    "action": {
                        "type": "update_status",
                        "ticket_id": t_id,
                        "status": "done",
                    },
                },
                message=f"Czy chcesz oznaczyć zadanie {t_id} jako wykonane (done)?",
                source_layer="conversational_fast_path",
            )

        # C. Change priority proposal
        m_prio_change = re.search(
            r"^(?:zmien|ustaw|zwieksz|zmniejsz|change|set)\s+priorytet\s+(?:zadania\s+|ticketu\s+)?([A-Za-z0-9_-]+)\s+na\s+(krytyczn\w*|wysok\w*|normaln\w*|nisk\w*|critical|high|normal|low)$",
            normalized,
            re.IGNORECASE,
        )
        if not m_prio_change:
            m_prio_change = re.search(
                r"^(?:set|change)\s+priority\s+(?:of\s+)?([A-Za-z0-9_-]+)\s+to\s+(critical|high|normal|low)$",
                normalized,
                re.IGNORECASE,
            )
        if m_prio_change:
            t_id = m_prio_change.group(1).upper()
            p_word = m_prio_change.group(2).lower()
            if "krytycz" in p_word or "critical" in p_word:
                prio = "critical"
            elif "wysok" in p_word or "high" in p_word:
                prio = "high"
            elif "nisk" in p_word or "low" in p_word:
                prio = "low"
            else:
                prio = "normal"
            return DSLResult(
                ok=True,
                command={
                    "verb": "action_proposal",
                    "action": {
                        "type": "change_priority",
                        "ticket_id": t_id,
                        "priority": prio,
                    },
                    "conversational_intent": "change_priority",
                },
                data={
                    "proposal": True,
                    "action": {
                        "type": "change_priority",
                        "ticket_id": t_id,
                        "priority": prio,
                    },
                },
                message=f"Czy chcesz zmienić priorytet zadania {t_id} na '{prio}'?",
                source_layer="conversational_fast_path",
            )

        # D. Block ticket proposal
        m_block = re.search(
            r"^(?:zablokuj)\s+(?:zadanie\s+|ticket\s+)?([A-Za-z0-9_-]+)(?:\s+(?:z powodu|powod:?)\s+(.+))?$",
            raw_text,
            re.IGNORECASE,
        )
        if m_block:
            t_id = m_block.group(1).upper()
            reason = m_block.group(2).strip() if m_block.group(2) else None
            return DSLResult(
                ok=True,
                command={
                    "verb": "action_proposal",
                    "action": {
                        "type": "block_ticket",
                        "ticket_id": t_id,
                        "reason": reason or "Zablokowane przez asystenta głosowego",
                    },
                    "conversational_intent": "block_ticket",
                },
                data={
                    "proposal": True,
                    "action": {
                        "type": "block_ticket",
                        "ticket_id": t_id,
                        "reason": reason,
                    },
                },
                message=f"Czy chcesz zablokować zadanie {t_id}" + (f" z powodu: '{reason}'?" if reason else "?"),
                source_layer="conversational_fast_path",
            )

        # ── Conversational Read / Status Queries ──
        # 1. Blocked / waiting queries
        if any(p in normalized for p in ("co jest zablokowane", "zablokowane", "blokuj", "blocked", "czeka na", "co blokuje")):
            try:
                tickets = self.pf.list_tickets(sprint="current")
                all_tickets = self.pf.list_tickets(sprint="all")
            except Exception as exc:
                logger.debug("Failed to list tickets for blocked queries: %s", exc)
                tickets, all_tickets = [], []
            seen = set()
            combined = []
            for t in tickets + all_tickets:
                if t.id not in seen:
                    seen.add(t.id)
                    combined.append(t)
            blocked = [
                t for t in combined
                if getattr(t, "status", "") == "blocked"
                or (getattr(t, "execution", None) and getattr(t.execution, "state", None) in ("failed", "waiting_input", "blocked"))
            ]
            if not blocked:
                msg = "Wszystkie zadania postępują prawidłowo. Brak zablokowanych zadań w bieżącym sprincie."
            else:
                items = [f"{t.id}: {t.name}" for t in blocked]
                msg = f"Znaleziono {len(blocked)} zablokowane zadanie(a): " + "; ".join(items)
            return DSLResult(
                ok=True,
                command={"verb": "list", "object_type": "ticket", "params": {"status": "blocked"}, "conversational_intent": "blocked_tickets"},
                data=[t.model_dump(mode="json", exclude_none=True) for t in blocked],
                message=msg,
                source_layer="conversational_fast_path",
            )

        # 2. Next task queries
        if any(p in normalized for p in ("nastepne", "co robic", "co dalej", "next task", "next ticket", "co teraz", "kolejne zadanie")):
            try:
                tickets = self.pf.list_tickets(sprint="current")
            except Exception as exc:
                logger.debug("Failed to list tickets for next task queries: %s", exc)
                tickets = []
            open_tickets = [t for t in tickets if getattr(t, "status", "") in ("todo", "open", "ready", "pending")]
            prio_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
            open_tickets.sort(key=lambda t: prio_order.get(getattr(t, "priority", "normal"), 2))
            if open_tickets:
                nxt = open_tickets[0]
                q_name = getattr(nxt.execution, "queue", "default") if getattr(nxt, "execution", None) else "default"
                msg = f"Następne rekomendowane zadanie to {nxt.id}: '{nxt.name}' (priorytet: {nxt.priority}, kolejka: {q_name})."
                return DSLResult(
                    ok=True,
                    command={"verb": "show", "object_type": "ticket", "target": nxt.id, "conversational_intent": "next_ticket"},
                    data=nxt.model_dump(mode="json", exclude_none=True),
                    message=msg,
                    source_layer="conversational_fast_path",
                )
            else:
                return DSLResult(
                    ok=True,
                    command={"verb": "show", "conversational_intent": "next_ticket"},
                    data=None,
                    message="Brak oczekujących zadań do podjęcia w bieżącym sprincie.",
                    source_layer="conversational_fast_path",
                )

        # 3. Sprint / Plan summary
        if any(p in normalized for p in ("stan sprintu", "status planu", "podsumuj sprint", "podsumowanie", "jak idzie", "sprint summary", "plan status")):
            try:
                tickets = self.pf.list_tickets(sprint="current")
                all_tickets = self.pf.list_tickets(sprint="all")
            except Exception as exc:
                logger.debug("Failed to list tickets for sprint summary queries: %s", exc)
                tickets, all_tickets = [], []
            seen = set()
            combined = []
            for t in tickets + all_tickets:
                if t.id not in seen:
                    seen.add(t.id)
                    combined.append(t)
            total = len(combined)
            done = sum(1 for t in combined if getattr(t, "status", "") == "done")
            running = sum(1 for t in combined if getattr(t, "execution", None) and getattr(t.execution, "state", None) == "running")
            blocked = sum(1 for t in combined if getattr(t, "status", "") == "blocked" or (getattr(t, "execution", None) and getattr(t.execution, "state", None) in ("failed", "waiting_input", "blocked")))
            open_cnt = max(0, total - done - running - blocked)
            pct = round((done / total * 100), 1) if total > 0 else 0.0
            msg = f"Stan sprintu: {total} zadań (Ukończone: {done} [{pct}%], W toku: {running}, Otwarte: {open_cnt}, Zablokowane: {blocked})."
            return DSLResult(
                ok=True,
                command={"verb": "summary", "object_type": "sprint", "conversational_intent": "sprint_summary"},
                data={
                    "total": total,
                    "done": done,
                    "running": running,
                    "open": open_cnt,
                    "blocked": blocked,
                    "completion_rate_pct": pct,
                },
                message=msg,
                source_layer="conversational_fast_path",
            )

        # 4. High priority queries
        if any(p in normalized for p in ("wysoki priorytet", "krytyczne", "pilne", "high priority", "critical")):
            try:
                tickets = self.pf.list_tickets(sprint="current")
            except Exception as exc:
                logger.debug("Failed to list tickets for high priority queries: %s", exc)
                tickets = []
            high_prio = [t for t in tickets if getattr(t, "priority", "") in ("critical", "high") and getattr(t, "status", "") != "done"]
            if not high_prio:
                msg = "Brak aktywnych zadań o wysokim lub krytycznym priorytecie."
            else:
                items = [f"{t.id}: {t.name} ({t.priority})" for t in high_prio]
                msg = f"Aktywne zadania o wysokim priorytecie ({len(high_prio)}): " + "; ".join(items)
            return DSLResult(
                ok=True,
                command={"verb": "list", "object_type": "ticket", "params": {"priority": "high"}, "conversational_intent": "high_priority"},
                data=[t.model_dump(mode="json", exclude_none=True) for t in high_prio],
                message=msg,
                source_layer="conversational_fast_path",
            )

        return None

    def _translate_with_llm(self, text: str) -> str | None:
        """Translate natural language text to canonical planfile DSL via LiteLLM if available."""
        if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")):
            return None
        prompt = (
            "Translate the following natural language user request into a single valid planfile DSL command.\n"
            "Supported DSL syntax examples:\n"
            "  create ticket \"NAME\" [priority=P] [sprint=S] [labels=a,b]\n"
            "  list tickets [sprint=S] [status=ST]\n"
            "  show ticket ID\n"
            "  update ticket ID [status=ST] [priority=P] [title=T]\n"
            "  done ticket ID\n"
            "  delete ticket ID\n"
            "  list sprints\n"
            "  show config\n"
            "Respond with ONLY the exact DSL command string, no explanations, no markdown backticks.\n\n"
            f"User request: {text.strip()}\n"
            "DSL:"
        )
        model = os.getenv("PLANFILE_LLM_MODEL", os.getenv("LLM_MODEL_VALIDATOR", "openrouter/anthropic/claude-3.5-haiku"))
        try:
            from planfile.llm.client import call_llm
            resp = call_llm(prompt, model=model, temperature=0.0)
            cleaned = resp.strip().strip("`").strip()
            if cleaned.startswith("dsl "):
                cleaned = cleaned[4:].strip()
            return cleaned
        except Exception as exc:
            logger.debug("Planfile LLM translation fallback failed for %r: %s", text, exc)
            return None

    def execute(self, cmd: DSLCommand) -> DSLResult:
        """Execute an already-parsed DSLCommand."""
        handler = getattr(self, f"_exec_{cmd.verb}", None)
        if handler is None:
            return DSLResult(
                ok=False,
                command=cmd.to_dict(),
                error=f"Unknown command verb: '{cmd.verb}'. Try 'help'.",
            )
        try:
            return handler(cmd)
        except Exception as exc:
            return DSLResult(ok=False, command=cmd.to_dict(), error=str(exc))

    # ── Verb handlers ──────────────────────────────────────────────────────────

    def _exec_help(self, cmd: DSLCommand) -> DSLResult:
        help_text = (
            "planfile DSL commands:\n"
            "  create ticket \"NAME\" [priority=P] [sprint=S] [labels=a,b]\n"
            "  list tickets [sprint=S] [status=ST]\n"
            "  list sprints\n"
            "  list config\n"
            "  show config [PATH]\n"
            "  set config PATH=VALUE [PATH=VALUE] [mode=dry-run] [if_revision=cfg_...]\n"
            "  show ticket ID\n"
            "  update ticket ID status=done\n"
            "  set ticket ID priority=high labels=backend,auth\n"
            "  move ticket ID to sprint=2\n"
            "  done ticket ID\n"
            "  start ticket ID\n"
            "  block ticket ID [reason=\"...\"]  \n"
            "  delete ticket ID [--force]\n"
            "  validate\n"
            "  sync [github|gitlab|jira|markdown|all]\n"
            "  query tickets where priority=high\n"
        )
        return DSLResult(ok=True, command=cmd.to_dict(), message=help_text)

    def _exec_unknown(self, cmd: DSLCommand) -> DSLResult:
        err = cmd.params.get("error") or f"Unrecognized command: '{cmd.raw}'. Type 'help' for usage."
        return DSLResult(
            ok=False,
            command=cmd.to_dict(),
            error=err,
        )

    def _exec_clarify(self, cmd: DSLCommand) -> DSLResult:
        q = cmd.params.get("question", "Clarification required")
        return DSLResult(
            ok=False,
            command=cmd.to_dict(),
            data={"status": "clarify", "question": q},
            message=q,
            source_layer="nl_plan_v1",
        )

    def _exec_unsupported(self, cmd: DSLCommand) -> DSLResult:
        reason = cmd.params.get("reason", "Unsupported request")
        return DSLResult(
            ok=False,
            command=cmd.to_dict(),
            data={"status": "unsupported", "reason": reason},
            error=reason,
            source_layer="nl_plan_v1",
        )

    def _exec_sequence(self, cmd: DSLCommand) -> DSLResult:
        import json
        calls = cmd.params.get("calls", [])
        if not (1 <= len(calls) <= 16):
            return DSLResult(
                ok=False,
                command=cmd.to_dict(),
                error=f"Sequence must contain 1-16 calls, got {len(calls)}",
                source_layer="nl_plan_v1",
            )
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        step_results = []
        for idx, call in enumerate(calls):
            if not isinstance(call, dict) or call.get("kind") != "call":
                return DSLResult(
                    ok=False,
                    command=cmd.to_dict(),
                    error=f"Invalid call specification at step {idx}: {call}",
                    data={"completed_steps": idx, "step_results": step_results},
                    source_layer="nl_plan_v1",
                )
            op = call.get("operation")
            args = call.get("arguments", {})
            if not op or not isinstance(op, str):
                return DSLResult(
                    ok=False,
                    command=cmd.to_dict(),
                    error=f"Missing operation URI in step {idx}",
                    data={"completed_steps": idx, "step_results": step_results},
                    source_layer="nl_plan_v1",
                )
            step_cmd_text = f"uri: {op} {json.dumps(args)}"
            step_cmd = self._parser.parse(step_cmd_text)
            if dry_run:
                step_cmd.params["dry_run"] = True
            step_res = self.execute(step_cmd)
            step_results.append(step_res.to_dict())
            if not step_res.ok:
                return DSLResult(
                    ok=False,
                    command=cmd.to_dict(),
                    error=f"Step {idx} ({op}) failed: {step_res.error}",
                    data={"completed_steps": idx, "step_results": step_results},
                    source_layer="nl_plan_v1",
                )
        return DSLResult(
            ok=True,
            command=cmd.to_dict(),
            data={"steps_count": len(calls), "step_results": step_results, "dry_run": dry_run},
            message=f"Executed sequence of {len(calls)} call(s)",
            source_layer="nl_plan_v1",
        )

    def _exec_create(self, cmd: DSLCommand) -> DSLResult:
        obj = cmd.object_type or "ticket"
        if obj == "ticket":
            params = dict(cmd.params)
            params.pop("title", None)
            params_name = params.pop("name", None)
            name = cmd.target or params_name
            if not name:
                return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket name required.")
            dry_run = bool(params.pop("dry_run", False)) or params.get("mode") == "dry-run"
            priority = params.pop("priority", "normal")
            sprint = params.pop("sprint", "current")
            labels = params.pop("labels", [])
            description = params.pop("description", "")
            if dry_run:
                with self.pf.store.mutation_lock():
                    preview_id = self.pf.store._next_id_unlocked()
                return DSLResult(
                    ok=True,
                    command=cmd.to_dict(),
                    data={
                        "dry_run": True,
                        "ticket": {
                            "id": preview_id,
                            "name": name,
                            "priority": priority,
                            "sprint": sprint,
                            "status": "todo",
                            "labels": labels,
                            "description": description,
                        },
                    },
                    message=f"[dry-run] Would create ticket {preview_id}: {name}",
                )
            from planfile import TicketSource
            ticket = self.pf.create_ticket(
                name=name,
                priority=priority,
                sprint=sprint,
                description=description,
                labels=labels,
                source=TicketSource(tool="dsl"),
                **params,
            )
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data=ticket.model_dump(mode="json", exclude_none=True),
                message=f"Created {ticket.id}: {ticket.name}",
            )
        if obj == "sprint":
            return self._exec_create_sprint(cmd)
        return DSLResult(ok=False, command=cmd.to_dict(), error=f"Cannot create '{obj}' via DSL.")

    def _exec_create_sprint(self, cmd: DSLCommand) -> DSLResult:
        from pathlib import Path

        import yaml
        name = cmd.target or cmd.params.get("name", "Sprint")
        days = int(cmd.params.get("days", 14))
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if dry_run:
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "name": name, "length_days": days},
                message=f"[dry-run] Would create sprint: {name}",
            )
        pf_path = Path(self.pf.store.project_dir) / "planfile.yaml"
        if not pf_path.exists():
            return DSLResult(ok=False, command=cmd.to_dict(), error="planfile.yaml not found.")
        with open(pf_path) as f:
            data = yaml.safe_load(f) or {}
        sprints = data.get("sprints", [])
        new_id = max((s.get("id", 0) for s in sprints), default=0) + 1
        sprints.append({"id": new_id, "name": name, "length_days": days})
        data["sprints"] = sprints
        with open(pf_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data={"id": new_id, "name": name, "length_days": days},
            message=f"Created sprint {new_id}: {name}",
        )

    def _exec_list(self, cmd: DSLCommand) -> DSLResult:
        obj = cmd.object_type or "ticket"
        if obj == "config":
            data = self._configuration().list()
            return DSLResult(
                ok=True,
                command=cmd.to_dict(),
                data=data,
                message=f"Found {len(data['writable'])} writable configuration path(s)",
            )
        if obj == "ticket":
            sprint = cmd.params.get("sprint", "current")
            filters = {k: v for k, v in cmd.params.items() if k != "sprint"}
            tickets = self.pf.list_tickets(sprint=sprint, **filters)
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data=[t.model_dump(mode="json", exclude_none=True) for t in tickets],
                message=f"Found {len(tickets)} ticket(s)",
            )
        if obj == "sprint":
            return self._exec_list_sprints(cmd)
        return DSLResult(ok=False, command=cmd.to_dict(), error=f"Cannot list '{obj}'.")

    def _exec_list_sprints(self, cmd: DSLCommand) -> DSLResult:
        from pathlib import Path

        import yaml
        pf_path = Path(self.pf.store.project_dir) / "planfile.yaml"
        if not pf_path.exists():
            return DSLResult(ok=False, command=cmd.to_dict(), error="planfile.yaml not found.")
        with open(pf_path) as f:
            data = yaml.safe_load(f) or {}
        sprints = data.get("sprints", [])
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=sprints,
            message=f"Found {len(sprints)} sprint(s)",
        )

    def _exec_show(self, cmd: DSLCommand) -> DSLResult:
        if cmd.object_type == "config":
            return DSLResult(
                ok=True,
                command=cmd.to_dict(),
                data=self._configuration().show(cmd.target),
            )
        ticket_id = cmd.target
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        ticket = self.pf.get_ticket(ticket_id)
        if not ticket:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=ticket.model_dump(mode="json", exclude_none=True),
        )

    def _exec_update(self, cmd: DSLCommand) -> DSLResult:
        if cmd.object_type == "config":
            return self._exec_update_config(cmd)
        ticket_id = cmd.target
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        params = dict(cmd.params)
        dry_run = bool(params.pop("dry_run", False)) or params.get("mode") == "dry-run"
        if not params:
            return DSLResult(ok=False, command=cmd.to_dict(), error="No fields to update.")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True,
                command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "updates": params},
                message=f"[dry-run] Would update {ticket_id}",
            )
        ticket = self.pf.update_ticket(ticket_id, **params)
        if not ticket:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=ticket.model_dump(mode="json", exclude_none=True),
            message=f"Updated {ticket.id}",
        )

    def _configuration(self):
        return self.pf.configuration

    def _exec_update_config(self, cmd: DSLCommand) -> DSLResult:
        if cmd.target:
            return DSLResult(
                ok=False,
                command=cmd.to_dict(),
                error="Use PATH=VALUE syntax: set config store.archive.enabled=false",
            )
        params = dict(cmd.params)
        mode = str(params.pop("mode", "apply"))
        actor = str(params.pop("actor", "dsl"))
        reason = str(params.pop("reason", ""))
        expected_revision = params.pop("if_revision", None)
        if not params:
            return DSLResult(
                ok=False,
                command=cmd.to_dict(),
                error="No configuration values to update.",
            )
        data = self._configuration().set_many(
            params,
            mode=mode,
            actor=actor,
            reason=reason,
            expected_revision=(
                str(expected_revision) if expected_revision is not None else None
            ),
        )
        return DSLResult(
            ok=True,
            command=cmd.to_dict(),
            data=data,
            message=(
                f"Validated {len(data['changed'])} configuration change(s)"
                if mode == "dry-run"
                else f"Applied {len(data['changed'])} configuration change(s)"
            ),
        )

    def _exec_move(self, cmd: DSLCommand) -> DSLResult:
        ticket_id = cmd.target
        to_sprint = cmd.params.get("to") or cmd.params.get("sprint")
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        if not to_sprint:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Target sprint required: move ticket ID to=sprint_id")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "to_sprint": to_sprint},
                message=f"[dry-run] Would move {ticket_id} → sprint {to_sprint}",
            )
        ok = self.pf.store.move_ticket(ticket_id, str(to_sprint))
        if not ok:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data={"ticket_id": ticket_id, "to_sprint": to_sprint},
            message=f"Moved {ticket_id} → sprint {to_sprint}",
        )

    def _exec_done(self, cmd: DSLCommand) -> DSLResult:
        ticket_id = cmd.target
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "status": "done"},
                message=f"[dry-run] Would mark {ticket_id} as done",
            )
        ticket = self.pf.update_ticket(ticket_id, status="done")
        if not ticket:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=ticket.model_dump(mode="json", exclude_none=True),
            message=f"Marked {ticket_id} as done",
        )

    def _exec_start(self, cmd: DSLCommand) -> DSLResult:
        ticket_id = cmd.target
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "status": "in_progress"},
                message=f"[dry-run] Would start {ticket_id}",
            )
        ticket = self.pf.update_ticket(ticket_id, status="in_progress")
        if not ticket:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=ticket.model_dump(mode="json", exclude_none=True),
            message=f"Started {ticket_id}",
        )

    def _exec_block(self, cmd: DSLCommand) -> DSLResult:
        ticket_id = cmd.target
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        reason = cmd.params.get("reason")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "status": "blocked", "reason": reason},
                message=f"[dry-run] Would block {ticket_id}",
            )
        ticket = self.pf.block_ticket(ticket_id, reason=reason)
        if not ticket:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=ticket.model_dump(mode="json", exclude_none=True),
            message=f"Blocked {ticket_id}",
        )

    def _exec_delete(self, cmd: DSLCommand) -> DSLResult:
        ticket_id = cmd.target
        dry_run = bool(cmd.params.get("dry_run", False)) or cmd.params.get("mode") == "dry-run"
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        if dry_run:
            ticket = self.pf.get_ticket(ticket_id)
            if not ticket:
                return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data={"dry_run": True, "ticket_id": ticket_id, "deleted": True},
                message=f"[dry-run] Would delete {ticket_id}",
            )
        ok = self.pf.delete_ticket(ticket_id)
        if not ok:
            return DSLResult(ok=False, command=cmd.to_dict(), error=f"Ticket {ticket_id} not found.")
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data={"deleted": ticket_id},
            message=f"Deleted {ticket_id}",
        )

    def _exec_validate(self, cmd: DSLCommand) -> DSLResult:

        from planfile import validate_planfile_tickets
        strategy_path = cmd.params.get("strategy", "planfile.yaml")
        project_path = cmd.params.get("project", self._project_path)
        report = validate_planfile_tickets(strategy_path=strategy_path, project_path=project_path)
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=report,
            message=(
                f"Validation: total={report.get('total', 0)} "
                f"current={report.get('current', 0)} stale={report.get('stale', 0)}"
            ),
        )

    def _exec_sync(self, cmd: DSLCommand) -> DSLResult:
        integration = cmd.target or cmd.params.get("integration", "all")
        directory = cmd.params.get("directory", self._project_path)
        dry_run = bool(cmd.params.get("dry_run", False))
        try:
            from planfile.cli.groups.sync.core import sync_integration
            if integration == "all":
                from planfile.integrations.config import IntegrationConfig
                cfg = IntegrationConfig(directory)
                cfg.load_configs()
                integrations = list(cfg.config.get("integrations", {}).keys()) or ["markdown"]
                results = []
                for intg in integrations:
                    sync_integration(intg, directory, dry_run, "to", show_header=False)
                    results.append(intg)
                return DSLResult(
                    ok=True, command=cmd.to_dict(),
                    data={"synced": results},
                    message=f"Synced: {', '.join(results)}",
                )
            else:
                sync_integration(integration, directory, dry_run, "to", show_header=False)
                return DSLResult(
                    ok=True, command=cmd.to_dict(),
                    data={"synced": integration},
                    message=f"Synced {integration}",
                )
        except Exception as exc:
            return DSLResult(ok=False, command=cmd.to_dict(), error=str(exc))

    def _exec_query(self, cmd: DSLCommand) -> DSLResult:
        return self._exec_list(cmd)

    def _exec_export(self, cmd: DSLCommand) -> DSLResult:
        fmt = cmd.params.get("format", "json")
        sprint = cmd.params.get("sprint", "all")
        tickets = self.pf.list_tickets(sprint=sprint)
        data = [t.model_dump(mode="json", exclude_none=True) for t in tickets]
        if fmt == "yaml":
            import yaml
            return DSLResult(
                ok=True, command=cmd.to_dict(),
                data=yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
                message=f"Exported {len(tickets)} tickets as YAML",
            )
        import json
        return DSLResult(
            ok=True, command=cmd.to_dict(),
            data=json.dumps(data, indent=2, default=str),
            message=f"Exported {len(tickets)} tickets as JSON",
        )
