"""Import tickets from vallm validation.toon."""


def import_vallm(toon_path: str, auto_priority: bool = True, **kwargs) -> list[dict]:
    """Parse vallm validation.toon ERRORS[] → ticket dicts."""
    content = open(toon_path, encoding="utf-8").read()
    parser = VallmParser(auto_priority)
    return parser.parse(content)


class VallmParser:
    """Parser for vallm validation.toon files."""

    def __init__(self, auto_priority: bool = True):
        self.auto_priority = auto_priority
        self.current_file = None
        self.tickets = []

    def parse(self, content: str) -> list[dict]:
        """Parse content and extract tickets."""
        for line in content.split("\n"):
            self._process_line(line.strip())
        return self.tickets

    def _process_line(self, line: str):
        """Process a single line from the content."""
        if not line:
            return

        if self._is_file_entry(line):
            self._parse_file_entry(line)
        elif self._is_issue_entry(line):
            self._parse_issue_entry(line)

    def _is_file_entry(self, line: str) -> bool:
        """Check if line is a file entry."""
        return ("," in line and
                not line.startswith("issues") and
                not line.count(",") >= 3)

    def _is_issue_entry(self, line: str) -> bool:
        """Check if line is an issue entry."""
        return (self.current_file and
                "," in line and
                line.count(",") >= 3)

    def _parse_file_entry(self, line: str):
        """Parse a file entry and update current_file."""
        parts = line.rsplit(",", 1)
        if len(parts) == 2:
            try:
                float(parts[1])  # Validate it's a score
                self.current_file = parts[0].strip()
            except ValueError:
                pass

    def _parse_issue_entry(self, line: str):
        """Parse an issue entry and create a ticket."""
        issue_parts = line.split(",", 3)
        if len(issue_parts) >= 3 and issue_parts[1] == "error":
            rule = issue_parts[0]
            message = issue_parts[2]

            ticket = {
                "title": f"{rule}: {self.current_file}",
                "description": message,
                "priority": self._determine_priority(rule),
                "labels": _auto_labels(rule),
                "source": {"tool": "vallm", "context": {
                    "file": self.current_file,
                    "rule": rule,
                    "message": message,
                }},
            }
            self.tickets.append(ticket)

    def _determine_priority(self, rule: str) -> str:
        """Determine ticket priority based on rule."""
        if not self.auto_priority:
            return "normal"

        if "import" in rule:
            return "critical"
        elif "syntax" in rule:
            return "high"

        return "normal"


def _auto_labels(rule: str) -> list[str]:
    labels = [rule.split(".")[0]]
    if "import" in rule:
        labels.append("import-error")
    if "syntax" in rule:
        labels.append("syntax-error")
    return labels
