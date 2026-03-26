#!/usr/bin/env python3
"""
Example: Using LiteLLM adapters with planfile CLI commands.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
import tempfile
import yaml
import json

# Add planfile to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from planfile.llm.adapters import (
    LiteLLMAdapter,
    OpenRouterAdapter,
    LocalLLMAdapter
)


class PlanfileLLMIntegration:
    """Integration of LLM adapters with planfile CLI."""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="planfile-llm-test-"))
        print(f"📁 Working in temporary directory: {self.temp_dir}")
    
    def cleanup(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
        print(f"🧹 Cleaned up temporary directory")
    
    async def generate_strategy_with_adapter(
        self, 
        adapter, 
        model: str,
        project_info: dict
    ) -> Path:
        """Generate a strategy using an LLM adapter."""
        print(f"\n🤖 Generating strategy with {adapter.__class__.__name__} - {model}")
        
        # Create prompt
        prompt = f"""
        Generate a comprehensive software development strategy in YAML format for:
        
        Project: {project_info['name']}
        Type: {project_info['type']}
        Domain: {project_info['domain']}
        Goal: {project_info['goal']}
        
        Requirements:
        - Create {project_info.get('sprints', 3)} sprints
        - Include detailed task patterns
        - Define quality gates with metrics
        - Add resource estimates
        - Use proper YAML structure
        
        Output ONLY the YAML strategy without markdown formatting.
        """
        
        # Generate using adapter
        result = await adapter.test_strategy_generation(prompt, model)
        
        if not result.success:
            raise Exception(f"Generation failed: {result.error}")
        
        # Clean up the response
        yaml_content = result.response
        
        # Remove markdown if present
        if "```yaml" in yaml_content:
            yaml_content = yaml_content.split("```yaml")[1].split("```")[0]
        elif "```" in yaml_content:
            yaml_content = yaml_content.split("```")[1]
        
        # Validate YAML
        try:
            data = yaml.safe_load(yaml_content)
            print(f"✅ Generated valid YAML ({result.response_time:.2f}s)")
        except yaml.YAMLError as e:
            print(f"⚠️  Warning: Generated YAML may have issues: {e}")
        
        # Save strategy file
        strategy_file = self.temp_dir / f"strategy-{model.replace('/', '-')}.yaml"
        with open(strategy_file, 'w') as f:
            f.write(yaml_content)
        
        print(f"💾 Strategy saved to: {strategy_file.name}")
        return strategy_file
    
    def run_planfile_command(self, cmd: list, description: str) -> bool:
        """Run a planfile CLI command."""
        print(f"\n🔧 {description}")
        print(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.temp_dir
            )
            
            if result.stdout:
                print("Output:")
                print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
            
            if result.stderr:
                print("Errors:")
                print(result.stderr[:500] + "..." if len(result.stderr) > 500 else result.stderr)
            
            if result.returncode == 0:
                print("✅ Command succeeded")
                return True
            else:
                print(f"❌ Command failed with code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print("⏰ Command timed out")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    async def demonstrate_workflow(self):
        """Demonstrate complete workflow with different LLMs."""
        print("=" * 60)
        print("PLANFILE + LLM ADAPTERS WORKFLOW DEMONSTRATION")
        print("=" * 60)
        
        # Project to generate strategy for
        project_info = {
            "name": "AI-Powered Analytics Dashboard",
            "type": "data-analytics",
            "domain": "business-intelligence",
            "goal": "Build real-time analytics dashboard with AI insights",
            "sprints": 3
        }
        
        # Test adapters
        adapters_to_test = []
        
        # OpenRouter adapter
        if os.environ.get('OPENROUTER_API_KEY'):
            adapters_to_test.append(
                ("OpenRouter", OpenRouterAdapter({
                    'api_key': os.environ.get('OPENROUTER_API_KEY')
                }), "anthropic/claude-3-haiku")
            )
        
        # LiteLLM adapter (if OpenAI key available)
        if os.environ.get('OPENAI_API_KEY'):
            adapters_to_test.append(
                ("LiteLLM", LiteLLMAdapter({
                    'api_key': os.environ.get('OPENAI_API_KEY')
                })), "gpt-3.5-turbo")
            )
        
        # Local adapter (Ollama)
        try:
            import httpx
            # Check if Ollama is running
            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                adapters_to_test.append(
                    ("Ollama", LocalLLMAdapter({
                        'base_url': 'http://localhost:11434',
                        'provider': 'ollama'
                    })), "llama2")
                )
        except:
            print("⚠️  Ollama not available (run 'ollama serve' to enable)")
        
        if not adapters_to_test:
            print("\n❌ No adapters available. Please configure API keys:")
            print("  export OPENROUTER_API_KEY=your_key")
            print("  export OPENAI_API_KEY=your_key")
            print("  # Or start Ollama: ollama serve")
            return
        
        # Generate and test strategies
        for adapter_name, adapter, model in adapters_to_test:
            print(f"\n{'='*60}")
            print(f"TESTING WITH: {adapter_name}")
            print(f"{'='*60}")
            
            try:
                # Generate strategy
                strategy_file = await self.generate_strategy_with_adapter(
                    adapter, model, project_info
                )
                
                # Validate strategy
                self.run_planfile_command(
                    [sys.executable, "-m", "planfile.cli.commands", "validate", str(strategy_file)],
                    f"Validating {strategy_file.name}"
                )
                
                # Apply strategy (dry run)
                self.run_planfile_command(
                    [sys.executable, "-m", "planfile.cli.commands", "apply",
                     str(strategy_file), ".", "--backend", "generic", "--dry-run"],
                    f"Applying {strategy_file.name} (dry run)"
                )
                
                # Review strategy
                self.run_planfile_command(
                    [sys.executable, "-m", "planfile.cli.commands", "review",
                     str(strategy_file), ".", "--backend", "generic"],
                    f"Reviewing {strategy_file.name}"
                )
                
            except Exception as e:
                print(f"❌ Failed to test {adapter_name}: {e}")
        
        # Compare generated strategies
        print(f"\n{'='*60}")
        print("STRATEGY COMPARISON")
        print(f"{'='*60}")
        
        strategies = list(self.temp_dir.glob("strategy-*.yaml"))
        
        if len(strategies) > 1:
            comparison = {
                'strategies': {},
                'metrics': {}
            }
            
            for strategy_file in strategies:
                with open(strategy_file, 'r') as f:
                    content = f.read()
                    data = yaml.safe_load(content)
                
                adapter_name = strategy_file.stem.replace("strategy-", "").replace("-", " ")
                
                comparison['strategies'][adapter_name] = {
                    'sprints': len(data.get('sprints', [])),
                    'quality_gates': len(data.get('quality_gates', [])),
                    'has_tasks': 'tasks' in data,
                    'file_size': len(content)
                }
            
            # Save comparison
            comparison_file = self.temp_dir / "strategy-comparison.json"
            with open(comparison_file, 'w') as f:
                json.dump(comparison, f, indent=2)
            
            print("\n📊 Strategy Comparison:")
            for adapter, stats in comparison['strategies'].items():
                print(f"\n{adapter}:")
                print(f"  Sprints: {stats['sprints']}")
                print(f"  Quality Gates: {stats['quality_gates']}")
                print(f"  Has Tasks: {stats['has_tasks']}")
                print(f"  Size: {stats['file_size']} chars")
        
        # Copy results to current directory
        results_dir = Path("llm-test-results")
        results_dir.mkdir(exist_ok=True)
        
        import shutil
        for file in self.temp_dir.glob("*"):
            shutil.copy2(file, results_dir)
        
        print(f"\n💾 All results saved to: {results_dir}")


async def main():
    """Main demonstration."""
    demo = PlanfileLLMIntegration()
    
    try:
        await demo.demonstrate_workflow()
    finally:
        demo.cleanup()
    
    print("\n✅ Demonstration complete!")


if __name__ == "__main__":
    asyncio.run(main())
