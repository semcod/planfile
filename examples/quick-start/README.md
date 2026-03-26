# Quick Start Examples

Get started with planfile in minutes! This example shows the basics:
- Generate strategy from files
- Create templates
- Load and analyze strategies
- Export to different formats
- Compare strategies

## Files

- `quick_start_examples.py` - Main example script
- `run.sh` - Convenience script to run the example

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 quick_start_examples.py
```

## What You'll Learn

1. **Generate from Files** - Analyze current directory and create strategy
2. **Create Template** - Generate project templates (web, mobile, ML)
3. **Load and Analyze** - Load strategies and get statistics
4. **Export Formats** - Export to YAML, JSON, and Python dict
5. **Compare Strategies** - Compare two strategies and see differences

## Generated Files

- `quick-start.yaml` - Basic generated strategy
- `web-template.yaml` - Web project template
- `web-template.json` - Template in JSON format

## Next Steps

After running this example:

1. Open the YAML files to see the strategy structure
2. Try: `python3 -m planfile.cli.commands stats quick-start.yaml`
3. Try: `python3 -m planfile.cli.commands export web-template.yaml --format html`
4. Try: `python3 -m planfile.cli.commands template mobile fitness`

## Tips

- No external dependencies required
- Works with any Python project
- Generated strategies are ready to use
- Export to multiple formats for integration
