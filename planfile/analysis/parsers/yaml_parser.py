import yaml
from pathlib import Path
from typing import Tuple, List, Any

from planfile import models
from planfile.analysis.models import ExtractedIssue, ExtractedMetric, ExtractedTask
from planfile.analysis.parsers.text_parser import analyze_text
from planfile.analysis.parsers.toon_parser import analyze_toon

def extract_from_yaml_structure(data: Any, path: str, parent_key: str = "", visited: set = None) -> List[ExtractedIssue]:
    """Extract issues from YAML structure with recursion protection."""
    if visited is None:
        visited = set()
    
    issues = []
    
    # Prevent infinite recursion
    if id(data) in visited:
        return issues
    visited.add(id(data))
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            
            # Skip if we're already processing issues (prevent self-reference)
            if 'issues' in full_key.lower():
                continue
            
            # Look for common issue indicators, but not in our own generated content
            if isinstance(value, str) and len(value) < 500:  # Limit string length
                if any(keyword in value.lower() for keyword in ['error', 'fail', 'bug', 'issue']):
                    # Skip if this looks like our own generated issue
                    if not any(skip in value.lower() for skip in ['extractedissue', 'file_path', 'priority:', 'category:']):
                        issues.append(ExtractedIssue(
                            title=f"Issue in {full_key}",
                            description=value[:200],  # Limit description length
                            priority="medium",
                            category="bug",
                            file_path=path
                        ))
            
            # Recurse with protection
            issues.extend(extract_from_yaml_structure(value, path, full_key, visited))
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            issues.extend(extract_from_yaml_structure(item, path, f"{parent_key}[{i}]", visited))
    
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
