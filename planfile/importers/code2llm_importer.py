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
    tickets = []
    in_next = False
    current = {}
    for line in content.split("\n"):
        if line.strip().startswith("NEXT["):
            in_next = True
            continue
        if in_next and line.strip().startswith("[") and "]" in line:
            if current:
                tickets.append(_evolution_item_to_ticket(current, auto_priority))
            current = {"raw": line.strip()}
        elif in_next and "WHY:" in line:
            current["why"] = line.split("WHY:")[1].strip()
        elif in_next and "EFFORT:" in line:
            current["effort"] = line.split("EFFORT:")[1].strip().split()[0]
        elif in_next and "IMPACT:" in line:
            try:
                current["impact"] = int(line.split("IMPACT:")[1].strip())
            except ValueError:
                pass
        elif in_next and line.strip() and not line.startswith(" "):
            in_next = False
    if current:
        tickets.append(_evolution_item_to_ticket(current, auto_priority))
    return tickets


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
