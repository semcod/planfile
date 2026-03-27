#!/usr/bin/env python3
"""Test script to verify markdown backend integration."""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from planfile.integrations.config import IntegrationConfig
from planfile.sync.markdown_backend import MarkdownFileBackend

def test_markdown_backend():
    """Test markdown backend functionality."""
    print("Testing MarkdownFileBackend...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        print(f"Working in: {tmpdir}")
        
        # Test 1: Backend creation
        backend = MarkdownFileBackend()
        print("✓ Backend created successfully")
        
        # Test 2: File creation
        assert Path("CHANGELOG.md").exists(), "CHANGELOG.md should be created"
        assert Path("TODO.md").exists(), "TODO.md should be created"
        print("✓ Markdown files created")
        
        # Test 3: Create ticket
        ticket_data = {
            "title": "Test Feature",
            "description": "This is a test feature implementation",
            "labels": ["feature"],
            "priority": "high"
        }
        ticket = backend.create_ticket(ticket_data)
        print(f"✓ Ticket created: {ticket.id}")
        
        # Test 4: Duplicate prevention
        try:
            duplicate_ticket = {
                "title": "Test Feature",
                "description": "Duplicate ticket",
                "labels": ["duplicate"]
            }
            backend.create_ticket(duplicate_ticket)
            print("✗ Duplicate prevention failed!")
            return False
        except ValueError as e:
            if "already exists" in str(e):
                print("✓ Duplicate prevention works")
            else:
                print(f"✗ Unexpected error: {e}")
                return False
        
        # Test 5: Integration config fallback
        config = IntegrationConfig(".")
        config.load_configs()
        assert config.validate_integration("markdown"), "Markdown should always be valid"
        print("✓ Integration config validates markdown")
        
        # Test 6: Default backend
        default_backend = config.get_default_backend()
        assert isinstance(default_backend, MarkdownFileBackend), "Should return MarkdownFileBackend"
        print("✓ Default backend returns MarkdownFileBackend")
        
        print("\n✅ All tests passed!")
        return True

if __name__ == "__main__":
    success = test_markdown_backend()
    sys.exit(0 if success else 1)
