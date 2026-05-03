# MCP (Model Context Protocol) Examples

This directory contains examples for using planfile via MCP (Model Context Protocol).

## Overview

MCP allows LLM agents to use planfile DSL commands directly through a standardized protocol. The MCP server exposes tools that agents can call to:

- Execute DSL commands (full DSL support)
- Read planfile.yaml as JSON
- Patch planfile.yaml via dot-notation
- List sprints

## Running MCP Server

```bash
python -m planfile.mcp.server
```

The MCP server uses stdio transport and expects JSON-RPC messages on stdin.

## Examples

- `01_dsl_tool.py` — MCP tool call examples for DSL, YAML operations, and sprint management

## MCP Tools

### planfile_dsl

Execute a DSL command against planfile.

```json
{
  "name": "planfile_dsl",
  "arguments": {
    "command": "list tickets sprint=current",
    "project_path": "."
  }
}
```

### planfile_yaml_get

Read the full planfile.yaml as a JSON object.

```json
{
  "name": "planfile_yaml_get",
  "arguments": {
    "project_path": "."
  }
}
```

### planfile_yaml_patch

Patch a key in planfile.yaml using dot-notation.

```json
{
  "name": "planfile_yaml_patch",
  "arguments": {
    "path": "metadata.model_tier",
    "value": "premium",
    "project_path": "."
  }
}
```

### planfile_list_sprints

List all sprints from planfile.yaml.

```json
{
  "name": "planfile_list_sprints",
  "arguments": {
    "project_path": "."
  }
}
```

## Integration with LLMs

To use planfile MCP with an LLM (e.g., Claude, ChatGPT), configure the MCP server in your LLM client:

```json
{
  "mcpServers": {
    "planfile": {
      "command": "python",
      "args": ["-m", "planfile.mcp.server"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Then the LLM can use planfile commands like:
- "List all high-priority tickets in the current sprint"
- "Create a ticket for the login bug"
- "Mark ticket PLF-001 as done"
- "Validate tickets and sync to GitHub"
