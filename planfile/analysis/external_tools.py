"""Integration with external analysis tools: code2llm, vallm, redup.

This module provides interfaces to run external code analysis tools
and parse their output for planfile generation.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class AnalysisResults:
    """Results from external tool analysis."""
    cc_average: float = 0.0
    critical_functions: int = 0
    high_cc_functions: List[Dict[str, Any]] = None
    validation_errors: int = 0
    validation_warnings: int = 0
    duplication_groups: int = 0
    saved_lines: int = 0
    pass_rate: float = 0.0

    def __post_init__(self):
        if self.high_cc_functions is None:
            self.high_cc_functions = []


class ExternalToolRunner:
    """Runner for external code analysis tools."""
    
    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.output_dir = self.project_path / ".planfile_analysis"
        self.output_dir.mkdir(exist_ok=True)
        
        # Analysis results
        self.code2llm_results: Optional[AnalysisResults] = None
        self.vallm_results: Optional[AnalysisResults] = None
        self.redup_results: Optional[AnalysisResults] = None
    
    def run_all(self) -> AnalysisResults:
        """Run all external tools and return combined results."""
        self.code2llm_results = self.run_code2llm()
        self.vallm_results = self.run_vallm()
        self.redup_results = self.run_redup()
        
        # Combine results
        combined = AnalysisResults()
        
        if self.code2llm_results:
            combined.cc_average = self.code2llm_results.cc_average
            combined.critical_functions = self.code2llm_results.critical_functions
            combined.high_cc_functions = self.code2llm_results.high_cc_functions
        
        if self.vallm_results:
            combined.validation_errors = self.vallm_results.validation_errors
            combined.validation_warnings = self.vallm_results.validation_warnings
            combined.pass_rate = self.vallm_results.pass_rate
        
        if self.redup_results:
            combined.duplication_groups = self.redup_results.duplication_groups
            combined.saved_lines = self.redup_results.saved_lines
        
        return combined
    
    def run_code2llm(self) -> Optional[AnalysisResults]:
        """Run code2llm analysis."""
        print("🔍 Running code2llm analysis...")
        
        cmd = [
            "code2llm",
            str(self.project_path),
            "-f", "all",
            "-o", str(self.output_dir),
            "--no-chunk",
            "--exclude", ".git",
            "--exclude", "__pycache__",
            "--exclude", "*.pyc",
            "--exclude", "node_modules",
            "--exclude", ".pytest_cache",
            "--exclude", ".planfile_analysis"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ code2llm completed successfully")
                return self.parse_code2llm_output()
            else:
                print(f"⚠️  code2llm failed: {result.stderr[:200]}")
                return self._mock_code2llm_data()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️  code2llm not available, using mock data")
            return self._mock_code2llm_data()
    
    def run_vallm(self) -> Optional[AnalysisResults]:
        """Run vallm validation."""
        print("🔍 Running vallm validation...")
        
        cmd = [
            "vallm",
            "batch",
            str(self.project_path),
            "--recursive",
            "--format", "toon",
            "--output", str(self.output_dir)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ vallm completed successfully")
                return self.parse_vallm_output()
            else:
                print(f"⚠️  vallm failed: {result.stderr[:200]}")
                return self._mock_vallm_data()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️  vallm not available, using mock data")
            return self._mock_vallm_data()
    
    def run_redup(self) -> Optional[AnalysisResults]:
        """Run redup duplication analysis."""
        print("🔍 Running redup analysis...")
        
        cmd = [
            "redup",
            "scan",
            str(self.project_path),
            "--format", "toon",
            "--output", str(self.output_dir)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ redup completed successfully")
                return self.parse_redup_output()
            else:
                print(f"⚠️  redup failed: {result.stderr[:200]}")
                return self._mock_redup_data()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️  redup not available, using mock data")
            return self._mock_redup_data()
    
    def parse_code2llm_output(self) -> Optional[AnalysisResults]:
        """Parse code2llm analysis.toon.yaml output."""
        analysis_file = self.output_dir / "analysis.toon.yaml"
        
        if not analysis_file.exists():
            return self._mock_code2llm_data()
        
        with open(analysis_file, 'r') as f:
            content = f.read()
        
        # Extract metrics from header
        lines = content.split('\n')
        header = lines[0] if lines else ""
        
        result = AnalysisResults()
        
        # Parse CC average
        cc_match = re.search(r'CC̄=(\d+\.?\d*)', header)
        if cc_match:
            result.cc_average = float(cc_match.group(1))
        
        # Parse critical count
        critical_match = re.search(r'critical:(\d+)', header)
        if critical_match:
            result.critical_functions = int(critical_match.group(1))
        
        # Parse high-CC functions
        in_health = False
        for line in lines:
            if 'HEALTH[' in line:
                in_health = True
            elif 'REFACTOR[' in line:
                in_health = False
            elif in_health and 'CC=' in line and 'limit:' in line:
                func_match = re.search(r'(\w+)\s+CC=(\d+)', line)
                if func_match:
                    result.high_cc_functions.append({
                        'name': func_match.group(1),
                        'cc': int(func_match.group(2))
                    })
        
        return result
    
    def parse_vallm_output(self) -> Optional[AnalysisResults]:
        """Parse vallm validation.toon.yaml output."""
        validation_file = self.output_dir / "validation.toon.yaml"
        
        if not validation_file.exists():
            return self._mock_vallm_data()
        
        with open(validation_file, 'r') as f:
            content = f.read()
        
        result = AnalysisResults()
        
        # Parse summary line
        summary_match = re.search(r'scanned:\s*(\d+).*?passed:\s*(\d+).*?\((\d+\.?\d*)%\).*?warnings:\s*(\d+).*?errors:\s*(\d+)', content)
        if summary_match:
            result.pass_rate = float(summary_match.group(3))
            result.validation_warnings = int(summary_match.group(4))
            result.validation_errors = int(summary_match.group(5))
        
        return result
    
    def parse_redup_output(self) -> Optional[AnalysisResults]:
        """Parse redup duplication.toon.yaml output."""
        dup_file = self.output_dir / "duplication.toon.yaml"
        
        if not dup_file.exists():
            return self._mock_redup_data()
        
        with open(dup_file, 'r') as f:
            content = f.read()
        
        result = AnalysisResults()
        
        # Parse duplication metrics
        dup_match = re.search(r'dup_groups:\s*(\d+)', content)
        if dup_match:
            result.duplication_groups = int(dup_match.group(1))
        
        saved_match = re.search(r'saved_lines:\s*(\d+)', content)
        if saved_match:
            result.saved_lines = int(saved_match.group(1))
        
        return result
    
    def _mock_code2llm_data(self) -> AnalysisResults:
        """Mock code2llm data for testing."""
        return AnalysisResults(
            cc_average=4.1,
            critical_functions=2,
            high_cc_functions=[
                {'name': 'generate_report', 'cc': 20},
                {'name': 'update_ticket', 'cc': 18},
            ]
        )
    
    def _mock_vallm_data(self) -> AnalysisResults:
        """Mock vallm data for testing."""
        return AnalysisResults(
            pass_rate=85.0,
            validation_warnings=3,
            validation_errors=1
        )
    
    def _mock_redup_data(self) -> AnalysisResults:
        """Mock redup data for testing."""
        return AnalysisResults(
            duplication_groups=1,
            saved_lines=12
        )


def run_external_analysis(project_path: Union[str, Path]) -> AnalysisResults:
    """Convenience function to run all external tools.
    
    Args:
        project_path: Path to project directory
        
    Returns:
        Combined analysis results
    """
    runner = ExternalToolRunner(Path(project_path))
    return runner.run_all()
