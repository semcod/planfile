#!/usr/bin/env python3
"""
Example 2: MCP Tools Integration
Demonstrates how planfile can be used as MCP tools for LLM agents
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List

def run_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate running an MCP tool."""
    print(f"\n🔧 MCP Tool: {tool_name}")
    print(f"Arguments: {json.dumps(arguments, indent=2)}")
    
    if tool_name == "planfile_generate":
        return simulate_planfile_generate(arguments)
    elif tool_name == "planfile_apply":
        return simulate_planfile_apply(arguments)
    elif tool_name == "planfile_review":
        return simulate_planfile_review(arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def simulate_planfile_generate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate planfile generate tool."""
    project_path = args.get("project_path", ".")
    model = args.get("model", "anthropic/claude-sonnet-4")
    sprints = args.get("sprints", 3)
    focus = args.get("focus", "complexity")
    
    # Simulate project analysis
    metrics = {
        "total_files": 25,
        "total_lines": 3500,
        "avg_cc": 5.2,
        "max_cc": 18,
        "critical_count": 3,
        "god_modules": 2,
        "dup_groups": 5
    }
    
    # Generate strategy based on metrics
    strategy = {
        "project": {
            "name": Path(project_path).name,
            "focus": focus,
            "metrics": metrics
        },
        "sprints": [],
        "quality_gates": []
    }
    
    # Generate sprints
    for i in range(sprints):
        sprint = {
            "id": f"sprint-{i+1}",
            "name": f"Sprint {i+1}: {'Critical Fixes' if i == 0 else 'Refactoring' if i == 1 else 'Polish'}",
            "goal": "Reduce complexity and improve code quality" if i == 0 else "Refactor god modules" if i == 1 else "Add tests and documentation",
            "task_patterns": []
        }
        
        # Add tasks based on focus
        if focus == "complexity":
            if i == 0:
                sprint["task_patterns"] = [
                    {
                        "name": f"Split high-CC function (CC={metrics['max_cc']})",
                        "task_type": "refactor",
                        "priority": "critical",
                        "model_hints": {"planning": "premium", "implementation": "balanced"}
                    },
                    {
                        "name": f"Extract {metrics['god_modules']} god modules",
                        "task_type": "refactor",
                        "priority": "high",
                        "model_hints": {"planning": "premium", "implementation": "premium"}
                    }
                ]
            elif i == 1:
                sprint["task_patterns"] = [
                    {
                        "name": "Implement repository pattern",
                        "task_type": "refactor",
                        "priority": "medium",
                        "model_hints": {"planning": "balanced", "implementation": "balanced"}
                    }
                ]
        
        strategy["sprints"].append(sprint)
    
    # Add quality gates
    strategy["quality_gates"] = [
        {
            "name": "Complexity Gate",
            "metric": "avg_cc",
            "threshold": 3.0,
            "operator": "<="
        },
        {
            "name": "Coverage Gate",
            "metric": "test_coverage",
            "threshold": 80,
            "operator": ">="
        }
    ]
    
    # Save strategy
    output_file = args.get("output", "strategy.yaml")
    print(f"✓ Strategy generated and saved to: {output_file}")
    
    return {
        "success": True,
        "strategy": strategy,
        "metrics": metrics,
        "output_file": output_file
    }

def simulate_planfile_apply(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate planfile apply tool."""
    strategy_path = args.get("strategy_path", "strategy.yaml")
    backend = args.get("backend", "github")
    dry_run = args.get("dry_run", True)
    
    # Simulate loading strategy
    strategy = {
        "sprints": [
            {"id": "sprint-1", "task_patterns": [{"name": "Task 1"}, {"name": "Task 2"}]},
            {"id": "sprint-2", "task_patterns": [{"name": "Task 3"}]}
        ]
    }
    
    tickets = []
    total_tasks = 0
    
    for sprint in strategy["sprints"]:
        for task in sprint["task_patterns"]:
            total_tasks += 1
            if not dry_run:
                # Simulate creating ticket
                ticket_url = f"https://github.com/example/repo/issues/{total_tasks}"
                tickets.append(ticket_url)
                print(f"  ✓ Created ticket: {task['name']} -> {ticket_url}")
            else:
                print(f"  📍 Would create ticket: {task['name']}")
    
    return {
        "success": True,
        "backend": backend,
        "dry_run": dry_run,
        "total_tasks": total_tasks,
        "tickets_created": tickets,
        "message": f"{'Dry run completed' if dry_run else f'Created {len(tickets)} tickets'}"
    }

def simulate_planfile_review(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate planfile review tool."""
    strategy_path = args.get("strategy_path", "strategy.yaml")
    project_path = args.get("project_path", ".")
    
    # Simulate collecting metrics
    current_metrics = {
        "avg_cc": 4.1,  # Improved from 5.2
        "max_cc": 12,   # Improved from 18
        "test_coverage": 65,  # Added coverage
        "god_modules": 1,     # Reduced from 2
    }
    
    # Calculate progress
    total_tasks = 10
    completed_tasks = 4
    progress = (completed_tasks / total_tasks) * 100
    
    # Check quality gates
    quality_gates = [
        {"name": "Complexity Gate", "threshold": 3.0, "current": current_metrics["avg_cc"], "passed": False},
        {"name": "Coverage Gate", "threshold": 80, "current": current_metrics["test_coverage"], "passed": False}
    ]
    
    return {
        "success": True,
        "progress": {
            "completion_percentage": progress,
            "tasks_completed": completed_tasks,
            "total_tasks": total_tasks,
            "sprints_completed": 1,
            "total_sprints": 3
        },
        "metrics": current_metrics,
        "quality_gates": quality_gates,
        "recommendations": [
            "Focus on reducing cyclomatic complexity in remaining modules",
            "Increase test coverage to meet quality gate",
            "Complete remaining tasks in Sprint 2"
        ]
    }

def example_mcp_session():
    """Example of an LLM agent using planfile MCP tools."""
    print("=" * 60)
    print("MCP Tools Integration Example")
    print("=" * 60)
    
    # Agent's plan
    agent_plan = """
    Agent: I need to refactor this Python project to reduce complexity.
    
    Plan:
    1. Generate a refactoring strategy using planfile_generate
    2. Apply the strategy to create tickets in GitHub
    3. Review progress after initial work
    """
    
    print(agent_plan)
    
    # Step 1: Generate strategy
    print("\n" + "=" * 40)
    print("STEP 1: Generate Strategy")
    print("=" * 40)
    
    result1 = run_mcp_tool("planfile_generate", {
        "project_path": "./my-project",
        "model": "anthropic/claude-sonnet-4",
        "sprints": 3,
        "focus": "complexity",
        "output": "refactor-strategy.yaml"
    })
    
    print(f"Result: {json.dumps(result1, indent=2)}")
    
    # Step 2: Apply strategy
    print("\n" + "=" * 40)
    print("STEP 2: Apply Strategy")
    print("=" * 40)
    
    result2 = run_mcp_tool("planfile_apply", {
        "strategy_path": "refactor-strategy.yaml",
        "backend": "github",
        "dry_run": True
    })
    
    print(f"Result: {json.dumps(result2, indent=2)}")
    
    # Step 3: Review progress
    print("\n" + "=" * 40)
    print("STEP 3: Review Progress")
    print("=" * 40)
    
    result3 = run_mcp_tool("planfile_review", {
        "strategy_path": "refactor-strategy.yaml",
        "project_path": "./my-project"
    })
    
    print(f"Result: {json.dumps(result3, indent=2)}")
    
    # Agent's conclusion
    print("\n" + "=" * 40)
    print("AGENT'S CONCLUSION")
    print("=" * 40)
    
    conclusion = """
    Agent: Based on the review:
    - Progress is at 40% (4/10 tasks complete)
    - Complexity reduced from 5.2 to 4.1 (on track)
    - Test coverage at 65% (need 15% more to meet gate)
    
    Next actions:
    1. Complete remaining tasks in Sprint 2
    2. Add unit tests to increase coverage
    3. Continue refactoring to meet complexity gate
    
    The MCP tools provided a complete workflow for managing the refactoring process!
    """
    
    print(conclusion)

def create_mcp_tool_definitions():
    """Create MCP tool definitions for integration."""
    tools = [
        {
            "name": "planfile_generate",
            "description": "Generate a refactoring strategy YAML from project analysis. Uses LLM to create sprints, tasks, and quality gates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "default": "."},
                    "model": {"type": "string", "description": "LiteLLM model ID"},
                    "sprints": {"type": "integer", "default": 3},
                    "focus": {"type": "string", "enum": ["complexity", "duplication", "tests", "docs"]},
                    "output": {"type": "string", "default": "strategy.yaml"}
                }
            }
        },
        {
            "name": "planfile_apply",
            "description": "Apply a strategy.yaml to a project — create tickets, execute tasks.",
            "inputSchema": {
                "type": "object",
                "required": ["strategy_path"],
                "properties": {
                    "strategy_path": {"type": "string"},
                    "project_path": {"type": "string", "default": "."},
                    "backend": {"type": "string", "enum": ["github", "jira", "gitlab", "generic"]},
                    "dry_run": {"type": "boolean", "default": False}
                }
            }
        },
        {
            "name": "planfile_review",
            "description": "Review progress against a strategy — check quality gates, report status.",
            "inputSchema": {
                "type": "object",
                "required": ["strategy_path"],
                "properties": {
                    "strategy_path": {"type": "string"},
                    "project_path": {"type": "string", "default": "."}
                }
            }
        }
    ]
    
    # Save tool definitions
    with open("mcp-tools.json", "w") as f:
        json.dump(tools, f, indent=2)
    
    print("\n✅ MCP tool definitions saved to: mcp-tools.json")
    
    # Create example MCP server integration
    server_code = '''
# Example MCP Server Integration
from mcp.server import Server
from mcp.server.stdio import stdio_server
from planfile.mcp import handle_planfile_generate, handle_planfile_apply, handle_planfile_review

app = Server("planfile-mcp")

@app.call_tool()
async def planfile_generate(arguments):
    return await handle_planfile_generate(arguments)

@app.call_tool()
async def planfile_apply(arguments):
    return await handle_planfile_apply(arguments)

@app.call_tool()
async def planfile_review(arguments):
    return await handle_planfile_review(arguments)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
    
    with open("mcp-server-example.py", "w") as f:
        f.write(server_code)
    
    print("✅ MCP server example saved to: mcp-server-example.py")

if __name__ == "__main__":
    example_mcp_session()
    create_mcp_tool_definitions()
