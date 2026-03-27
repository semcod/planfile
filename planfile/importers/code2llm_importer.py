"""Import tickets from code2llm evolution.toon and analysis.toon."""


def import_code2llm(toon_path: str, auto_priority: bool = True,
                     sprint: str = "backlog", **kwargs) -> list[dict]:
    """Parse evolution.toon NEXT[] → ticket dicts."""
    content = open(toon_path, encoding="utf-8").read()

    if "NEXT[" in content:
        return _parse_evolution(content, auto_priority)
    elif "HEALTH[" in content:
        return _parse_health(content, auto_priority)
    return []


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
        elif (stripped and 
              not line.startswith(" ") and 
              not stripped.startswith("[") and
              ":" not in stripped):
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
        "source": {"tool": "code2llm", "context": {
            "impact": impact,
            "effort": item.get("effort"),
        }},
    }


def _parse_health(content: str, auto_priority: bool) -> list[dict]:
    """Parse HEALTH[] section from analysis.toon."""
    tickets = []
    for line in content.split("\n"):
        if "CC" in line and "limit:" in line:
            parts = line.strip().split()
            func = parts[2] if len(parts) > 2 else "unknown"
            cc_str = [p for p in parts if p.startswith("CC=")]
            cc = int(cc_str[0].split("=")[1]) if cc_str else 0
            tickets.append({
                "title": f"Reduce CC: {func} (CC={cc})",
                "priority": "high" if cc > 20 else "normal",
                "labels": ["complexity", "cc-violation"],
                "source": {"tool": "code2llm", "context": {
                    "function": func, "cc": cc,
                }},
            })
    return tickets
