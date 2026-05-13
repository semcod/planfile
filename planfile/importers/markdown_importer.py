"""Import tickets from standard markdown task lists (TODO.md)."""

import re
from pathlib import Path

def import_markdown(path: str, **kwargs) -> list[dict]:
    """Parse a markdown file containing task list items (- [ ] ...).
    
    Specifically supports the 'prefact' format: path/to/file.py:line - Description
    """
    file_path = Path(path)
    if not file_path.exists():
        return []
        
    content = file_path.read_text(encoding="utf-8")
    # Regex pattern: - [ ] path/to/file.py:123 - Description OR - [ ] Description
    pattern = re.compile(r"-\s*\[\s*\]\s*([^\s:]+):(\d+|\?)\s*-\s*(.+)")
    generic_pattern = re.compile(r"-\s*\[\s*\]\s*(.+)")
    
    tickets = []
    seen_titles = set()
    
    # Try specific line pattern first
    matches = pattern.findall(content)
    if matches:
        for file_loc, line, desc in matches:
            if desc in seen_titles:
                continue
            seen_titles.add(desc)
            
            title = f"Fix {desc.split(':')[0]}" if ":" in desc else desc
            if len(title) > 60:
                title = title[:57] + "..."
                
            tickets.append({
                "name": title,
                "description": f"{desc}\nLocation: {file_loc}:{line}",
                "labels": ["markdown", "todo-import"],
                "files": [file_loc],
                "priority": "normal"
            })
        return tickets
        
    # Fallback to simple task lines
    for line in content.splitlines():
        match = generic_pattern.search(line)
        if match:
            desc = match.group(1).strip()
            if desc in seen_titles:
                continue
            seen_titles.add(desc)
            tickets.append({
                "name": desc[:60],
                "description": desc,
                "labels": ["markdown", "todo-import"]
            })
            
    return tickets
