# Planfile Checkbox Tickets Example

This example demonstrates planfile's support for native markdown checkbox tickets (`- [ ]` / `- [x]`).

## Files

- `TODO.md` - Example TODO file with checkbox-style tickets
- `demo.py` - Python script demonstrating checkbox parsing and sync
- `run.sh` - Convenience script to run the demo

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 demo.py
```

## What You'll Learn

1. **Checkbox Format** - Use standard markdown checkboxes for tickets
2. **Status Detection** - Automatic recognition of `[ ]` (open) vs `[x]` (completed)
3. **Sync Integration** - Sync checkbox tickets with planfile
4. **Toggle Status** - Programmatically mark tickets as done/undone

## Checkbox Format

```markdown
## Pending Tasks
- [ ] Fix authentication bug in login.py:42
- [ ] Add validation to user form
- [ ] Update documentation for API v2

## Completed Tasks  
- [x] Setup project structure
- [x] Configure CI/CD pipeline
- [x] Initial release v1.0
```

## Next Steps

After running this example:

1. Edit `TODO.md` and check/uncheck some items
2. Run `python3 demo.py` again to see status changes
3. Try: `planfile sync markdown` to sync with planfile
4. Use `--direction from` to import checkbox tickets into planfile

## Tips

- Works with any markdown file (TODO.md, CHANGELOG.md, etc.)
- Ticket IDs are auto-generated: `TODO-{line}-{content_hash}`
- Status is automatically detected from checkbox state
- No external APIs required - pure markdown support
