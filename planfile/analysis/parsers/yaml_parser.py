import yaml
from pathlib import Path
from typing import Tuple, List, Any

from ... import models
from ..models import ExtractedIssue, ExtractedMetric, ExtractedTask
from .text_parser import analyze_text
from .toon_parser import analyze_toon

def extract_from_yaml_structure(data: Any, path: str, parent_key: str = "") -> List[ExtractedIssue]:
    """Extract issues from YAML structure."""
    issues = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            
            # Look for common issue indicators
            if isinstance(value, str):
                if any(keyword in value.lower() for keyword in ['error', 'fail', 'bug', 'issue']):
                    issues.append(ExtractedIssue(
                        title=f"Issue in {full_key}",
                        description=value,
                        priority="medium",
                        category="bug",
                        file_path=path
                    ))
            
            # Recurse
            issues.extend(extract_from_yaml_structure(value, path, full_key))
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            issues.extend(extract_from_yaml_structure(item, path, f"{parent_key}[{i}]"))
    
    return issues

def analyze_yaml(file_path: Path) -> Tuple[List[ExtractedIssue], List[ExtractedMetric], List[ExtractedTask]]:
    """Analyze YAML file with better error handling."""
    issues = []
    metrics = []
    tasks = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        try:
            data = yaml.safe_load(content)
            issues.extend(extract_from_yaml_structure(data, str(file_path)))
            
        except yaml.YAMLError as e:
            if 'toon' in str(file_path):
                return analyze_toon(file_path)
            
            issues.append(ExtractedIssue(
                title=f"Fix YAML syntax in {file_path.name}",
                description=f"YAML parsing error: {str(e)}",
                priority="high",
                category="bug",
                file_path=str(file_path),
                effort_estimate="1h",
                tags=["yaml", "syntax"]
            ))
        
        text_issues, text_metrics, text_tasks = analyze_text(file_path)
        issues.extend(text_issues)
        metrics.extend(text_metrics)
        tasks.extend(text_tasks)
        
    except Exception as e:
        issues.append(ExtractedIssue(
            title=f"Failed to parse {file_path.name}",
            description=f"File error: {str(e)}",
            priority="high",
            category="bug",
            file_path=str(file_path)
        ))
    
    return issues, metrics, tasks
