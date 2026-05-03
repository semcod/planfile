"""MCP (Model Context Protocol) DSL tool usage examples.

MCP allows LLM agents to use planfile DSL commands directly.
Run MCP server: python -m planfile.mcp.server
"""

import json
import sys


def example_mcp_dsl_tool():
    """Example MCP tool call for planfile_dsl."""
    # MCP tool call (JSON-RPC)
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "planfile_dsl",
            "arguments": {
                "command": "list tickets sprint=current status=open",
                "project_path": "."
            }
        }
    }

    # Simulate sending to MCP server (via stdio)
    print("MCP Request:", json.dumps(mcp_request))
    print("\nExpected response structure:")
    print({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "ok": True,
                    "command": {"verb": "list", ...},
                    "data": [...],
                    "message": "Found 3 ticket(s)"
                })
            }]
        }
    })


def example_mcp_yaml_get():
    """Example MCP tool call for reading planfile.yaml."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "planfile_yaml_get",
            "arguments": {
                "project_path": "."
            }
        }
    }
    print("MCP Request:", json.dumps(mcp_request))


def example_mcp_yaml_patch():
    """Example MCP tool call for patching planfile.yaml."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "planfile_yaml_patch",
            "arguments": {
                "path": "metadata.model_tier",
                "value": "premium",
                "project_path": "."
            }
        }
    }
    print("MCP Request:", json.dumps(mcp_request))


def example_mcp_list_sprints():
    """Example MCP tool call for listing sprints."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "planfile_list_sprints",
            "arguments": {
                "project_path": "."
            }
        }
    }
    print("MCP Request:", json.dumps(mcp_request))


def example_mcp_tools_list():
    """List all available MCP tools."""
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/list",
        "params": {}
    }
    print("MCP Request:", json.dumps(mcp_request))


def example_full_mcp_workflow():
    """Complete MCP workflow: list -> create -> validate -> sync."""
    commands = [
        "list tickets sprint=current",
        'create ticket "Fix bug" priority=high',
        "validate",
        "sync github"
    ]

    for cmd in commands:
        mcp_request = {
            "jsonrpc": "2.0",
            "id": hash(cmd),
            "method": "tools/call",
            "params": {
                "name": "planfile_dsl",
                "arguments": {"command": cmd, "project_path": "."}
            }
        }
        print(f"\nCommand: {cmd}")
        print("MCP Request:", json.dumps(mcp_request))


if __name__ == "__main__":
    print("MCP DSL Tool Examples")
    print("=" * 40)
    print("Start MCP server: python -m planfile.mcp.server\n")

    example_mcp_tools_list()
    print("\n" + "-" * 40 + "\n")

    example_mcp_dsl_tool()
    print("\n" + "-" * 40 + "\n")

    example_mcp_yaml_get()
    print("\n" + "-" * 40 + "\n")

    example_mcp_yaml_patch()
    print("\n" + "-" * 40 + "\n")

    example_mcp_list_sprints()
    print("\n" + "-" * 40 + "\n")

    example_full_mcp_workflow()
