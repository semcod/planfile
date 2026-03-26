# Planfile - Standalone Usage

Planfile can now be used as a standalone package without LLX dependencies. This makes it easier to integrate into any project.

## Installation

```bash
# Install base package
pip install planfile

# Install with LLM providers
pip install planfile[openai]  # For OpenAI
pip install planfile[litellm]  # For LiteLLM (supports many providers)
pip install planfile[all]  # All optional dependencies
```

## Quick Start

### 1. Basic Usage (Mock Execution)

```python
from planfile import Strategy, StrategyExecutor

# Create or load a strategy
strategy = Strategy.load_flexible("my_strategy.yaml")

# Execute (mock mode - no LLM calls)
executor = StrategyExecutor()
results = executor.execute_strategy(strategy, dry_run=True)

for result in results:
    print(f"{result.task_name}: {result.status}")
```

### 2. With OpenAI

```python
from planfile import Strategy, create_openai_client, execute_strategy

# Create client
client = create_openai_client(api_key="your-api-key")

# Execute strategy
results = execute_strategy(
    "strategy.yaml",
    project_path=".",
    client=client
)
```

### 3. With LiteLLM (Multiple Providers)

```python
from planfile import Strategy, create_litellm_client, execute_strategy

# Supports OpenAI, Anthropic, Cohere, etc.
client = create_litellm_client(api_key="your-api-key")

results = execute_strategy(
    "strategy.yaml",
    project_path=".",
    client=client,
    model_override="anthropic/claude-3-sonnet"
)
```

### 4. Custom LLM Client

```python
from planfile import Strategy, LLMClient, StrategyExecutor

def my_client(messages, model):
    """Your custom LLM implementation."""
    # Call your LLM here
    return "LLM response"

client = LLMClient(my_client)
executor = StrategyExecutor(client=client)
results = executor.execute_strategy(strategy)
```

## Strategy Format

Planfile now supports a simplified V2 format:

```yaml
name: "My Strategy"
goal: "Improve code quality"

sprints:
  - id: 1
    name: "Refactoring Sprint"
    objectives: ["Extract methods", "Add tests"]
    tasks:
      - name: "Extract Complex Methods"
        description: "Extract methods with CC > 10"
        type: "refactor"
        model_hints: "balanced"  # Simple string!
      
      - name: "Add Unit Tests"
        description: "Write tests for refactored code"
        type: "test"
        model_hints: "cheap"  # Use free/cheap models
```

## Key Improvements

### 1. **Simplified Format**
- Tasks are embedded directly in sprints
- No separate task patterns section
- Model hints can be simple strings

### 2. **Flexible Validation**
- Added `refactor` and `test` task types
- `free` alias for `cheap` models
- String criteria auto-convert to lists
- Sensible defaults for missing fields

### 3. **Standalone Execution**
- No LLX dependency required
- Works with any LLM provider
- Mock mode for testing
- Custom client support

### 4. **Better Error Handling**
- Graceful fallbacks
- Clear error messages
- Execution time tracking

## Model Selection

Planfile automatically selects models based on:

1. **Task Hints**: `model_hints: "cheap"` or `"balanced"` or `"premium"`
2. **Task Type**: 
   - `chore`, `documentation` → cheap models
   - `refactor`, `feature` → balanced models
   - Critical tasks → premium models
3. **Custom Configuration**:

```python
config = {
    'model_map': {
        'local': 'ollama/llama2',
        'cheap': 'openrouter/mistral-7b',
        'balanced': 'anthropic/claude-sonnet',
        'premium': 'openai/gpt-4'
    }
}

executor = StrategyExecutor(config=config)
```

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI
from planfile import Strategy, create_openai_client, StrategyExecutor

app = FastAPI()
client = create_openai_client(api_key="your-key")
executor = StrategyExecutor(client=client)

@app.post("/execute-strategy")
async def execute(strategy_file: str):
    strategy = Strategy.load_flexible(strategy_file)
    results = executor.execute_strategy(strategy)
    return {"results": results}
```

### CLI Integration

```python
import click
from planfile import Strategy, create_litellm_client, execute_strategy

@click.command()
@click.option('--strategy', required=True)
@click.option('--api-key', required=True)
@click.option('--dry-run', is_flag=True)
def run(strategy, api_key, dry_run):
    client = create_litellm_client(api_key=api_key)
    results = execute_strategy(
        strategy, 
        client=client, 
        dry_run=dry_run
    )
    for r in results:
        click.echo(f"{r.task_name}: {r.status}")

if __name__ == "__main__":
    run()
```

## Migration from LLX

If you were using LLX's planfile:

1. **Install standalone planfile**:
   ```bash
   pip install planfile[litellm]
   ```

2. **Update imports**:
   ```python
   # Before
   from llx.planfile import execute_strategy
   
   # After
   from planfile import execute_strategy
   ```

3. **Add LLM client**:
   ```python
   from planfile import create_litellm_client
   
   client = create_litellm_client(api_key="your-key")
   results = execute_strategy("strategy.yaml", client=client)
   ```

## Examples

See `example_standalone.py` for complete examples including:
- Basic usage with mock execution
- OpenAI integration
- Custom client implementation
- Model configuration

## Testing

```bash
# Run basic tests
python3 example_standalone.py

# Test with your strategy
python3 -c "
from planfile import execute_strategy
results = execute_strategy('my_strategy.yaml', dry_run=True)
print(f'Executed {len(results)} tasks')
"
```

## Benefits of Standalone Planfile

1. **Simpler Setup**: No need to install LLX
2. **Flexible**: Works with any LLM provider
3. **Lighter**: Fewer dependencies
4. **Easier Integration**: Drop-in to any Python project
5. **Better Testing**: Mock mode for unit tests
6. **Customizable**: Use your own LLM implementation

## Next Steps

1. Try the examples: `python3 example_standalone.py`
2. Create your first strategy: See `examples/strategy_simple_v2.yaml`
3. Integrate with your LLM provider
4. Build your custom workflow on top of planfile!
