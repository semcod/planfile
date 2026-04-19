#!/usr/bin/env python3
"""Debug: test different regex patterns."""
import re

content = """**ID:** `refactor-cli-20250329-123045`"""

patterns = [
    r"ID: `([^`]+)`",
    r"ID:\s*`([^`]+)`",
    r"\*\*ID:\*\* `([^`]+)`",
    r"ID:\*\* `([^`]+)`",
    r"`([^`]+)`",
]

print("Testing patterns:")
for p in patterns:
    matches = list(re.finditer(p, content))
    print(f"  Pattern '{p}': {len(matches)} matches")
    for m in matches:
        print(f"    -> '{m.group(1)}'")
