"""DSL executor — maps DSLCommand to planfile operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from planfile.dsl.parser import DSLCommand, DSLParser


@dataclass
class DSLResult:
    ok: bool
    command: dict = field(default_factory=dict)
    data: Any = None
    error: str | None = None
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "command": self.command,
            "data": self.data,
            "error": self.error,
            "message": self.message,
        }


class DSLExecutor:
    """Execute DSL commands against a Planfile instance."""

    def __init__(self, project_path: str = "."):
        self._project_path = project_path
        self._pf = None
        self._parser = DSLParser()

    @property
    def pf(self):
        if self._pf is None:
            from planfile import Planfile
            self._pf = Planfile.auto_discover(self._project_path)
        return self._pf

    def run(self, text: str) -> DSLResult:
        """Parse and execute a DSL command string."""
        cmd = self._parser.parse(text)
        return self.execute(cmd)

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
        return DSLResult(
            ok=False,
            command=cmd.to_dict(),
            error=f"Unrecognized command: '{cmd.raw}'. Type 'help' for usage.",
        )

    def _exec_create(self, cmd: DSLCommand) -> DSLResult:
        obj = cmd.object_type or "ticket"
        if obj == "ticket":
            name = cmd.target or cmd.params.pop("name", None)
            if not name:
                return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket name required.")
            params = dict(cmd.params)
            params.setdefault("priority", "normal")
            params.setdefault("sprint", "current")
            from planfile import TicketSource
            ticket = self.pf.create_ticket(
                name=name,
                priority=params.pop("priority"),
                sprint=params.pop("sprint"),
                description=params.pop("description", ""),
                labels=params.pop("labels", []),
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
        import yaml
        from pathlib import Path
        name = cmd.target or cmd.params.get("name", f"Sprint")
        days = int(cmd.params.get("days", 14))
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
        import yaml
        from pathlib import Path
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
        if not cmd.params:
            return DSLResult(ok=False, command=cmd.to_dict(), error="No fields to update.")
        ticket = self.pf.update_ticket(ticket_id, **cmd.params)
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
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        if not to_sprint:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Target sprint required: move ticket ID to=sprint_id")
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
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
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
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
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
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
        reason = cmd.params.get("reason")
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
        if not ticket_id:
            return DSLResult(ok=False, command=cmd.to_dict(), error="Ticket ID required.")
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
        from pathlib import Path
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
