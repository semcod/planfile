"""Import tickets from code2llm evolution.toon and analysis.toon."""

import hashlib
import re
from pathlib import Path


def import_code2llm(
    toon_path: str, auto_priority: bool = True, sprint: str = "backlog", **kwargs
) -> list[dict]:
    """Parse current HEALTH or legacy NEXT sections into persistable candidates."""
    path = Path(toon_path)
    raw = path.read_bytes()
    content = raw.decode("utf-8")
    if re.search(r"^\s*HEALTH\[\d+\]:\s*$", content, re.MULTILINE):
        tickets = _parse_health(content, auto_priority)
        digest = hashlib.sha256(raw).hexdigest()
        for ticket in tickets:
            ticket["source"]["context"].update(
                analysis_path=str(path.resolve()), analysis_sha256=digest
            )
    elif re.search(r"^\s*NEXT\[\d+\]:", content, re.MULTILINE):
        tickets = _parse_evolution(content, auto_priority)
    else:
        return []
    for ticket in tickets:
        ticket["name"] = ticket["title"]
    return tickets


def _parse_evolution(content: str, auto_priority: bool) -> list[dict]:
    """Parse NEXT[] section from evolution.toon."""
    parser = EvolutionParser(auto_priority)
    return parser.parse(content)


class EvolutionParser:
    """State machine parser for evolution.toon NEXT[] sections."""

    def __init__(self, auto_priority: bool):
        self.auto_priority = auto_priority
        self.state = "outside"
        self.tickets = []
        self.current = {}

    def parse(self, content: str) -> list[dict]:
        """Parse content and return tickets."""
        for line in content.split("\n"):
            self._process_line(line)

        # Add last ticket if exists
        if self.current:
            self.tickets.append(_evolution_item_to_ticket(self.current, self.auto_priority))

        return self.tickets

    def _process_line(self, line: str):
        """Process a single line based on current state."""
        if self.state == "outside":
            self._handle_outside(line)
        elif self.state == "in_next":
            self._handle_in_next(line)

    def _handle_outside(self, line: str):
        """Handle lines when outside NEXT[] section."""
        if line.strip().startswith("NEXT["):
            self.state = "in_next"

    def _handle_in_next(self, line: str):
        """Handle lines when inside NEXT[] section."""
        stripped = line.strip()
        if not stripped:
            return

        # Start of new item
        if stripped.startswith("[") and "]" in stripped:
            if self.current:
                self.tickets.append(_evolution_item_to_ticket(self.current, self.auto_priority))
            self.current = {"raw": stripped}

        # End of NEXT section - check if line has content but doesn't start with space
        # and is not a property line (WHY:, EFFORT:, IMPACT:)
        elif (
            stripped
            and not line.startswith(" ")
            and not stripped.startswith("[")
            and ":" not in stripped
        ):
            self.state = "outside"

        # Property lines
        elif "WHY:" in stripped:
            self.current["why"] = stripped.split("WHY:")[1].strip()
        elif "EFFORT:" in stripped:
            self.current["effort"] = stripped.split("EFFORT:")[1].strip().split()[0]
        elif "IMPACT:" in stripped:
            try:
                self.current["impact"] = int(stripped.split("IMPACT:")[1].strip())
            except ValueError:
                pass


def _evolution_item_to_ticket(item: dict, auto_priority: bool) -> dict:
    raw = item.get("raw", "")
    parts = raw.split("]", 1)[-1].strip().lstrip("! ").split(None, 1)
    action = parts[0] if parts else "REFACTOR"
    target = parts[1] if len(parts) > 1 else ""

    impact = item.get("impact", 0)
    priority = "normal"
    if auto_priority:
        if impact > 5000:
            priority = "critical"
        elif impact > 1000:
            priority = "high"

    return {
        "title": f"{action} {target}".strip(),
        "description": item.get("why", ""),
        "priority": priority,
        "labels": ["tech-debt", "refactoring", action.lower()],
        "source": {
            "tool": "code2llm",
            "context": {
                "impact": impact,
                "effort": item.get("effort"),
            },
        },
    }


def _parse_health(content: str, auto_priority: bool) -> list[dict]:
    """Import only HEALTH alerts; other sections contain repeated metrics."""
    tickets = {}
    in_health = False
    declared_count = 0
    for line in content.splitlines():
        header = re.fullmatch(r"\s*HEALTH\[(\d+)\]:\s*", line)
        if header:
            in_health = True
            declared_count += int(header[1])
            continue
        if not in_health:
            continue
        if re.match(r"^[A-Z][A-Z0-9_]*\[\d+\]:", line):
            in_health = False
            continue
        ticket = _health_alert(line.strip(), auto_priority)
        if ticket:
            key = ticket["source"]["context"]["dedupe_key"]
            tickets.setdefault(key, ticket)
    if declared_count and not tickets:
        raise ValueError("Non-empty code2llm HEALTH section has no supported alerts")
    return list(tickets.values())


def _health_ticket(
    title: str, description: str, priority: str, labels: list[str], context: dict, key: str
) -> dict:
    context["dedupe_key"] = key
    return {
        "title": title,
        "description": description,
        "priority": priority,
        "labels": ["tech-debt", *labels, f"dedupe:{key}"],
        "source": {"tool": "code2llm", "context": context},
    }


def _health_alert(line: str, auto_priority: bool) -> dict | None:
    god = re.search(r"\bGOD\s+(\S+)\s*=\s*(\d+)L\b", line)
    if god:
        path = god[1]
        if Path(path).is_absolute() or "\\" in path or ":" in path or ".." in Path(path).parts:
            raise ValueError(f"Unsafe code2llm module path: {path}")
        cc = re.search(r"max CC=(\d+)", line)
        context = {"signal": "god", "module": path, "lines": int(god[2])}
        if cc:
            context["cc"] = int(cc[1])
        ticket = _health_ticket(
            f"Split god module: {path}",
            f"Review {path} ({god[2]} lines) and split cohesive responsibilities. "
            "Preserve public behavior, run relevant tests and compare a fresh analysis. "
            "A native ticket and editing admission are required before execution.",
            "high" if auto_priority else "normal",
            ["refactoring", "god-module"],
            context,
            f"code2llm:god:{path}",
        )
        ticket["files"] = [path]
        return ticket
    dup = re.search(r"\bDUP\s+(\d+) duplicate class groups\b", line)
    if dup and int(dup[1]):
        return _health_ticket(
            f"Review duplicated classes ({dup[1]} groups)",
            "Inspect concrete duplicate groups before choosing a shared abstraction. "
            "The aggregate alert does not identify editable files.",
            "high" if auto_priority else "normal",
            ["duplication", "triage"],
            {"signal": "dup", "groups": int(dup[1])},
            "code2llm:dup:class-groups",
        )
    cycle = re.search(r"\bCYCLE\s+Circular dependency detected:\s*(.+)", line)
    if cycle:
        chain = cycle[1].split(". This indicates", 1)[0].rstrip(".")
        key = hashlib.sha256(chain.encode()).hexdigest()[:20]
        return _health_ticket(
            f"Inspect circular dependency: {chain[:120]}",
            f"Reported call chain: {chain}. Check whether recursion is intentional "
            "and whether the code is vendored before proposing a change. "
            "Resolve source files and a bounded native scope during triage.",
            "high" if auto_priority else "normal",
            ["circular-dependency", "triage"],
            {"signal": "cycle", "chain": chain},
            f"code2llm:cycle:{key}",
        )
    legacy = re.search(r"\bCC\s+(\S+)\s+(?:CC=|=\s*)(\d+)\s*\(limit:\s*\d+\)", line)
    if legacy:
        function, cc = legacy[1], int(legacy[2])
        return _health_ticket(
            f"Reduce CC: {function} (CC={cc})",
            "Reduce complexity while preserving behavior and run relevant tests.",
            "high" if auto_priority and cc > 20 else "normal",
            ["complexity", "cc-violation"],
            {"function": function, "cc": cc},
            f"code2llm:cc:{function}",
        )
    return None
