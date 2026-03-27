#!/usr/bin/env python3
"""
Example 3: Proxy Integration for Smart Model Routing
Demonstrates how planfile uses proxy for cost-effective model selection
"""

import asyncio
import json
from typing import Any

import aiohttp


class ProxyClient:
    """Client for interacting with Proxym API."""

    def __init__(self, base_url: str = "http://localhost:4000"):
        self.base_url = base_url

    async def chat(self, messages: list[dict], model: str = None, task_type: str = None) -> dict[str, Any]:
        """Send chat request through proxy with smart routing."""
        payload = {
            "messages": messages,
            "task_type": task_type,  # Let proxy choose model based on task
            "model": model,  # Optional override
            "max_tokens": 4096,
            "temperature": 0.2
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/v1/chat/completions", json=payload) as resp:
                return await resp.json()

    async def get_routing_decision(self, task_type: str, complexity: str) -> dict[str, Any]:
        """Get routing decision from proxy."""
        payload = {
            "task_type": task_type,
            "complexity": complexity,
            "budget_limit": 1.0
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/routing/decide", json=payload) as resp:
                return await resp.json()

    async def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics from proxy."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/stats") as resp:
                return await resp.json()

async def example_strategy_generation_with_proxy():
    """Example: Generate strategy using proxy for smart model routing."""
    print("=" * 60)
    print("Strategy Generation with Proxy Model Routing")
    print("=" * 60)

    proxy = ProxyClient()

    # Project metrics
    project_metrics = {
        "total_files": 45,
        "total_lines": 8500,
        "avg_cc": 6.2,
        "max_cc": 24,
        "critical_count": 5,
        "god_modules": 3,
        "dup_groups": 8
    }

    # Step 1: Get routing decisions for different tasks
    print("\n1. Getting routing decisions from proxy...")

    tasks = [
        ("planning", "high", "Generate overall refactoring strategy"),
        ("refactor", "critical", "Split god module with CC=24"),
        ("test", "medium", "Write unit tests for service layer"),
        ("docs", "low", "Generate API documentation"),
        ("review", "medium", "Review code changes")
    ]

    routing_decisions = {}

    for task_type, complexity, description in tasks:
        decision = await proxy.get_routing_decision(task_type, complexity)
        routing_decisions[task_type] = decision

        print(f"\nTask: {description}")
        print(f"  Type: {task_type}, Complexity: {complexity}")
        print(f"  Selected Model: {decision.get('model', 'auto')}")
        print(f"  Est. Cost: ${decision.get('estimated_cost', 0):.4f}")
        print(f"  Reasoning: {decision.get('reasoning', 'N/A')}")

    # Step 2: Generate strategy using routed models
    print("\n\n2. Generating strategy tasks using routed models...")

    strategy_prompt = f"""
    Based on these project metrics, generate a refactoring strategy:
    
    Metrics: {json.dumps(project_metrics, indent=2)}
    
    Create 3 sprints with specific tasks for:
    - Sprint 1: Critical fixes (god modules, high CC)
    - Sprint 2: Systematic refactoring (patterns, architecture)
    - Sprint 3: Quality improvements (tests, docs, coverage)
    
    Output as YAML with sprints, tasks, and quality gates.
    """

    strategy_results = {}

    for task_type in ["planning"]:
        messages = [
            {"role": "system", "content": "You are a software engineering strategist. Generate YAML output only."},
            {"role": "user", "content": strategy_prompt}
        ]

        result = await proxy.chat(messages, task_type=task_type)
        strategy_results[task_type] = result

        model_used = result.get("model", "unknown")
        cost = result.get("usage", {}).get("cost", 0)

        print(f"\n✓ Strategy generated using: {model_used}")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Tokens: {result.get('usage', {}).get('total_tokens', 0)}")

    # Step 3: Generate individual tasks with appropriate models
    print("\n\n3. Generating individual tasks with task-specific models...")

    task_results = []

    for i, (task_type, complexity, description) in enumerate(tasks[1:], 1):  # Skip planning
        task_prompt = f"""
        Task: {description}
        
        Context:
        - Part of larger refactoring strategy
        - Complexity level: {complexity}
        - Task type: {task_type}
        
        Generate:
        1. Detailed implementation steps
        2. Code examples if applicable
        3. Success criteria
        4. Estimated effort (hours)
        
        Be specific and actionable.
        """

        messages = [
            {"role": "system", "content": f"You are an expert software engineer specializing in {task_type}."},
            {"role": "user", "content": task_prompt}
        ]

        result = await proxy.chat(messages, task_type=task_type)
        task_results.append(result)

        model_used = result.get("model", "unknown")
        cost = result.get("usage", {}).get("cost", 0)

        print(f"\nTask {i}: {description[:30]}...")
        print(f"  Model: {model_used}")
        print(f"  Cost: ${cost:.4f}")

    # Step 4: Summary and cost analysis
    print("\n\n4. Cost Analysis Summary")
    print("=" * 40)

    total_cost = 0
    model_usage = {}

    # Analyze strategy generation
    for task_type, result in strategy_results.items():
        cost = result.get("usage", {}).get("cost", 0)
        model = result.get("model", "unknown")
        total_cost += cost
        model_usage[model] = model_usage.get(model, 0) + cost

    # Analyze task generation
    for result in task_results:
        cost = result.get("usage", {}).get("cost", 0)
        model = result.get("model", "unknown")
        total_cost += cost
        model_usage[model] = model_usage.get(model, 0) + cost

    print(f"Total Cost: ${total_cost:.4f}")
    print("\nCost by Model:")
    for model, cost in sorted(model_usage.items(), key=lambda x: x[1], reverse=True):
        percentage = (cost / total_cost) * 100 if total_cost > 0 else 0
        print(f"  {model}: ${cost:.4f} ({percentage:.1f}%)")

    # Compare with using premium model for everything
    premium_cost_per_task = 0.015  # Example: Claude Opus
    num_tasks = len(tasks)
    total_premium_cost = premium_cost_per_task * num_tasks

    print("\nCost Comparison:")
    print(f"  Smart routing: ${total_cost:.4f}")
    print(f"  All premium:   ${total_premium_cost:.4f}")
    print(f"  Savings:       ${total_premium_cost - total_cost:.4f} ({((total_premium_cost - total_cost) / total_premium_cost * 100):.1f}%)")

def create_proxy_config_example():
    """Create example proxy configuration for planfile integration."""
    config = {
        "routing": {
            "rules": [
                {
                    "name": "planfile_planning",
                    "pattern": {
                        "task_type": "planning",
                        "min_complexity": "medium"
                    },
                    "models": ["anthropic/claude-sonnet-4", "openai/gpt-4"],
                    "fallback": True,
                    "max_cost_per_request": 2.0
                },
                {
                    "name": "planfile_critical_refactor",
                    "pattern": {
                        "task_type": "refactor",
                        "complexity": "critical"
                    },
                    "models": ["anthropic/claude-opus-4"],
                    "max_cost_per_request": 5.0
                },
                {
                    "name": "planfile_standard_refactor",
                    "pattern": {
                        "task_type": "refactor",
                        "complexity": ["low", "medium"]
                    },
                    "models": ["anthropic/claude-sonnet-4", "openai/gpt-4"],
                    "max_cost_per_request": 1.0
                },
                {
                    "name": "planfile_tests",
                    "pattern": {
                        "task_type": "test"
                    },
                    "models": ["anthropic/claude-haiku-4.5", "openai/gpt-3.5-turbo"],
                    "prefer_cheap": True,
                    "max_cost_per_request": 0.5
                },
                {
                    "name": "planfile_docs",
                    "pattern": {
                        "task_type": "docs"
                    },
                    "models": ["anthropic/claude-haiku-4.5"],
                    "prefer_cheap": True,
                    "max_cost_per_request": 0.3
                },
                {
                    "name": "planfile_review",
                    "pattern": {
                        "task_type": "review"
                    },
                    "models": ["anthropic/claude-sonnet-4"],
                    "max_cost_per_request": 1.0
                }
            ]
        },
        "budget": {
            "daily_limit": 50.0,
            "monthly_limit": 500.0,
            "per_project_limits": {
                "planfile": {
                    "daily": 20.0,
                    "monthly": 200.0
                }
            }
        },
        "cache": {
            "enabled": True,
            "strategy_similarity_threshold": 0.8,
            "task_cache_ttl": 3600,
            "strategy_cache_ttl": 86400
        },
        "analytics": {
            "track_project_metrics": True,
            "track_model_performance": True,
            "optimize_routing": True
        }
    }

    # Save configuration
    with open("proxy-planfile-config.yaml", "w") as f:
        import yaml
        yaml.dump(config, f, default_flow_style=False, indent=2)

    print("\n✅ Proxy configuration saved to: proxy-planfile-config.yaml")

async def example_budget_tracking():
    """Example: Budget tracking with proxy."""
    print("\n\n" + "=" * 60)
    print("Budget Tracking Example")
    print("=" * 60)

    proxy = ProxyClient()

    # Get current budget status
    stats = await proxy.get_usage_stats()

    print("\nCurrent Budget Status:")
    print(f"  Daily Usage: ${stats.get('daily_usage', 0):.2f} / ${stats.get('daily_limit', 50):.2f}")
    print(f"  Monthly Usage: ${stats.get('monthly_usage', 0):.2f} / ${stats.get('monthly_limit', 500):.2f}")
    print(f"  Project (planfile): ${stats.get('project_usage', {}).get('planfile', 0):.2f}")

    # Simulate budget-aware routing
    print("\nBudget-Aware Routing Decisions:")

    scenarios = [
        {"daily_remaining": 10.0, "task": "critical_refactor", "decision": "Use premium model (within budget)"},
        {"daily_remaining": 1.0, "task": "standard_refactor", "decision": "Use balanced model"},
        {"daily_remaining": 0.5, "task": "docs", "decision": "Use cheap model"},
        {"daily_remaining": 0.1, "task": "any", "decision": "Queue for tomorrow or use local model"}
    ]

    for scenario in scenarios:
        remaining = scenario["daily_remaining"]
        task = scenario["task"]
        decision = scenario["decision"]

        print(f"\n  Daily remaining: ${remaining:.2f}")
        print(f"  Task: {task}")
        print(f"  Decision: {decision}")

if __name__ == "__main__":
    print("Planfile + Proxy Integration Examples")

    # Run examples
    asyncio.run(example_strategy_generation_with_proxy())
    create_proxy_config_example()
    asyncio.run(example_budget_tracking())

    print("\n\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("""
    Proxy integration provides:
    1. Smart model routing based on task complexity
    2. Cost optimization without sacrificing quality
    3. Budget tracking and enforcement
    4. Caching to avoid duplicate work
    5. Fallback chains for reliability
    
    This allows planfile to be both powerful AND cost-effective!
    """)
