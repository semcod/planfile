"""Import tickets from vallm validation.toon."""


def import_vallm(toon_path: str, auto_priority: bool = True, **kwargs) -> list[dict]:
    """Parse vallm validation.toon ERRORS[] → ticket dicts."""
    content = open(toon_path, encoding="utf-8").read()
    tickets = []
    current_file = None

    for line in content.split("\n"):
        stripped = line.strip()
        # File entry: "  llx/orchestration/__init__.py,0.57"
        if stripped and "," in stripped and not stripped.startswith("issues"):
            parts = stripped.rsplit(",", 1)
            if len(parts) == 2:
                try:
                    float(parts[1])
                    current_file = parts[0].strip()
                except ValueError:
                    pass
        # Issue: "  python.import.resolvable,error,Module 'X' not found,3"
        elif current_file and stripped and "," in stripped:
            issue_parts = stripped.split(",", 3)
            if len(issue_parts) >= 3 and issue_parts[1] == "error":
                rule = issue_parts[0]
                message = issue_parts[2]

                priority = "normal"
                if auto_priority and "import" in rule:
                    priority = "critical"
                elif auto_priority and "syntax" in rule:
                    priority = "high"

                tickets.append({
                    "title": f"{rule}: {current_file}",
                    "description": message,
                    "priority": priority,
                    "labels": _auto_labels(rule),
                    "source": {"tool": "vallm", "context": {
                        "file": current_file,
                        "rule": rule,
                        "message": message,
                    }},
                })
    return tickets


def _auto_labels(rule: str) -> list[str]:
    labels = [rule.split(".")[0]]
    if "import" in rule:
        labels.append("import-error")
    if "syntax" in rule:
        labels.append("syntax-error")
    return labels
