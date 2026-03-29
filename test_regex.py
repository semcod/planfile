#!/usr/bin/env python3
"""Quick regex test for structured ticket ID pattern."""
import re

content = """### Structured Tickets (legacy format)
## 🟠 Refactor cli.py

**ID:** `refactor-cli-20250329-123045`
**Priority:** high
**Labels:** refactoring, cli

Need to break down the large functions.

---

## 🟡 Update documentation

**ID:** `update-docs-20250329-123046`  
**Priority:** medium

Update README with new examples.

---
"""

id_pattern = r"ID: `([^`]+)`"
matches = list(re.finditer(id_pattern, content))

print(f"Found {len(matches)} ID matches:")
for m in matches:
    print(f"  ID: '{m.group(1)}'")
