#!/usr/bin/env python3
"""Example of using planfile as a standalone package."""

from pathlib import Path
from planfile import Strategy, StrategyExecutor, create_openai_client, execute_strategy

def example_1_basic_usage():
    """Basic usage without LLM client."""
    print("=== Example 1: Basic Usage (Mock Execution) ===\n")
    
    # Create a simple strategy
    strategy_data = {
        "name": "Code Cleanup",
        "goal": "Improve code quality",
        "sprints": [
            {
                "id": 1,
                "name": "Refactoring Sprint",
                "objectives": ["Extract methods", "Add tests"],
                "tasks": [
                    {
                        "name": "Extract Complex Methods",
                        "description": "Extract methods with CC > 10",
                        "type": "refactor",
                        "model_hints": "balanced"
                    },
                    {
                        "name": "Add Unit Tests",
                        "description": "Write tests for extracted methods",
                        "type": "test",
                        "model_hints": "cheap"
                    }
                ]
            }
        ]
    }
    
    # Load strategy
    strategy = Strategy.load_flexible(strategy_data)
    print(f"Loaded strategy: {strategy.name}")
    print(f"Sprints: {len(strategy.sprints)}")
    print(f"Tasks: {len(strategy.get_task_patterns())}\n")
    
    # Execute with mock client (dry run)
    executor = StrategyExecutor()
    results = executor.execute_strategy(strategy, dry_run=True)
    
    print("Results:")
    for result in results:
        print(f"  - {result.task_name}: {result.status} (model: {result.model_used})")


def example_2_with_openai():
    """Example with OpenAI client."""
    print("\n=== Example 2: With OpenAI Client ===\n")
    
    # You need to set your API key
    api_key = "your-openai-api-key-here"
    
    if api_key == "your-openai-api-key-here":
        print("Skipping: Set your OpenAI API key to run this example")
        return
    
    try:
        # Create client
        client = create_openai_client(api_key, model="gpt-4o-mini")
        
        # Execute strategy
        results = execute_strategy(
            strategy_path="examples/strategy_simple_v2.yaml",
            project_path=".",
            client=client,
            dry_run=False  # Set to True to actually execute
        )
        
        print("Execution results:")
        for result in results:
            print(f"\nTask: {result.task_name}")
            print(f"Status: {result.status}")
            print(f"Model: {result.model_used}")
            if result.response:
                print(f"Response: {result.response[:200]}...")
                
    except Exception as e:
        print(f"Error: {e}")


def example_3_custom_client():
    """Example with custom LLM client."""
    print("\n=== Example 3: Custom Client ===\n")
    
    from planfile import LLMClient
    
    # Define your own client function
    def my_llm_client(messages, model):
        """Custom client that returns a simple response."""
        user_msg = messages[0]["content"] if messages else ""
        return f"Custom response for: {user_msg[:50]}... (using model: {model})"
    
    # Create client
    client = LLMClient(my_llm_client)
    
    # Create executor with custom client
    executor = StrategyExecutor(client=client)
    
    # Load and execute strategy
    strategy = Strategy.load_flexible("examples/strategy_simple_v2.yaml")
    results = executor.execute_strategy(strategy, sprint_filter=1)
    
    print("Custom client results:")
    for result in results:
        print(f"\n{result.task_name}:")
        print(f"  {result.response}")


def example_4_model_configuration():
    """Example of custom model configuration."""
    print("\n=== Example 4: Custom Model Configuration ===\n")
    
    # Custom configuration
    config = {
        'model_map': {
            'local': 'ollama/llama2',
            'cheap': 'openrouter/mistral-7b',
            'balanced': 'anthropic/claude-sonnet',
            'premium': 'openai/gpt-4'
        }
    }
    
    executor = StrategyExecutor(config=config)
    
    # Test model selection
    from planfile import Task
    
    tasks = [
        Task(name="Simple task", description="...", model_hints="free"),
        Task(name="Complex task", description="...", model_hints="premium"),
        Task(name="Default task", description="...", model_hints={})
    ]
    
    print("Model selection with custom config:")
    for task in tasks:
        model = executor._select_model(task)
        print(f"  {task.name}: {model}")


if __name__ == "__main__":
    print("Planfile Standalone Examples\n")
    print("=" * 50)
    
    # Run examples
    example_1_basic_usage()
    example_2_with_openai()
    example_3_custom_client()
    example_4_model_configuration()
    
    print("\n" + "=" * 50)
    print("\nTo use with real LLM:")
    print("1. Install required packages: pip install openai litellm")
    print("2. Set your API key")
    print("3. Use create_openai_client() or create_litellm_client()")
    print("4. Execute strategy with client parameter")
