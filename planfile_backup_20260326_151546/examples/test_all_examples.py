#!/usr/bin/env python3
"""
Test runner for all planfile examples
Validates generated code and strategies using LLX + OpenRouter free LLM
"""

import os
import sys
import json
import yaml
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio
import aiohttp
from datetime import datetime

class ExampleTester:
    """Test runner for planfile examples."""
    
    def __init__(self):
        self.results = []
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.free_model = "meta-llama/llama-3.2-3b-instruct:free"  # Free model on OpenRouter
        
    async def test_all_examples(self):
        """Test all examples in the ecosystem directory."""
        print("=" * 60)
        print("Testing All Planfile Examples")
        print("=" * 60)
        
        examples_dir = Path("planfile/examples/ecosystem")
        if not examples_dir.exists():
            examples_dir = Path("planfile/examples")
        
        # Test each example
        for example_file in examples_dir.glob("*"):
            if example_file.suffix in ['.py', '.sh']:
                print(f"\n{'='*40}")
                print(f"Testing: {example_file.name}")
                print('='*40)
                
                try:
                    if example_file.suffix == '.py':
                        await self._test_python_example(example_file)
                    elif example_file.suffix == '.sh':
                        await self._test_shell_example(example_file)
                except Exception as e:
                    print(f"❌ Error testing {example_file}: {e}")
                    self.results.append({
                        "example": example_file.name,
                        "status": "error",
                        "error": str(e)
                    })
        
        # Print summary
        self._print_summary()
    
    async def _test_python_example(self, example_path: Path):
        """Test a Python example."""
        print(f"\n1. Running Python example: {example_path.name}")
        
        # Create a test directory
        with tempfile.TemporaryDirectory() as test_dir:
            test_dir_path = Path(test_dir)
            
            # Run the example
            result = subprocess.run(
                [sys.executable, str(example_path)],
                cwd=test_dir_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"❌ Example failed to run")
                print(f"Error: {result.stderr}")
                return
            
            print("✅ Example ran successfully")
            
            # Check for generated files
            generated_files = list(test_dir_path.rglob("*"))
            generated_files = [f for f in generated_files if f.is_file()]
            
            print(f"\n2. Found {len(generated_files)} generated files:")
            
            # Validate generated files
            validations = []
            for file_path in generated_files:
                rel_path = file_path.relative_to(test_dir_path)
                print(f"  - {rel_path}")
                
                validation = await self._validate_file(file_path)
                validations.append({
                    "file": str(rel_path),
                    "validation": validation
                })
            
            # Store results
            self.results.append({
                "example": example_path.name,
                "status": "success",
                "generated_files": len(generated_files),
                "validations": validations
            })
    
    async def _test_shell_example(self, example_path: Path):
        """Test a shell example."""
        print(f"\n1. Running shell example: {example_path.name}")
        
        # Create a test directory
        with tempfile.TemporaryDirectory() as test_dir:
            test_dir_path = Path(test_dir)
            
            # Make script executable
            os.chmod(example_path, 0o755)
            
            # Run the example
            result = subprocess.run(
                [str(example_path)],
                cwd=test_dir_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"❌ Example failed to run")
                print(f"Error: {result.stderr}")
                return
            
            print("✅ Example ran successfully")
            print(f"Output:\n{result.stdout[:500]}...")
            
            # Check for generated files
            generated_files = list(test_dir_path.rglob("*"))
            generated_files = [f for f in generated_files if f.is_file()]
            
            print(f"\n2. Found {len(generated_files)} generated files:")
            
            # Validate key files
            for file_path in generated_files:
                rel_path = file_path.relative_to(test_dir_path)
                print(f"  - {rel_path}")
                
                if rel_path.suffix in ['.yaml', '.yml', '.py', '.json']:
                    validation = await self._validate_file(file_path)
                    print(f"    Validation: {validation['status']}")
            
            # Store results
            self.results.append({
                "example": example_path.name,
                "status": "success",
                "generated_files": len(generated_files)
            })
    
    async def _validate_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate a generated file using LLM."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            if file_path.suffix in ['.yaml', '.yml']:
                return await self._validate_yaml(content, file_path.name)
            elif file_path.suffix == '.py':
                return await self._validate_python(content, file_path.name)
            elif file_path.suffix == '.json':
                return await self._validate_json(content, file_path.name)
            else:
                return {"status": "skipped", "reason": "Unsupported file type"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _validate_yaml(self, content: str, filename: str) -> Dict[str, Any]:
        """Validate YAML content."""
        # First check if it's valid YAML
        try:
            yaml_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return {"status": "invalid", "error": f"Invalid YAML: {e}"}
        
        # Use LLM to validate strategy structure if it's a strategy file
        if 'strategy' in filename.lower() or any(key in content for key in ['sprints:', 'tasks:', 'quality_gates:']):
            return await self._validate_strategy_with_llm(yaml_data, content)
        
        return {"status": "valid", "type": "yaml"}
    
    async def _validate_python(self, content: str, filename: str) -> Dict[str, Any]:
        """Validate Python code."""
        # Check syntax
        try:
            compile(content, filename, 'exec')
        except SyntaxError as e:
            return {"status": "invalid", "error": f"Syntax error: {e}"}
        
        # Use LLM for code quality check
        return await self._validate_code_with_llm(content, filename, "python")
    
    async def _validate_json(self, content: str, filename: str) -> Dict[str, Any]:
        """Validate JSON content."""
        try:
            json_data = json.loads(content)
            return {"status": "valid", "type": "json", "keys": len(json_data) if isinstance(json_data, dict) else 0}
        except json.JSONDecodeError as e:
            return {"status": "invalid", "error": f"Invalid JSON: {e}"}
    
    async def _validate_strategy_with_llm(self, yaml_data: Dict, content: str) -> Dict[str, Any]:
        """Validate strategy YAML using LLM."""
        if not self.openrouter_api_key:
            return {"status": "skipped", "reason": "No OpenRouter API key"}
        
        prompt = f"""
        Validate this strategy YAML file for a refactoring project:
        
        ```yaml
        {content[:1000]}...
        ```
        
        Check for:
        1. Valid structure (sprints, tasks, quality_gates)
        2. Logical task priorities
        3. Realistic time estimates
        4. Proper quality gates
        
        Respond with JSON: {{"valid": true/false, "issues": ["list of issues"], "suggestions": ["list of suggestions"]}}
        """
        
        try:
            response = await self._call_llm(prompt)
            llm_result = json.loads(response)
            
            return {
                "status": "valid" if llm_result.get("valid") else "needs_improvement",
                "issues": llm_result.get("issues", []),
                "suggestions": llm_result.get("suggestions", [])
            }
        except Exception as e:
            return {"status": "error", "error": f"LLM validation failed: {e}"}
    
    async def _validate_code_with_llm(self, content: str, filename: str, language: str) -> Dict[str, Any]:
        """Validate code using LLM."""
        if not self.openrouter_api_key:
            return {"status": "skipped", "reason": "No OpenRouter API key"}
        
        prompt = f"""
        Review this {language} code from {filename}:
        
        ```{language}
        {content[:1500]}...
        ```
        
        Check for:
        1. Code quality and best practices
        2. Potential bugs or issues
        3. Security vulnerabilities
        4. Performance considerations
        
        Respond with JSON: {{"quality": "excellent/good/fair/poor", "issues": [], "suggestions": []}}
        """
        
        try:
            response = await self._call_llm(prompt)
            llm_result = json.loads(response)
            
            return {
                "status": "validated",
                "quality": llm_result.get("quality", "unknown"),
                "issues": llm_result.get("issues", []),
                "suggestions": llm_result.get("suggestions", [])
            }
        except Exception as e:
            return {"status": "error", "error": f"LLM validation failed: {e}"}
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM via OpenRouter."""
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.free_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    raise Exception(f"API error: {response.status}")
                
                result = await response.json()
                return result["choices"][0]["message"]["content"]
    
    def _print_summary(self):
        """Print test summary."""
        print("\n\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "error")
        
        print(f"\nTotal examples: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        # Detailed results
        print("\n\nDetailed Results:")
        for result in self.results:
            print(f"\n{result['example']}:")
            print(f"  Status: {result['status']}")
            
            if result["status"] == "success":
                if "generated_files" in result:
                    print(f"  Generated files: {result['generated_files']}")
                
                if "validations" in result:
                    for val in result["validations"]:
                        print(f"  {val['file']}: {val['validation']['status']}")
                        if val['validation'].get("issues"):
                            print(f"    Issues: {', '.join(val['validation']['issues'][:2])}")
            else:
                print(f"  Error: {result.get('error', 'Unknown error')}")
        
        # Save results
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed
            },
            "results": self.results
        }
        
        with open("test-results.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: test-results.json")

async def main():
    """Main entry point."""
    # Check for OpenRouter API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  Warning: OPENROUTER_API_KEY not set")
        print("   LLM validation will be skipped")
        print("   Get a free key at: https://openrouter.ai/keys")
        print("\n   To set: export OPENROUTER_API_KEY=your_key_here")
        print()
    
    # Run tests
    tester = ExampleTester()
    await tester.test_all_examples()

if __name__ == "__main__":
    asyncio.run(main())
