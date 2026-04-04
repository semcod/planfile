"""README detection utilities."""

from __future__ import annotations

import re
from pathlib import Path


def _find_readme_content(project_path: Path) -> tuple[str | None, str | None]:
    """
    Extract description and goal from README.
    Returns: (description, goal) - goal is first meaningful paragraph, description can be from badges/tagline
    """
    readme_files = ["README.md", "README.rst", "README.txt", "README"]

    for readme_name in readme_files:
        readme_path = project_path / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                description = None
                goal = None

                # Find first non-empty, non-header line for description
                for line in lines:
                    line_stripped = line.strip()
                    # Skip empty lines, headers, and badges
                    if not line_stripped or line_stripped.startswith("#") or line_stripped.startswith("["):
                        continue
                    # Remove markdown formatting
                    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line_stripped)  # links
                    cleaned = re.sub(r"[*_`~]", "", cleaned)  # formatting chars
                    if len(cleaned) > 10:
                        description = cleaned[:200]
                        break

                # Find a better "goal" - look for summary/intro paragraph
                # Skip past badges and find first substantial paragraph
                content_without_badges = re.sub(r'\[!?\[.*?\]\(.*?\)\]\(.*?\)', '', content)
                content_without_badges = re.sub(r'!\[.*?\]\(.*?\)', '', content_without_badges)
                paragraphs = [p.strip() for p in content_without_badges.split('\n\n') if p.strip()]

                for para in paragraphs:
                    # Skip short lines (likely badges), headers, and code blocks
                    if len(para) < 20 or para.startswith('#') or para.startswith('```'):
                        continue
                    # Clean markdown
                    cleaned_para = re.sub(r"[*_`~]", "", para)
                    cleaned_para = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned_para)
                    if len(cleaned_para) > 30:
                        goal = cleaned_para[:150]
                        break

                return description, goal
            except Exception:
                return None, None
    return None, None


def _find_readme_description(project_path: Path) -> str | None:
    """Extract first paragraph from README as description."""
    desc, _ = _find_readme_content(project_path)
    return desc


def _find_readme_goal(project_path: Path) -> str | None:
    """Extract goal/summary from README."""
    _, goal = _find_readme_content(project_path)
    return goal
