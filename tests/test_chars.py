#!/usr/bin/env python3
"""Debug: check what characters are actually in the content."""

content = """**ID:** `refactor-cli-20250329-123045`"""

print("Character codes:")
for i, char in enumerate(content):
    if char == '`' or ord(char) > 127:
        print(f"  Position {i}: char='{char}' code={ord(char)}")
