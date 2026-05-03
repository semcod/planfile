"""CLI DSL usage examples.

Run these via: planfile dsl <command>
"""

# Example 1: List tickets
# planfile dsl "list tickets sprint=current"

# Example 2: List with filters
# planfile dsl "list tickets sprint=current status=open priority=high"

# Example 3: Create ticket
# planfile dsl 'create ticket "Fix login bug" priority=high sprint=1 labels=backend,auth'

# Example 4: Show ticket
# planfile dsl "show ticket PLF-001"

# Example 5: Update ticket
# planfile dsl "update ticket PLF-001 status=done"

# Example 6: Set multiple fields
# planfile dsl "set ticket PLF-002 priority=critical labels=security,urgent"

# Example 7: Move ticket to sprint
# planfile dsl "move ticket PLF-003 to sprint=2"

# Example 8: Mark ticket as done
# planfile dsl "done ticket PLF-004"

# Example 9: Start ticket
# planfile dsl "start ticket PLF-005"

# Example 10: Block ticket
# planfile dsl 'block ticket PLF-006 reason="Waiting for API"'

# Example 11: Delete ticket
# planfile dsl "delete ticket PLF-007"

# Example 12: List sprints
# planfile dsl "list sprints"

# Example 13: Add sprint
# planfile dsl 'add sprint "Sprint 4" days=14'

# Example 14: Validate tickets
# planfile dsl "validate"

# Example 15: Sync to integration
# planfile dsl "sync github"

# Example 16: Sync all integrations
# planfile dsl "sync all"

# Example 17: Query with where clause
# planfile dsl "query tickets where priority=high status=open"

# Example 18: Export to YAML
# planfile dsl "export format=yaml"

# Example 19: Export to JSON
# planfile dsl "export format=json"

# Example 20: Interactive shell
# planfile dsl

# Format options
# planfile dsl "list tickets" --format json
# planfile dsl "list tickets" --format yaml
# planfile dsl "list tickets" --format text  # default

# Fail on error (exit code 1 if command fails)
# planfile dsl "update ticket PLF-999 status=done" --fail-on-error

# Use different project path
# planfile dsl "list tickets" --project /path/to/project
