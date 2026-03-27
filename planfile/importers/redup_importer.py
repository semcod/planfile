"""Redup duplication importer for planfile."""

import re
import yaml
from typing import Dict, List, Any
from datetime import datetime


def import_redup(file_path: str) -> List[dict]:
    """Import duplication issues from redup toon.yaml file.
    
    Args:
        file_path: Path to duplication.toon.yaml file
        
    Returns:
        List of ticket dictionaries representing refactoring opportunities
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Parse the toon format
    data = _parse_toon_format(content)
    
    tickets = []
    
    # Extract refactoring suggestions
    refactor_section = data.get('REFACTOR', [])
    
    for i, item in enumerate(refactor_section):
        ticket = _create_refactor_ticket(item, i + 1)
        if ticket:
            tickets.append(ticket)
    
    return tickets


def _parse_toon_format(content: str) -> Dict[str, Any]:
    """Parse redup toon.yaml format into structured data."""
    data = {}
    
    # Parse SUMMARY
    summary_match = re.search(r'SUMMARY:(.*?)(?=DUPLICATES|$)', content, re.DOTALL)
    if summary_match:
        summary_text = summary_match.group(1).strip()
        data['SUMMARY'] = {}
        for line in summary_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                data['SUMMARY'][key.strip()] = value.strip()
    
    # Parse DUPLICATES
    dup_match = re.search(r'DUPLICATES\[(\d+)\](.*?)(?=REFACTOR|$)', content, re.DOTALL)
    if dup_match:
        dup_text = dup_match.group(2).strip()
        data['DUPLICATES'] = _parse_duplicates(dup_text)
    
    # Parse REFACTOR
    refactor_match = re.search(r'REFACTOR\[(\d+)\](.*?)(?=METRICS-TARGET|$)', content, re.DOTALL)
    if refactor_match:
        refactor_text = refactor_match.group(2).strip()
        data['REFACTOR'] = _parse_refactor(refactor_text)
    
    # Parse METRICS-TARGET
    metrics_match = re.search(r'METRICS-TARGET:(.*?)(?=$)', content, re.DOTALL)
    if metrics_match:
        metrics_text = metrics_match.group(1).strip()
        data['METRICS-TARGET'] = {}
        for line in metrics_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                data['METRICS-TARGET'][key.strip()] = value.strip()
    
    return data


def _parse_duplicates(text: str) -> List[Dict[str, Any]]:
    """Parse DUPLICATES section."""
    duplicates = []
    current_dup = None
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Parse duplicate header
        header_match = re.match(r'\[([a-f0-9]+)\]\s+(\w+)\s+(\w+)\s+L=(\d+)\s+N=(\d+)\s+saved=(\d+)\s+sim=([\d.]+)', line)
        if header_match:
            if current_dup:
                duplicates.append(current_dup)
            current_dup = {
                'hash': header_match.group(1),
                'type': header_match.group(2),
                'name': header_match.group(3),
                'lines': int(header_match.group(4)),
                'occurrences': int(header_match.group(5)),
                'saved': int(header_match.group(6)),
                'similarity': float(header_match.group(7)),
                'files': []
            }
        elif current_dup and line.startswith('      '):
            # Parse file location
            file_match = re.match(r'(\S+):(\d+)-(\d+)\s+\((\w+)\)', line.strip())
            if file_match:
                current_dup['files'].append({
                    'path': file_match.group(1),
                    'start': int(file_match.group(2)),
                    'end': int(file_match.group(3)),
                    'function': file_match.group(4)
                })
    
    if current_dup:
        duplicates.append(current_dup)
    
    return duplicates


def _parse_refactor(text: str) -> List[Dict[str, Any]]:
    """Parse REFACTOR section."""
    refactor_items = []
    current_item = None
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Parse refactor item header
        header_match = re.match(r'\[(\d+)\]\s+○\s+(\w+)\s+→\s+(\S+)', line)
        if header_match:
            if current_item:
                refactor_items.append(current_item)
            current_item = {
                'priority': int(header_match.group(1)),
                'action': header_match.group(2),
                'target': header_match.group(3),
                'why': '',
                'files': []
            }
        elif current_item and line.startswith('WHY:'):
            current_item['why'] = line[4:].strip()
        elif current_item and line.startswith('FILES:'):
            files_str = line[6:].strip()
            current_item['files'] = [f.strip() for f in files_str.split(',')]
    
    if current_item:
        refactor_items.append(current_item)
    
    return refactor_items


def _create_refactor_ticket(item: Dict[str, Any], index: int) -> dict:
    """Create a ticket dictionary from a refactor item."""
    # Extract saved lines from WHY clause
    saved_match = re.search(r'saves (\d+) lines', item.get('why', ''))
    saved_lines = int(saved_match.group(1)) if saved_match else 0
    
    # Determine priority based on lines saved
    if saved_lines > 20:
        priority = "critical"
    elif saved_lines > 10:
        priority = "high"
    elif saved_lines > 5:
        priority = "normal"
    else:
        priority = "low"
    
    # Create title
    action_map = {
        'extract_base_class': 'Extract base class',
        'extract_function': 'Extract function',
        'create_template': 'Create template',
        'consolidate': 'Consolidate code'
    }
    
    action = action_map.get(item['action'], item['action'].replace('_', ' ').title())
    title = f"{action} to eliminate code duplication"
    
    # Build description
    description = item.get('why', '')
    
    # Add affected files
    if item.get('files'):
        description += f"\n\nAffected files:\n"
        for file_path in item['files']:
            description += f"- {file_path}\n"
    
    # Add target location
    if item.get('target'):
        description += f"\nTarget location: {item['target']}"
    
    # Create acceptance criteria
    acceptance_criteria = [
        "Extract duplicated code to shared location",
        "Update all files to use extracted code",
        "Verify functionality remains unchanged",
        "Run tests to ensure no regressions"
    ]
    
    # Add labels
    labels = ['refactoring', 'code-quality', 'duplication']
    if saved_lines > 10:
        labels.append('high-impact')
    
    return {
        'title': title,
        'description': description,
        'status': 'open',
        'priority': priority,
        'labels': labels,
        'acceptance_criteria': acceptance_criteria,
        'source': {
            'tool': 'redup',
            'timestamp': datetime.now().isoformat(),
            'context': {
                'saved_lines': saved_lines,
                'refactor_action': item['action'],
                'target': item['target'],
                'files': item['files']
            }
        }
    }
